"""Deterministic Dividend Farm recovery-exit lifecycle.

This module detects filled Aegis-managed entries, verifies the selected broker
still owns the shares, and creates an immutable EXIT decision plus a risk-review
plan when a fresh price reaches the actual entry fill price on/after ex-date.
It never calls a broker or submits an order.
"""
from __future__ import annotations
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import BrokerSnapshot, ControlledExecutionRecord, ControlledTradeIntent, DataRecord, DevelopmentActivity, DividendFarmPosition, Instrument, PlannedTrade, StrategyDecision
from .strategy_engine import canonical_checksum


def _number(value):
    try:return float(str(value).replace("$","").replace(",",""))
    except (TypeError,ValueError):return None

def _find(value, keys):
    if isinstance(value,dict):
        for key in keys:
            if key in value and (found:=_number(value[key])) is not None:return found
        for child in value.values():
            if (found:=_find(child,keys)) is not None:return found
    elif isinstance(value,list):
        for child in value:
            if (found:=_find(child,keys)) is not None:return found
    return None

def _fill_totals(fills):
    rows=[]
    def walk(value):
        if isinstance(value,dict):
            quantity=_find(value,("quantity","executed_quantity","filled_quantity"));price=_find(value,("price","execution_price","average_price"))
            if quantity and price:rows.append((quantity,price,value.get("timestamp") or value.get("executed_at") or value.get("filled_at")))
            else:
                for child in value.values():walk(child)
        elif isinstance(value,list):
            for child in value:walk(child)
    walk(fills)
    quantity=sum(row[0] for row in rows);notional=sum(row[0]*row[1] for row in rows)
    return quantity,(notional/quantity if quantity else 0),next((row[2] for row in reversed(rows) if row[2]),None)

def capture_filled_entries(db:Session)->list[int]:
    """Register reconciled Aegis BUY fills exactly once."""
    records=db.scalars(select(ControlledExecutionRecord).where(ControlledExecutionRecord.status.in_(("FILLED","RECONCILED"))).order_by(ControlledExecutionRecord.id)).all();created=[]
    for record in records:
        if db.scalar(select(DividendFarmPosition).where(DividendFarmPosition.entry_execution_id==record.id)):continue
        intent=db.get(ControlledTradeIntent,record.intent_id)
        if not intent or intent.side!="BUY":continue
        decision=db.get(StrategyDecision,intent.strategy_decision_id)
        if not decision or decision.decision!="ENTRY":continue
        quantity,price,filled_at=_fill_totals(record.fills)
        try:ex_date=datetime.fromisoformat(str(decision.inputs.get("next_ex_dividend_date"))).date()
        except (TypeError,ValueError):continue
        if quantity<=0 or price<=0:continue
        timestamp=datetime.fromisoformat(str(filled_at).replace("Z","+00:00")) if filled_at else record.updated_at
        if timestamp.tzinfo is None:timestamp=timestamp.replace(tzinfo=UTC)
        plan=db.scalar(select(PlannedTrade).where(PlannedTrade.strategy_decision_id==decision.id,PlannedTrade.side=="BUY").order_by(PlannedTrade.id.desc()))
        row=DividendFarmPosition(entry_execution_id=record.id,entry_plan_id=plan.id if plan else None,strategy_decision_id=decision.id,symbol=intent.symbol,quantity=quantity,entry_price=price,entry_filled_at=timestamp,ex_dividend_date=ex_date,exit_target_price=price,status="OPEN",created_by="system:fill-reconciliation")
        db.add(row);db.flush();created.append(row.id)
        if plan:plan.status="FILLED";plan.quantity=quantity;plan.reference_price=price;plan.reserved_notional=0
        db.add(DevelopmentActivity(actor="system:fill-reconciliation",action="dividend_position_opened",entity_type="dividend_farm_position",entity_id=row.id,detail=f"symbol={row.symbol}; reconciled_fill=true; exit_target=purchase_price; broker_called=false"))
    if created:db.commit()
    return created

def _holding_quantity(snapshot:BrokerSnapshot,symbol:str)->float:
    total=0.0
    for group in snapshot.holdings or []:
        for row in group.get("records",[]):
            if not isinstance(row,dict) or str(row.get("symbol") or row.get("ticker") or "").upper()!=symbol:continue
            total+=_number(row.get("quantity") or row.get("total_quantity") or row.get("shares")) or 0
    return total

def monitor_recovery_exits(db:Session,now:datetime|None=None,max_price_age_seconds:int=300,max_snapshot_age_seconds:int=900)->list[int]:
    """Create deduplicated EXIT plans from fresh, verified evidence; never execute."""
    now=(now or datetime.now(UTC)).astimezone(UTC);snapshot=db.scalar(select(BrokerSnapshot).order_by(BrokerSnapshot.source_observed_at.desc()))
    if not snapshot or snapshot.status not in {"VERIFIED","PARTIAL"}:return []
    observed=snapshot.source_observed_at if snapshot.source_observed_at.tzinfo else snapshot.source_observed_at.replace(tzinfo=UTC)
    if (now-observed).total_seconds()>max_snapshot_age_seconds:return []
    created=[]
    for position in db.scalars(select(DividendFarmPosition).where(DividendFarmPosition.status=="OPEN").order_by(DividendFarmPosition.id)).all():
        if now.date()<position.ex_dividend_date:continue
        owned=_holding_quantity(snapshot,position.symbol)
        if owned+1e-9<position.quantity:continue
        instrument=db.scalar(select(Instrument).where(Instrument.symbol==position.symbol));
        if not instrument:continue
        quote=db.scalar(select(DataRecord).where(DataRecord.instrument_id==instrument.id,DataRecord.data_type.in_(("BROKER_QUOTE","QUOTE")),DataRecord.quality_status.in_(("VALID","WARNING"))).order_by(DataRecord.event_time.desc()))
        if not quote:continue
        quoted_at=quote.event_time if quote.event_time.tzinfo else quote.event_time.replace(tzinfo=UTC)
        age=(now-quoted_at).total_seconds()
        if age<0 or age>max_price_age_seconds:continue
        price=_find(quote.payload,("last_trade_price","mark_price","last_price","price","close"))
        if not price or price+1e-9<position.exit_target_price:continue
        entry=db.get(StrategyDecision,position.strategy_decision_id)
        frozen={"position_id":position.id,"entry_decision_id":entry.id,"symbol":position.symbol,"quantity":position.quantity,"entry_price":position.entry_price,"exit_target_price":position.exit_target_price,"observed_price":price,"price_record_id":quote.id,"price_observed_at":quoted_at.isoformat(),"broker_snapshot_id":snapshot.id,"ex_dividend_date":position.ex_dividend_date.isoformat(),"trigger":"PURCHASE_PRICE_RECOVERED"}
        decision=StrategyDecision(version_id=entry.version_id,symbol=position.symbol,as_of=now,decision="EXIT",reason_codes=["EX_DATE_REACHED","PURCHASE_PRICE_RECOVERED","BROKER_POSITION_VERIFIED","FRESH_PRICE_VERIFIED"],proposed_weight_pct=0,inputs=frozen)
        db.add(decision);db.flush();plan_frozen={"strategy_decision_id":decision.id,"symbol":position.symbol,"side":"SELL","quantity":position.quantity,"reference_price":price,"planned_entry_date":now.date().isoformat(),"trigger":"PURCHASE_PRICE_RECOVERED"}
        plan=PlannedTrade(strategy_decision_id=decision.id,symbol=position.symbol,side="SELL",quantity=position.quantity,reference_price=price,reserved_notional=0,planned_entry_date=now.date(),status="EXIT_RISK_REVIEW_REQUIRED",rationale="Dividend Farm purchase-price recovery verified on/after ex-date; deterministic RiskEngine authorization required",plan_checksum=canonical_checksum(plan_frozen),notification_status="PENDING",notification_event="EXIT_RECOVERY_TRIGGERED",created_by="system:dividend-exit-monitor")
        db.add(plan);db.flush();position.status="EXIT_SIGNALLED";position.exit_strategy_decision_id=decision.id;position.exit_plan_id=plan.id;position.last_observed_price=price;position.last_observed_at=quoted_at
        db.add(DevelopmentActivity(actor="system:dividend-exit-monitor",action="dividend_recovery_exit_planned",entity_type="dividend_farm_position",entity_id=position.id,detail=f"symbol={position.symbol}; target={position.exit_target_price:.6f}; observed={price:.6f}; risk_authorized=false; broker_called=false; trading=DISABLED"));created.append(plan.id)
    if created:db.commit()
    return created

def authorize_recovery_exits(db:Session,now:datetime|None=None)->list[int]:
    """Risk-assess fresh recovery exits; execution remains a separate disabled domain."""
    from .broker_sync.service import serialize_snapshot
    from .data.calendar import EASTERN,market_session
    from .risk.service import assess
    from .schemas import RiskAssessmentRequest
    now=(now or datetime.now(UTC)).astimezone(UTC);authorized=[]
    for plan in db.scalars(select(PlannedTrade).where(PlannedTrade.status=="EXIT_RISK_REVIEW_REQUIRED",PlannedTrade.side=="SELL").order_by(PlannedTrade.id)).all():
        decision=db.get(StrategyDecision,plan.strategy_decision_id);facts=decision.inputs or {};snapshot=db.get(BrokerSnapshot,facts.get("broker_snapshot_id"));quote=db.get(DataRecord,facts.get("price_record_id"))
        if not snapshot or not quote:continue
        snapshot_at=snapshot.source_observed_at if snapshot.source_observed_at.tzinfo else snapshot.source_observed_at.replace(tzinfo=UTC);quote_at=quote.event_time if quote.event_time.tzinfo else quote.event_time.replace(tzinfo=UTC)
        if (now-snapshot_at).total_seconds()>900 or not 0<=(now-quote_at).total_seconds()<=300:continue
        owned=_holding_quantity(snapshot,plan.symbol)
        if owned+1e-9<plan.quantity:continue
        session=market_session(now.astimezone(EASTERN).date());opened=datetime.fromisoformat(session["open_at"]) if session["open_at"] else None;closed=datetime.fromisoformat(session["close_at"]) if session["close_at"] else None;regular=bool(opened and closed and opened<=now<closed)
        instrument=db.scalar(select(Instrument).where(Instrument.symbol==plan.symbol));fractional=abs(plan.quantity-round(plan.quantity))>1e-9
        summary=serialize_snapshot(snapshot,"CONNECTED")["snapshot"]["summary"];position_value=plan.quantity*plan.reference_price;portfolio=max(float(summary.get("portfolio_value") or 0),position_value);cash=float(summary.get("cash") or 0);exposure=max(position_value,portfolio-cash)
        payload=RiskAssessmentRequest(proposal_id=f"dividend-exit-{facts.get('position_id')}-{quote.id}",strategy_decision_id=decision.id,symbol=plan.symbol,side="SELL",quantity=plan.quantity,price=plan.reference_price,reference_price=plan.reference_price,fractional_eligible=bool(instrument and instrument.active and instrument.asset_type in {"EQUITY","ETF"}),regular_session=regular,portfolio_value=portfolio,buying_power=float(summary.get("buying_power") or 0),current_position_value=position_value,total_exposure_value=exposure,sector_exposure_value=position_value,correlated_exposure_value=position_value,daily_pnl_pct=0,drawdown_pct=0,annualized_volatility_pct=0,open_order_count=int(snapshot.reconciliation.get("order_records",0)),market_data_as_of=quote_at,proposal_created_at=now)
        risk=assess(db,payload,"system:dividend-exit-risk",now);plan.final_risk_assessment_id=risk.id;plan.status="RISK_AUTHORIZED_EXIT" if risk.risk_authorized else "EXIT_RISK_BLOCKED";plan.revalidated_at=now;plan.revalidation_detail="FRESH_RECOVERY_EXIT_AUTHORIZED" if risk.risk_authorized else ",".join(risk.reason_codes);plan.notification_status="PENDING";plan.notification_event="EXIT_RISK_AUTHORIZED" if risk.risk_authorized else "EXIT_RISK_BLOCKED"
        db.add(DevelopmentActivity(actor="system:dividend-exit-risk",action="dividend_recovery_exit_risk_reviewed",entity_type="planned_trade",entity_id=plan.id,detail=f"outcome={risk.outcome}; broker_called=false; execution_domain_required=true; trading=DISABLED"))
        if risk.risk_authorized:authorized.append(plan.id)
        db.commit()
    return authorized
