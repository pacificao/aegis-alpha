from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import DataProvider, DataQualityIssue, DataRecord, IngestionRun, Instrument
from .providers import AlpacaDataProvider, AlphaVantageProvider, FredProvider, NormalizedItem, ProviderError, SecEdgarProvider, utc
from .quality import checksum, validate

def _safe_error(exc:Exception)->str:
    text=str(exc)
    patterns=(r"(?i)(api[ _-]?key(?:\s+as)?\s*[:=]?\s*)[A-Za-z0-9._-]+",r"(?i)((?:password|secret|token|authorization)\s*[:=]\s*)[^\s,;]+",r"(?i)([?&](?:apikey|api_key|token)=)[^&\s]+")
    for pattern in patterns:text=re.sub(pattern,r"\1<redacted>",text)
    return text[:500]

PROVIDER_DATASETS={"alpaca":{"historical","dividends"},"alpha_vantage":{"historical","quote","fundamentals","dividends","news"},"fred":{"economic"},"sec_edgar":{"companyfacts"}}

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
    if name=="alpaca":
        if not settings.alpaca_data_enabled:raise ProviderError("Alpaca data provider is disabled")
        return AlpacaDataProvider(settings.alpaca_api_key_id,settings.alpaca_api_secret_key,settings.alpaca_data_feed)
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
        run.status="ERROR"; run.detail=_safe_error(exc); provider.last_error=type(exc).__name__; provider.credential_status="WAITING_FOR_CREDENTIALS" if "key is not configured" in str(exc) else provider.credential_status
    run.completed_at=datetime.now(UTC); db.commit(); db.refresh(run)
    return run

ROBINHOOD_TYPES={
    "get_equity_historicals":"BROKER_OHLCV", "get_equity_fundamentals":"BROKER_FUNDAMENTAL",
    "get_financials":"BROKER_FINANCIAL", "get_equity_price_book":"BROKER_ORDER_BOOK",
    "get_equity_technical_indicators":"BROKER_TECHNICAL", "get_earnings_results":"BROKER_EARNINGS",
    "get_earnings_calendar":"BROKER_EARNINGS", "get_indexes":"BROKER_INDEX",
    "get_index_quotes":"BROKER_INDEX_QUOTE", "get_equity_quotes":"BROKER_QUOTE",
    "get_equity_tradability":"BROKER_REFERENCE", "get_option_historicals":"BROKER_OPTION",
    "get_option_chains":"BROKER_OPTION", "get_option_instruments":"BROKER_OPTION",
    "get_option_quotes":"BROKER_OPTION_QUOTE", "get_currency_pairs":"BROKER_CRYPTO_REFERENCE",
    "get_crypto_quotes":"BROKER_CRYPTO_QUOTE",
}

def ingest_robinhood(db: Session, settings: Settings, tool: str, arguments: dict, symbol: str | None = None) -> IngestionRun:
    from ..gateway import BrokerGatewayClient
    if tool not in ROBINHOOD_TYPES: raise ProviderError("Robinhood tool is not an approved market-data read")
    provider=db.scalar(select(DataProvider).where(DataProvider.name=="robinhood"))
    if provider is None: raise ProviderError("Robinhood data provider is not initialized")
    run=IngestionRun(provider_id=provider.id,dataset=tool,status="RUNNING",accepted=0,rejected=0,detail="")
    db.add(run); db.commit(); db.refresh(run)
    try:
        response=BrokerGatewayClient(settings).market_data(tool,arguments)
        if response.get("status")=="ERROR" or "data" not in response: raise ProviderError("Robinhood market-data gateway is unavailable")
        observed=datetime.now(UTC)
        target=symbol or "GLOBAL"
        items=[NormalizedItem(ROBINHOOD_TYPES[tool],f"{tool}:{target}:{observed.isoformat()}",observed,"snapshot",{"tool":tool,"arguments":arguments,"result":response["data"]},"https://agent.robinhood.com/mcp/trading")]
        if tool=="get_equity_fundamentals" and symbol:
            outer=response["data"];inner=outer.get("data",outer) if isinstance(outer,dict) else {};rows=inner.get("results",[]) if isinstance(inner,dict) else []
            for row in rows:
                ex_date=row.get("ex_dividend_date") if isinstance(row,dict) else None
                if str(row.get("symbol","")).upper()!=symbol.upper() or not ex_date:continue
                payload={"action":"DIVIDEND","amount":row.get("dividend_per_share"),"dividend_per_share":row.get("dividend_per_share"),"annual_yield_pct":row.get("dividend_yield"),"payment_frequency":row.get("distribution_frequency"),"ex_dividend_date":ex_date,"record_date":row.get("record_date"),"payment_date":row.get("payable_date"),"source_provider":"ROBINHOOD","coverage":"CURRENT_SCHEDULE"}
                items.append(NormalizedItem("CORPORATE_ACTION",f"{symbol}:robinhood:dividend:{ex_date}",utc(ex_date),"event",payload,"https://agent.robinhood.com/mcp/trading"))
        accepted,rejected=store(db,provider,symbol,items)
        run.status="COMPLETE"; run.accepted=accepted; run.rejected=rejected; run.detail=f"Accepted {accepted}; rejected {rejected}"
        provider.last_success_at=observed; provider.last_error=""; provider.credential_status="CONFIGURED"
    except Exception as exc:
        db.rollback(); run=db.get(IngestionRun,run.id); provider=db.get(DataProvider,provider.id)
        run.status="ERROR"; run.detail=_safe_error(exc); provider.last_error=type(exc).__name__
    run.completed_at=datetime.now(UTC); db.commit(); db.refresh(run); return run

def status(db: Session) -> dict:
    providers=db.scalars(select(DataProvider).order_by(DataProvider.name)).all()
    latest={}
    for provider in providers:
        run=db.scalar(select(IngestionRun).where(IngestionRun.provider_id==provider.id).order_by(IngestionRun.started_at.desc()).limit(1))
        latest[provider.name]={"enabled":provider.enabled,"credential_status":provider.credential_status,"last_success_at":provider.last_success_at,"last_error":provider.last_error,"latest_run":{"dataset":run.dataset,"status":run.status,"accepted":run.accepted,"rejected":run.rejected,"completed_at":run.completed_at} if run else None}
    record_count=db.scalar(select(func.count()).select_from(DataRecord)) or 0
    # Show actionable findings while preserving resolved findings as immutable audit history.
    issue_count=db.scalar(select(func.count()).select_from(DataQualityIssue).where(DataQualityIssue.severity!="RESOLVED")) or 0
    resolved_issue_count=db.scalar(select(func.count()).select_from(DataQualityIssue).where(DataQualityIssue.severity=="RESOLVED")) or 0
    freshest=dict(db.execute(select(DataRecord.data_type,func.max(DataRecord.event_time)).group_by(DataRecord.data_type)).all())
    return {"providers":latest,"record_count":record_count,"quality_issue_count":issue_count,"resolved_quality_issue_count":resolved_issue_count,"freshest":freshest,"trading":"DISABLED"}
