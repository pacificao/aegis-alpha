from datetime import UTC,datetime,timedelta
from uuid import uuid4
import httpx
from sqlalchemy import select
from app.config import Settings
from app.data.providers import AlphaVantageProvider,NasdaqTraderProvider
from app.data.queue import _select_batch_jobs,_symbols,enqueue,process_one,queue_status,schedule_freshness
from app.database import SessionLocal
from app.models import DataProvider,DataRecord,IngestionJob,IngestionRun,Instrument

def test_active_listing_csv_is_parsed():
    csv="symbol,name,exchange,assetType,ipoDate,delistingDate,status\nAAPL,Apple Inc,NASDAQ,Stock,1980-12-12,null,Active\nSPY,SPDR S&P 500,NYSE ARCA,ETF,1993-01-22,null,Active\n"
    def handler(request):return httpx.Response(200,text=csv,request=request)
    rows=AlphaVantageProvider("fixture",httpx.Client(transport=httpx.MockTransport(handler))).active_listings()
    assert [row["symbol"] for row in rows]==["AAPL","SPY"]

def test_official_exchange_directory_includes_strategy_neutral_security_types():
    nasdaq="Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\nQQQ|Invesco QQQ ETF|Q|N|N|100|Y|N\nTEST|Test Issue|Q|Y|N|100|N|N\nFile Creation Time: 0820202621:00|||||||\n"
    other="ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\nABC|Example Corp Common Stock|N|ABC|N|100|N|ABC\nABCP|Example Corp Preferred Stock|N|ABCP|N|100|N|ABCP\nABCW|Example Corp Warrant|N|ABCW|N|100|N|ABCW\n"
    def handler(request):return httpx.Response(200,text=nasdaq if "nasdaqlisted" in str(request.url) else other,request=request)
    rows=NasdaqTraderProvider(httpx.Client(transport=httpx.MockTransport(handler))).directory();types={row["symbol"]:row["asset_type"] for row in rows}
    assert types=={"QQQ":"ETF","ABC":"EQUITY","ABCP":"PREFERRED","ABCW":"WARRANT"}

def test_robinhood_calendar_symbol_discovery_is_bounded():
    payload={"data":{"results":[{"symbol":"AAPL"},{"symbol":"BRK.B"},{"symbol":"bad symbol"}]},"guide":"not a ticker"}
    assert _symbols(payload)=={"AAPL","BRK.B"}

def test_queue_is_idempotent_and_never_enables_trading():
    db=SessionLocal();symbol="Q"+uuid4().hex[:8].upper()
    try:
        first=enqueue(db,"robinhood","get_equity_quotes",symbol,{"symbols":[symbol]},5,"test");second=enqueue(db,"robinhood","get_equity_quotes",symbol,{"symbols":[symbol]},5,"test");db.commit()
        assert first is not None and second is None
        status=queue_status(db);assert status["trading"]=="DISABLED" and status["counts"]["QUEUED"]>=1
        assert status["catalog_instruments"]>=status["active_validated_instruments"] and "next_job_at" in status
    finally:db.close()

def test_alpha_quota_defers_without_calling_provider():
    db=SessionLocal();symbol="Q"+uuid4().hex[:8].upper();now=datetime.now(UTC)
    try:
        provider=db.scalar(select(DataProvider).where(DataProvider.name=="alpha_vantage"))
        if provider is None:
            provider=DataProvider(name="alpha_vantage",provider_type="market_data",enabled=True,credential_status="CONFIGURED",base_url="https://www.alphavantage.co");db.add(provider);db.flush()
        for _ in range(2):db.add(IngestionRun(provider_id=provider.id,dataset="fixture",status="COMPLETE",accepted=0,rejected=0,detail=""))
        job=enqueue(db,"alpha_vantage","news",symbol,{},90,"quota-test");db.commit();settings=Settings(alpha_vantage_daily_limit=1,broker_gateway_shared_secret="x"*32)
        assert process_one(db,settings,job,now)=="DEFERRED_QUOTA" and db.get(IngestionJob,job.id).status=="QUEUED"
    finally:db.close()

def test_batch_selection_finishes_active_ticker_cohorts_without_starving_validation():
    db=SessionLocal();now=datetime.now(UTC);prefix="C"+uuid4().hex[:5].upper()
    try:
        for index in range(30):
            symbol=f"{prefix}{index:02d}";db.add(Instrument(symbol=symbol,active=True));db.flush()
            enqueue(db,"alpaca","dividends",symbol,{},3,"cohort");enqueue(db,"alpaca","historical",symbol,{},12,"cohort")
        pending=f"{prefix}X";db.add(Instrument(symbol=pending,active=False));db.flush();enqueue(db,"robinhood","get_equity_quotes",pending,{"symbols":[pending]},5,"validation");db.commit()
        jobs=_select_batch_jobs(db,now+timedelta(seconds=1),10,cohort_size=25)
        assert len(jobs)==10 and any(job.symbol==pending for job in jobs)
        active=[job for job in jobs if job.symbol and job.symbol.startswith(prefix) and job.symbol!=pending]
        assert len(active)>=2 and len({job.symbol for job in active})<len(active)
    finally:db.close()

def test_batch_selection_prioritizes_nearest_upcoming_ex_dividend_date():
    db=SessionLocal();now=datetime.now(UTC);prefix="D"+uuid4().hex[:5].upper()
    try:
        provider=DataProvider(name=f"fixture-{prefix}",provider_type="market_data",enabled=True,credential_status="NONE",base_url="https://example.test");db.add(provider);db.flush()
        symbols=[f"{prefix}L",f"{prefix}N",f"{prefix}X"]
        for symbol in symbols:
            item=Instrument(symbol=symbol,active=True);db.add(item);db.flush();enqueue(db,"alpaca","historical",symbol,{},12,"dividend-priority")
            if symbol!=symbols[2]:
                ex_date=now+timedelta(days=10 if symbol==symbols[0] else 2)
                db.add(DataRecord(provider_id=provider.id,instrument_id=item.id,data_type="CORPORATE_ACTION",external_id=f"{symbol}:dividend",event_time=ex_date,interval="event",payload={"action":"DIVIDEND","ex_dividend_date":ex_date.date().isoformat()},source_url="https://example.test",observed_at=now,quality_status="VALID",checksum=f"{prefix}-{symbol}"))
        db.commit();jobs=_select_batch_jobs(db,now+timedelta(seconds=1),10,cohort_size=25);ordered=[job.symbol for job in jobs]
        assert symbols[1] in ordered and symbols[0] in ordered and ordered.index(symbols[1])<ordered.index(symbols[0])
    finally:db.close()

def test_freshness_schedule_is_tiered_and_deduplicated():
    db=SessionLocal();symbol="Q"+uuid4().hex[:8].upper();now=datetime.now(UTC)
    try:
        db.add(Instrument(symbol=symbol,active=True,metadata_json={"robinhood_market_data_validated_at":now.isoformat()}));db.commit();created=schedule_freshness(db,now,Settings(alpaca_data_enabled=False));again=schedule_freshness(db,now,Settings(alpaca_data_enabled=False))
        jobs=db.scalars(select(IngestionJob).where(IngestionJob.symbol==symbol)).all()
        assert created>=8 and again==0 and {j.provider for j in jobs}=={"robinhood","alpha_vantage"} and "get_equity_historicals" in {j.dataset for j in jobs}
    finally:db.close()
