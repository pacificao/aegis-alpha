"""Deterministic lifecycle maintenance for non-executable capital plans."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .data.calendar import dividend_entry_plan, next_sessions
from .models import BrokerSnapshot, CandidateScanState, DevelopmentActivity, PlannedTrade, StrategyDecision, StrategyScenario, StrategyVersion
from .strategy_engine import canonical_checksum

EXPIRABLE_PLAN_STATUSES=frozenset({"PLANNED","REVALIDATION_BLOCKED","READY_FOR_FINAL_APPROVAL"})

def expire_missed_plans(db:Session,today:date)->list[int]:
    """Release reservations after their eligible entry session has passed."""
    rows=db.scalars(select(PlannedTrade).where(PlannedTrade.status.in_(EXPIRABLE_PLAN_STATUSES),PlannedTrade.planned_entry_date<today).order_by(PlannedTrade.id)).all()
    expired=[]
    for row in rows:
        row.status="EXPIRED";row.revalidation_detail="ENTRY_SESSION_PASSED";row.notification_status="PENDING";row.notification_event="PLAN_EXPIRED"
        db.add(DevelopmentActivity(actor="system:plan-lifecycle",action="planned_trade_expired",entity_type="planned_trade",entity_id=row.id,detail=f"symbol={row.symbol}; entry={row.planned_entry_date}; released_notional={row.reserved_notional:.2f}; broker_called=false; trading=DISABLED"));expired.append(row.id)
    if expired:db.commit()
    return expired


def _account_capacity(db:Session)->tuple[float,float]:
    snapshot=db.scalar(select(BrokerSnapshot).order_by(BrokerSnapshot.source_observed_at.desc()))
    buying_power=total_value=0.0
    if snapshot:
        for dataset in snapshot.balances or []:
            if dataset.get("dataset")!="get_portfolio":continue
            for record in dataset.get("records",[]):
                try:total_value=max(total_value,float(record.get("total_value") or 0))
                except (TypeError,ValueError):pass
                value=record.get("buying_power",{});value=value.get("buying_power") if isinstance(value,dict) else value
                try:buying_power=max(buying_power,float(value or 0))
                except (TypeError,ValueError):pass
    return buying_power,total_value

def create_qualified_plans(db:Session,today:date)->list[int]:
    """Reserve capital for fully qualified ENTRY decisions; never assesses risk or calls a broker."""
    scenario=db.scalar(select(StrategyScenario).where(StrategyScenario.name=="Dividend Farm",StrategyScenario.lifecycle=="RESEARCH"))
    if not scenario:return []
    version=db.scalar(select(StrategyVersion).where(StrategyVersion.scenario_id==scenario.id).order_by(StrategyVersion.version.desc()))
    if not version:return []
    sessions={item["session_date"] for item in next_sessions(10,today)};parameters=version.specification.get("parameters",{});entry_offset=int(parameters.get("entry_days_before_ex_date",1));max_position=float(version.specification.get("position_sizing",{}).get("max_position_pct",1))/100;max_allocation=float(version.specification.get("position_sizing",{}).get("max_strategy_allocation_pct",25))/100
    buying_power,portfolio_value=_account_capacity(db);reserved=float(db.scalar(select(func.coalesce(func.sum(PlannedTrade.reserved_notional),0)).where(PlannedTrade.status.in_(EXPIRABLE_PLAN_STATUSES))) or 0)
    deployable=max(0.0,buying_power-reserved);allocation_left=max(0.0,portfolio_value*max_allocation-reserved);created=[]
    states=db.scalars(select(CandidateScanState).where(CandidateScanState.version_id==version.id,CandidateScanState.outcome=="ENTRY").order_by(CandidateScanState.last_scanned_at)).all()
    candidates=[]
    for state in states:
        decision=db.get(StrategyDecision,state.last_decision_id) if state.last_decision_id else None
        if not decision or decision.decision!="ENTRY":continue
        try:ex_date=date.fromisoformat(str(decision.inputs.get("next_ex_dividend_date")));entry=date.fromisoformat(dividend_entry_plan(ex_date,entry_offset)["planned_entry_date"])
        except (TypeError,ValueError):continue
        if entry.isoformat() in sessions and entry>=today:candidates.append((entry,ex_date,decision))
    for entry,ex_date,decision in sorted(candidates,key=lambda item:(item[0],item[1],item[2].symbol)):
        if deployable<1 or allocation_left<1:break
        if db.scalar(select(PlannedTrade).where(PlannedTrade.symbol==decision.symbol,PlannedTrade.planned_entry_date==entry,PlannedTrade.status.in_(EXPIRABLE_PLAN_STATUSES))):continue
        price=float(decision.inputs.get("latest_close") or 0);micro=portfolio_value<100;target=1.0 if micro else portfolio_value*max_position;notional=round(min(target,deployable,allocation_left),2)
        if price<=0 or notional<1:continue
        quantity=round(notional/price,6);reserved_notional=round(quantity*price,2)
        if reserved_notional<1:continue
        frozen={"strategy_decision_id":decision.id,"symbol":decision.symbol,"side":"BUY","quantity":quantity,"reference_price":price,"reserved_notional":reserved_notional,"planned_entry_date":entry.isoformat(),"trading":"DISABLED"};row=PlannedTrade(strategy_decision_id=decision.id,symbol=decision.symbol,side="BUY",quantity=quantity,reference_price=price,reserved_notional=reserved_notional,planned_entry_date=entry,status="PLANNED",rationale=f"Fully qualified Dividend Farm v{version.version} ENTRY; final session and RiskEngine review required",plan_checksum=canonical_checksum(frozen),notification_status="PENDING",notification_event="PLAN_CREATED",created_by="system:qualified-planner")
        db.add(row);db.flush();db.add(DevelopmentActivity(actor="system:qualified-planner",action="planned_trade_created",entity_type="planned_trade",entity_id=row.id,detail=f"symbol={row.symbol}; reserved_notional={reserved_notional:.2f}; entry={entry}; risk_authorized=false; broker_called=false; trading=DISABLED"));created.append(row.id);deployable-=reserved_notional;allocation_left-=reserved_notional
    if created:db.commit()
    return created
