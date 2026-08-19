from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import DataProvider, DataQualityIssue, DataRecord, IngestionRun, Instrument
from .providers import AlphaVantageProvider, FredProvider, NormalizedItem, ProviderError, SecEdgarProvider
from .quality import checksum, validate

PROVIDER_DATASETS={"alpha_vantage":{"historical","quote","fundamentals","dividends","news"},"fred":{"economic"},"sec_edgar":{"companyfacts"}}

def instrument(db: Session, symbol: str, cik: str | None = None) -> Instrument:
    normalized=symbol.strip().upper()
    value=db.scalar(select(Instrument).where(Instrument.symbol==normalized))
    if value is None:
        value=Instrument(symbol=normalized,cik=cik.zfill(10) if cik else None,metadata_json={})
        db.add(value); db.flush()
    elif cik and not value.cik:
        value.cik=cik.zfill(10)
    return value

def store(db: Session, provider: DataProvider, symbol: str | None, items: Iterable[NormalizedItem], cik: str | None = None) -> tuple[int,int]:
    target=instrument(db,symbol,cik) if symbol else None; accepted=0; rejected=0
    for item in items:
        observed=datetime.now(UTC); problems=validate(item.data_type,item.event_time,item.payload,observed)
        quality="REJECTED" if any(severity=="ERROR" for severity,_,_ in problems) else "WARNING" if problems else "VALID"
        record=DataRecord(provider_id=provider.id,instrument_id=target.id if target else None,data_type=item.data_type,external_id=item.external_id,event_time=item.event_time,interval=item.interval,payload=item.payload,source_url=item.source_url,observed_at=observed,quality_status=quality,checksum=checksum(item.data_type,item.external_id,item.event_time,item.payload))
        try:
            with db.begin_nested(): db.add(record); db.flush()
        except IntegrityError:
            continue
        for severity,code,detail in problems: db.add(DataQualityIssue(record_id=record.id,severity=severity,code=code,detail=detail))
        if quality=="REJECTED": rejected+=1
        else: accepted+=1
    return accepted,rejected

def provider_adapter(settings: Settings, name: str):
    if name=="alpha_vantage": return AlphaVantageProvider(settings.alpha_vantage_api_key)
    if name=="fred": return FredProvider(settings.fred_api_key)
    if name=="sec_edgar": return SecEdgarProvider(settings.sec_user_agent)
    raise ProviderError("Unknown data provider")

def fetch(adapter, dataset: str, symbol: str | None, series_id: str | None, cik: str | None):
    if dataset=="historical": return adapter.historical_daily(symbol)
    if dataset=="quote": return adapter.quote(symbol)
    if dataset=="fundamentals": return adapter.fundamentals(symbol)
    if dataset=="dividends": return adapter.dividends(symbol)
    if dataset=="news": return adapter.news(symbol or "")
    if dataset=="economic": return adapter.observations(series_id)
    if dataset=="companyfacts": return adapter.company_facts(cik)
    raise ProviderError("Unsupported provider dataset")

def ingest(db: Session, settings: Settings, name: str, dataset: str, symbol: str | None = None, series_id: str | None = None, cik: str | None = None) -> IngestionRun:
    if dataset not in PROVIDER_DATASETS.get(name,set()): raise ProviderError("Dataset is not supported by provider")
    provider=db.scalar(select(DataProvider).where(DataProvider.name==name))
    if provider is None: raise ProviderError("Provider is not initialized")
    run=IngestionRun(provider_id=provider.id,dataset=dataset,status="RUNNING",accepted=0,rejected=0,detail="")
    db.add(run); db.commit(); db.refresh(run)
    try:
        items=fetch(provider_adapter(settings,name),dataset,symbol,series_id,cik)
        accepted,rejected=store(db,provider,symbol,items,cik)
        run.status="COMPLETE"; run.accepted=accepted; run.rejected=rejected; run.detail=f"Accepted {accepted}; rejected {rejected}"
        provider.last_success_at=datetime.now(UTC); provider.last_error=""; provider.credential_status="CONFIGURED" if name=="alpha_vantage" else "NOT_REQUIRED"
    except Exception as exc:
        db.rollback(); run=db.get(IngestionRun,run.id); provider=db.get(DataProvider,provider.id)
        run.status="ERROR"; run.detail=str(exc)[:500]; provider.last_error=type(exc).__name__; provider.credential_status="WAITING_FOR_CREDENTIALS" if "key is not configured" in str(exc) else provider.credential_status
    run.completed_at=datetime.now(UTC); db.commit(); db.refresh(run)
    return run

def status(db: Session) -> dict:
    providers=db.scalars(select(DataProvider).order_by(DataProvider.name)).all()
    latest={}
    for provider in providers:
        run=db.scalar(select(IngestionRun).where(IngestionRun.provider_id==provider.id).order_by(IngestionRun.started_at.desc()).limit(1))
        latest[provider.name]={"enabled":provider.enabled,"credential_status":provider.credential_status,"last_success_at":provider.last_success_at,"last_error":provider.last_error,"latest_run":{"dataset":run.dataset,"status":run.status,"accepted":run.accepted,"rejected":run.rejected,"completed_at":run.completed_at} if run else None}
    record_count=db.scalar(select(func.count()).select_from(DataRecord)) or 0; issue_count=db.scalar(select(func.count()).select_from(DataQualityIssue)) or 0
    freshest=dict(db.execute(select(DataRecord.data_type,func.max(DataRecord.event_time)).group_by(DataRecord.data_type)).all())
    return {"providers":latest,"record_count":record_count,"quality_issue_count":issue_count,"freshest":freshest,"trading":"DISABLED"}
