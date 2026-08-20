"""Persistent, quota-aware, read-only market-data ingestion queue."""
from __future__ import annotations
from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..config import Settings
from ..models import DataProvider, IngestionJob, IngestionRun, Instrument
from .providers import AlphaVantageProvider, ProviderError
from .service import ingest, ingest_robinhood

SYMBOL_RE=re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,14}$")

def _key(provider:str,dataset:str,symbol:str|None,bucket:str,arguments:dict)->str:
    digest=hashlib.sha256(json.dumps(arguments,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:16]
    return f"{provider}:{dataset}:{symbol or 'GLOBAL'}:{bucket}:{digest}"[:255]

def enqueue(db:Session,provider:str,dataset:str,symbol:str|None,arguments:dict,priority:int,bucket:str,available_at:datetime|None=None)->IngestionJob|None:
    job=IngestionJob(provider=provider,dataset=dataset,symbol=symbol,arguments=arguments,priority=priority,status="QUEUED",available_at=available_at or datetime.now(UTC),dedupe_key=_key(provider,dataset,symbol,bucket,arguments))
    try:
        with db.begin_nested():db.add(job);db.flush()
    except IntegrityError:return None
    return job

def seed_control_jobs(db:Session,now:datetime|None=None)->int:
    now=now or datetime.now(UTC);day=now.date().isoformat();count=0
    if enqueue(db,"alpha_vantage","listing_status",None,{},1,day):count+=1
    if enqueue(db,"aegis","freshness_schedule",None,{},2,day):count+=1
    db.commit();return count

def _alpha_used_today(db:Session,now:datetime)->int:
    provider=db.scalar(select(DataProvider).where(DataProvider.name=="alpha_vantage"))
    if provider is None:return 0
    start=datetime(now.year,now.month,now.day,tzinfo=UTC)
    return int(db.scalar(select(func.count()).select_from(IngestionRun).where(IngestionRun.provider_id==provider.id,IngestionRun.started_at>=start)) or 0)

def _defer(job:IngestionJob,when:datetime,detail:str)->None:
    job.status="QUEUED";job.available_at=when;job.detail=detail[:500]

def _discover(db:Session,settings:Settings,now:datetime)->str:
    provider=db.scalar(select(DataProvider).where(DataProvider.name=="alpha_vantage"))
    if provider is None:raise ProviderError("Alpha Vantage provider is not initialized")
    run=IngestionRun(provider_id=provider.id,dataset="listing_status",status="RUNNING",accepted=0,rejected=0,detail="")
    db.add(run);db.commit();db.refresh(run)
    try:
        rows=AlphaVantageProvider(settings.alpha_vantage_api_key).active_listings();queued=0
        for row in rows:
            symbol=(row.get("symbol") or "").strip().upper();asset=(row.get("assetType") or row.get("asset_type") or "").strip()
            if not SYMBOL_RE.fullmatch(symbol) or asset.lower() not in {"stock","etf"}:continue
            item=db.scalar(select(Instrument).where(Instrument.symbol==symbol))
            metadata={"listing_source":"alpha_vantage","listing_status":"ACTIVE","ipo_date":row.get("ipoDate") or row.get("ipo_date"),"delisting_date":row.get("delistingDate") or row.get("delisting_date")}
            if item is None:
                item=Instrument(symbol=symbol,name=(row.get("name") or "")[:255],asset_type="ETF" if asset.lower()=="etf" else "EQUITY",exchange=(row.get("exchange") or "")[:30],active=False,metadata_json=metadata);db.add(item)
            else:
                item.name=(row.get("name") or item.name)[:255];item.asset_type="ETF" if asset.lower()=="etf" else "EQUITY";item.exchange=(row.get("exchange") or item.exchange)[:30];item.metadata_json={**(item.metadata_json or {}),**metadata}
            if enqueue(db,"robinhood","get_equity_quotes",symbol,{"symbols":[symbol]},5,"initial-validation"):queued+=1
        run.status="COMPLETE";run.accepted=queued;run.completed_at=now;run.detail=f"Discovered {len(rows)} active listings; queued {queued} Robinhood validations";provider.last_success_at=now;provider.last_error="";db.commit();return run.detail
    except Exception as exc:
        db.rollback();run=db.get(IngestionRun,run.id);provider=db.get(DataProvider,provider.id);run.status="ERROR";run.detail=type(exc).__name__;run.completed_at=now;provider.last_error=type(exc).__name__;db.commit();raise

def _expand_validated(db:Session,symbol:str,now:datetime)->int:
    item=db.scalar(select(Instrument).where(Instrument.symbol==symbol))
    if item:item.active=True;item.metadata_json={**(item.metadata_json or {}),"robinhood_market_data_validated_at":now.isoformat()}
    jobs=[("get_equity_historicals",{"symbols":[symbol],"start_time":"2016-01-01T00:00:00Z","interval":"day","bounds":"regular","adjustment_type":"split"},10),("get_equity_fundamentals",{"symbols":[symbol]},20),("get_earnings_results",{"symbol":symbol},20),("get_financials",{"symbols":[symbol],"period":"quarterly","limit":40},25),("get_option_chains",{"underlying_symbol":symbol},40)]
    count=0
    for dataset,args,priority in jobs:
        if enqueue(db,"robinhood",dataset,symbol,args,priority,"initial-core"):count+=1
    for dataset,priority in (("dividends",60),("fundamentals",70),("news",90)):
        if enqueue(db,"alpha_vantage",dataset,symbol,{},priority,"initial-independent"):count+=1
    return count

def schedule_freshness(db:Session,now:datetime)->int:
    day=now.date().isoformat();iso=now.isocalendar();week=f"{iso.year}-W{iso.week:02d}";month=day[:7];count=0
    symbols=db.scalars(select(Instrument.symbol).where(Instrument.active.is_(True),Instrument.symbol.not_like("%,%"))).all()
    for symbol in symbols:
        jobs=[("robinhood","get_equity_quotes",{"symbols":[symbol]},5,day),("robinhood","get_equity_historicals",{"symbols":[symbol],"start_time":"2016-01-01T00:00:00Z","interval":"day","bounds":"regular","adjustment_type":"split"},10,week),("robinhood","get_earnings_results",{"symbol":symbol},20,week),("robinhood","get_equity_fundamentals",{"symbols":[symbol]},25,week),("robinhood","get_financials",{"symbols":[symbol],"period":"quarterly","limit":40},30,month),("robinhood","get_option_chains",{"underlying_symbol":symbol},45,week),("alpha_vantage","dividends",{},60,month),("alpha_vantage","fundamentals",{},70,month)]
        for provider,dataset,args,priority,bucket in jobs:
            if enqueue(db,provider,dataset,symbol,args,priority,bucket):count+=1
    db.commit();return count

def process_one(db:Session,settings:Settings,job:IngestionJob,now:datetime|None=None)->str:
    now=now or datetime.now(UTC)
    if job.provider=="alpha_vantage" and _alpha_used_today(db,now)>=settings.alpha_vantage_daily_limit:
        tomorrow=datetime(now.year,now.month,now.day,tzinfo=UTC)+timedelta(days=1,minutes=5);_defer(job,tomorrow,"Deferred by Alpha Vantage daily quota");db.commit();return "DEFERRED_QUOTA"
    job.status="RUNNING";job.started_at=now;job.attempts+=1;db.commit()
    try:
        if job.provider=="aegis" and job.dataset=="freshness_schedule":detail=f"Queued {schedule_freshness(db,now)} due freshness jobs"
        elif job.provider=="alpha_vantage" and job.dataset=="listing_status":detail=_discover(db,settings,now)
        elif job.provider=="alpha_vantage":
            run=ingest(db,settings,"alpha_vantage",job.dataset,job.symbol);detail=run.detail
            if run.status!="COMPLETE":raise ProviderError(detail)
        elif job.provider=="robinhood":
            run=ingest_robinhood(db,settings,job.dataset,job.arguments,job.symbol);detail=run.detail
            if run.status!="COMPLETE":raise ProviderError(detail)
            if job.dataset=="get_equity_quotes" and job.symbol:_expand_validated(db,job.symbol,now)
        else:raise ProviderError("Unsupported queued provider")
        job=db.get(IngestionJob,job.id);job.status="COMPLETE";job.detail=detail[:500];job.completed_at=datetime.now(UTC);db.commit();return "COMPLETE"
    except Exception as exc:
        db.rollback();job=db.get(IngestionJob,job.id);delay=min(1440,2**min(job.attempts,10));job.detail=type(exc).__name__;job.status="FAILED" if job.attempts>=job.max_attempts else "QUEUED";job.available_at=now+timedelta(minutes=delay);job.completed_at=now if job.status=="FAILED" else None;db.commit();return job.status

def run_batch(db:Session,settings:Settings,limit:int|None=None)->dict:
    now=datetime.now(UTC);seed_control_jobs(db,now);
    for stale in db.scalars(select(IngestionJob).where(IngestionJob.status=="RUNNING",IngestionJob.started_at<now-timedelta(minutes=15))).all():stale.status="QUEUED";stale.available_at=now;stale.detail="Recovered after interrupted worker"
    db.commit();limit=limit or settings.ingestion_worker_batch_size
    jobs=db.scalars(select(IngestionJob).where(IngestionJob.status=="QUEUED",IngestionJob.available_at<=now).order_by(IngestionJob.priority,IngestionJob.id).limit(limit)).all();results={"COMPLETE":0,"QUEUED":0,"FAILED":0,"DEFERRED_QUOTA":0}
    for job in jobs:results[process_one(db,settings,job,now)]+=1
    results["processed"]=len(jobs);return results

def queue_status(db:Session)->dict:
    counts=dict(db.execute(select(IngestionJob.status,func.count()).group_by(IngestionJob.status)).all());providers=dict(db.execute(select(IngestionJob.provider,func.count()).where(IngestionJob.status=="QUEUED").group_by(IngestionJob.provider)).all());validated=int(db.scalar(select(func.count()).select_from(Instrument).where(Instrument.active.is_(True))) or 0);catalog=int(db.scalar(select(func.count()).select_from(Instrument)) or 0)
    next_job=db.scalar(select(func.min(IngestionJob.available_at)).where(IngestionJob.status=="QUEUED"))
    return {"counts":counts,"queued_by_provider":providers,"catalog_instruments":catalog,"active_validated_instruments":validated,"pending_robinhood_validation":max(catalog-validated,0),"next_job_at":next_job,"trading":"DISABLED"}
