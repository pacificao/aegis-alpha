from __future__ import annotations
from datetime import UTC,date,datetime,timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import DataRecord,DevelopmentActivity,Instrument,LabRun,LabTrade,StrategyVersion
from .engine import Action,Bar,checksum,sensitivity,simulate

def _number(payload:dict,*keys,default=0.0):
    for key in keys:
        value=payload.get(key)
        if value not in (None,""):
            try:return float(value)
            except (TypeError,ValueError):pass
    return default

def load_market_data(db:Session,symbols:list[str],start:date,end:date):
    wanted=set(symbols); start_at=datetime.combine(start,datetime.min.time(),tzinfo=UTC); end_before=datetime.combine(end+timedelta(days=1),datetime.min.time(),tzinfo=UTC); rows=db.execute(select(DataRecord,Instrument.symbol).join(Instrument,DataRecord.instrument_id==Instrument.id).where(Instrument.symbol.in_(wanted),DataRecord.event_time>=start_at,DataRecord.event_time<end_before,DataRecord.quality_status!="REJECTED").order_by(DataRecord.event_time)).all()
    bars=[];actions=[];checksums=[];providers=set();source_urls=set()
    for record,symbol in rows:
        checksums.append(record.checksum);source_urls.add(record.source_url);providers.add(record.provider_id);payload=record.payload
        if record.data_type=="OHLCV":bars.append(Bar(record.event_time.date(),symbol,_number(payload,"open"),_number(payload,"high"),_number(payload,"low"),_number(payload,"close"),int(_number(payload,"volume"))))
        elif record.data_type=="CORPORATE_ACTION":
            kind=str(payload.get("action","")).upper()
            if kind=="DIVIDEND":actions.append(Action(record.event_time.date(),symbol,"DIVIDEND",_number(payload,"amount","dividend_amount","cash_amount")))
            elif kind=="SPLIT":actions.append(Action(record.event_time.date(),symbol,"SPLIT",_number(payload,"ratio","split_coefficient",default=1)))
    available={b.symbol for b in bars};missing=wanted-available
    if missing:raise ValueError(f"No normalized OHLCV data for: {', '.join(sorted(missing))}")
    provenance={"record_count":len(rows),"bar_count":len(bars),"action_count":len(actions),"record_checksums":sorted(set(checksums)),"provider_ids":sorted(providers),"source_urls":sorted(source_urls),"symbols":sorted(wanted),"start":start.isoformat(),"end":end.isoformat()}
    return bars,actions,provenance

def run_backtest(db:Session,payload,actor:str)->LabRun:
    version=db.get(StrategyVersion,payload.strategy_version_id)
    if version is None:raise ValueError("Strategy version not found")
    config=payload.model_dump(mode="json"); config["start_date"]=payload.start_date.date().isoformat();config["end_date"]=payload.end_date.date().isoformat()
    requested=sorted(set(payload.symbols+[payload.benchmark_symbol.upper()]));bars,actions,provenance=load_market_data(db,requested,payload.start_date.date(),payload.end_date.date())
    identity=checksum({"strategy_checksum":version.checksum,"configuration":config,"data_checksums":provenance["record_checksums"]})
    existing=db.scalar(select(LabRun).where(LabRun.strategy_version_id==version.id,LabRun.configuration_checksum==identity))
    if existing:return existing
    result=simulate(bars,actions,config); variants=sensitivity(bars,actions,config) if payload.run_sensitivity else []
    run=LabRun(strategy_version_id=version.id,status="COMPLETE",configuration=config,configuration_checksum=identity,metrics=result["metrics"],equity_curve=result["equity_curve"],walk_forward=result["walk_forward"],monte_carlo=result["monte_carlo"],sensitivity=variants,data_provenance=provenance,detail=f"{len(result['trades'])} trades; reproducible research only; trading=DISABLED",created_by=actor)
    db.add(run);db.flush()
    for trade in result["trades"]:db.add(LabTrade(run_id=run.id,symbol=trade["symbol"],entry_day=date.fromisoformat(trade["entry_day"]),exit_day=date.fromisoformat(trade["exit_day"]),shares=trade["shares"],entry_price=trade["entry_price"],exit_price=trade["exit_price"],dividends=trade["dividends"],costs=trade["costs"],pnl=trade["pnl"],return_pct=trade["return_pct"],holding_days=trade["holding_days"],exit_reason=trade["exit_reason"],max_drawdown_pct=trade["max_drawdown_pct"]))
    db.add(DevelopmentActivity(actor=actor,action="lab_backtest_completed",entity_type="lab_run",entity_id=run.id,detail=f"version={version.version}; symbols={','.join(payload.symbols)}; trades={len(result['trades'])}; trading=DISABLED"));db.commit();db.refresh(run);return run

def serialize_run(run:LabRun,include_curve=False):
    value={"id":run.id,"strategy_version_id":run.strategy_version_id,"status":run.status,"configuration":run.configuration,"configuration_checksum":run.configuration_checksum,"metrics":run.metrics,"walk_forward":run.walk_forward,"monte_carlo":run.monte_carlo,"sensitivity":run.sensitivity,"data_provenance":run.data_provenance,"detail":run.detail,"created_by":run.created_by,"created_at":run.created_at,"risk_authorized":False,"executable":False,"trading":"DISABLED"}
    if include_curve:value["equity_curve"]=run.equity_curve
    return value
