"""Bounded, login-independent research candidate scanning; never authorizes risk or execution."""
from __future__ import annotations
from datetime import UTC, datetime, timedelta
from statistics import mean
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from .config import Settings
from .data.dividends import recovery_estimate
from .models import CandidateScanState, DataRecord, Instrument, StrategyDecision, StrategyScenario, StrategyVersion
from .strategy_engine import canonical_checksum, evaluate

RECORD_TYPES=("OHLCV","BROKER_OHLCV","CORPORATE_ACTION","BROKER_EARNINGS","FUNDAMENTALS","BROKER_FUNDAMENTALS","BROKER_FUNDAMENTAL")

def _utc(value:datetime)->datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

def _number(value):
    try:return float(value) if value is not None else None
    except (TypeError,ValueError):return None

def _facts(db:Session,instrument:Instrument,version:StrategyVersion,now:datetime,max_price_age_days:int)->tuple[dict|None,str]:
    rows=db.scalars(select(DataRecord).where(DataRecord.instrument_id==instrument.id,DataRecord.data_type.in_(RECORD_TYPES),DataRecord.quality_status!="REJECTED").order_by(DataRecord.event_time.desc(),DataRecord.ingested_at.desc()).limit(3000)).all()
    bars={};actions=[];earnings=[];fundamentals={}
    for row in reversed(rows):
        payload=row.payload or {}
        if row.data_type in {"OHLCV","BROKER_OHLCV"}:
            close=_number(payload.get("adjusted_close",payload.get("close")));volume=_number(payload.get("volume"))
            if close is not None and close>0:bars[row.event_time.date()]={"close":close,"volume":volume or 0}
        elif row.data_type=="CORPORATE_ACTION" and str(payload.get("action","DIVIDEND")).upper()=="DIVIDEND":actions.append((_utc(row.event_time),payload))
        elif row.data_type=="BROKER_EARNINGS":earnings.append(_utc(row.event_time))
        elif row.data_type in {"FUNDAMENTALS","BROKER_FUNDAMENTALS","BROKER_FUNDAMENTAL"}:
            result=payload.get("result",{});inner=result.get("data",result) if isinstance(result,dict) else {};items=inner.get("results",[]) if isinstance(inner,dict) else [];match=next((item for item in items if isinstance(item,dict) and str(item.get("symbol","")).upper()==instrument.symbol),None)
            fundamentals.update(match or payload)
    if not bars:return None,"NO_PRICE_HISTORY"
    ordered=sorted(bars);latest_day=ordered[-1]
    if latest_day < (now-timedelta(days=max_price_age_days)).date():return None,"STALE_PRICE_HISTORY"
    upcoming=sorted(((event,payload) for event,payload in actions if event>=now),key=lambda item:(item[0],0 if str(item[1].get("source_provider","")).upper()=="ROBINHOOD" else 1));event,payload=upcoming[0] if upcoming else (None,{})
    latest_close=bars[latest_day]["close"];amount=_number(payload.get("dividend_per_share",payload.get("amount")))
    action_dates=[item.date() for item,_ in actions];evidence=recovery_estimate(action_dates,{day:item["close"] for day,item in bars.items()},now.date())
    parameters=version.specification.get("parameters",{});earnings_window=int(parameters.get("earnings_exclusion_days",5) or 5)
    recent=ordered[-20:]
    facts={"latest_close":round(latest_close,6),"latest_price_date":latest_day.isoformat(),"average_daily_volume":round(mean([bars[day]["volume"] for day in recent]),2),"average_daily_dollar_volume":round(mean([bars[day]["close"]*bars[day]["volume"] for day in recent]),2),"dividend_per_share":amount,"event_yield_pct":round(amount/latest_close*100,6) if amount is not None else None,"annual_yield_pct":_number(payload.get("annual_yield_pct")),"next_ex_dividend_date":event.date().isoformat() if event else None,"days_to_ex_dividend":(event.date()-now.date()).days if event else None,"recovery_probability_pct":evidence["recovery_probability_pct"],"recovery_observations":evidence["recovery_observations"],"historical_dividend_events":evidence["historical_dividend_events"],"dividend_history_years":round((now.date()-min(action_dates)).days/365.25,3) if action_dates else None,"recovery_p90_days":evidence["recovery_p90_days"],"estimated_recovery_days":evidence["estimated_recovery_days"],"maximum_historical_drawdown_pct":evidence["maximum_historical_drawdown_pct"],"payment_frequency":str(payload.get("payment_frequency","")).upper() or None,"special_dividend":bool(payload.get("special",False)),"market_cap":_number(fundamentals.get("market_cap",fundamentals.get("market_capitalization"))),"asset_type":instrument.asset_type,"earnings_excluded":any(now<=earning<=now+timedelta(days=earnings_window) for earning in earnings),"recovered":False,"holding_days":0,"evidence_authority":"NORMALIZED_READ_ONLY_DATA"}
    facts["scanner_evidence_checksum"]=canonical_checksum(facts);return facts,"READY"


def _versions(db:Session)->list[StrategyVersion]:
    latest=select(StrategyVersion.scenario_id,func.max(StrategyVersion.version).label("version")).group_by(StrategyVersion.scenario_id).subquery()
    rows=list(db.scalars(select(StrategyVersion).join(latest,(latest.c.scenario_id==StrategyVersion.scenario_id)&(latest.c.version==StrategyVersion.version)).join(StrategyScenario,StrategyScenario.id==StrategyVersion.scenario_id).where(StrategyScenario.lifecycle=="RESEARCH").order_by(StrategyVersion.id)).all())
    required={"universe","entry_rules","exit_rules","filters","position_sizing"}
    return [version for version in rows if required.issubset((version.specification or {}).keys())]

def _due_instruments(db:Session,version:StrategyVersion,now:datetime,limit:int)->list[tuple[Instrument,CandidateScanState|None]]:
    state_join=(CandidateScanState.version_id==version.id)&(CandidateScanState.instrument_id==Instrument.id)
    next_ex=select(func.min(DataRecord.event_time)).where(DataRecord.instrument_id==Instrument.id,DataRecord.data_type=="CORPORATE_ACTION",DataRecord.quality_status!="REJECTED",DataRecord.event_time>=now).correlate(Instrument).scalar_subquery()
    has_dividend=select(func.count(DataRecord.id)).where(DataRecord.instrument_id==Instrument.id,DataRecord.data_type=="CORPORATE_ACTION",DataRecord.quality_status!="REJECTED").correlate(Instrument).scalar_subquery()
    rank=case((next_ex.is_not(None),0),(has_dividend>0,1),else_=2)
    query=select(Instrument,CandidateScanState).outerjoin(CandidateScanState,state_join).where(Instrument.active.is_(True),(CandidateScanState.id.is_(None))|(CandidateScanState.next_scan_at<=now))
    allowed=version.specification.get("universe",{}).get("symbols",[]);excluded=version.specification.get("universe",{}).get("exclude_symbols",[]);assets=version.specification.get("universe",{}).get("asset_types",[])
    if allowed:query=query.where(Instrument.symbol.in_(allowed))
    if excluded:query=query.where(Instrument.symbol.not_in(excluded))
    if assets:query=query.where(Instrument.asset_type.in_(assets))
    return list(db.execute(query.order_by(rank,case((CandidateScanState.id.is_(None),0),else_=1),CandidateScanState.next_scan_at,next_ex,Instrument.symbol).limit(limit)).all())


def scan_batch(db:Session,settings:Settings,now:datetime|None=None)->dict:
    now=(now or datetime.now(UTC)).astimezone(UTC);versions=_versions(db);result={"versions":len(versions),"scanned":0,"decisions":0,"entries":0,"not_ready":0,"risk_authorized":False,"executable":False,"trading":"DISABLED"}
    if not versions:return result
    base=max(1,settings.candidate_scanner_batch_size//len(versions));remaining=settings.candidate_scanner_batch_size
    for index,version in enumerate(versions):
        allowance=remaining if index==len(versions)-1 else min(base,remaining)
        due=_due_instruments(db,version,now,allowance);used=0
        for instrument,state in due:
            used+=1
            facts,detail=_facts(db,instrument,version,now,settings.candidate_scanner_max_price_age_days);result["scanned"]+=1
            if state is None:state=CandidateScanState(version_id=version.id,instrument_id=instrument.id,last_scanned_at=now,next_scan_at=now);db.add(state)
            state.last_scanned_at=now;state.detail=detail
            if facts is None:state.outcome="NOT_READY";state.next_scan_at=now+timedelta(hours=6);result["not_ready"]+=1;continue
            checksum=facts["scanner_evidence_checksum"];decision=evaluate(version.specification,instrument.symbol,facts,now)
            if checksum!=state.evidence_checksum or decision["decision"]!=state.outcome:
                row=StrategyDecision(version_id=version.id,symbol=instrument.symbol,as_of=now,decision=decision["decision"],reason_codes=decision["reason_codes"],proposed_weight_pct=decision["proposed_weight_pct"],inputs=facts);db.add(row);db.flush();state.last_decision_id=row.id;result["decisions"]+=1
            state.evidence_checksum=checksum;state.outcome=decision["decision"]
            if decision["decision"]=="ENTRY":result["entries"]+=1
            seconds=settings.candidate_scanner_interval_seconds if decision["decision"]=="ENTRY" else max(3600,settings.candidate_scanner_interval_seconds);state.next_scan_at=now+timedelta(seconds=seconds)
        remaining-=used
        if remaining<=0:break
    db.commit();return result
