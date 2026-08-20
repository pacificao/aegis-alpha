from datetime import UTC,datetime
from uuid import uuid4
import httpx
from sqlalchemy import select
from app.config import Settings
from app.data.providers import AlphaVantageProvider
from app.data.queue import enqueue,process_one,queue_status,schedule_freshness
from app.database import SessionLocal
from app.models import DataProvider,IngestionJob,IngestionRun,Instrument

def test_active_listing_csv_is_parsed():
    csv="symbol,name,exchange,assetType,ipoDate,delistingDate,status\nAAPL,Apple Inc,NASDAQ,Stock,1980-12-12,null,Active\nSPY,SPDR S&P 500,NYSE ARCA,ETF,1993-01-22,null,Active\n"
    def handler(request):return httpx.Response(200,text=csv,request=request)
    rows=AlphaVantageProvider("fixture",httpx.Client(transport=httpx.MockTransport(handler))).active_listings()
    assert [row["symbol"] for row in rows]==["AAPL","SPY"]

def test_queue_is_idempotent_and_never_enables_trading():
    db=SessionLocal();symbol="Q"+uuid4().hex[:8].upper()
    try:
        first=enqueue(db,"robinhood","get_equity_quotes",symbol,{"symbols":[symbol]},5,"test");second=enqueue(db,"robinhood","get_equity_quotes",symbol,{"symbols":[symbol]},5,"test");db.commit()
        assert first is not None and second is None
        status=queue_status(db);assert status["trading"]=="DISABLED" and status["counts"]["QUEUED"]>=1
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

def test_freshness_schedule_is_tiered_and_deduplicated():
    db=SessionLocal();symbol="Q"+uuid4().hex[:8].upper();now=datetime.now(UTC)
    try:
        db.add(Instrument(symbol=symbol,active=True,metadata_json={"robinhood_market_data_validated_at":now.isoformat()}));db.commit();created=schedule_freshness(db,now);again=schedule_freshness(db,now)
        jobs=db.scalars(select(IngestionJob).where(IngestionJob.symbol==symbol)).all()
        assert created>=8 and again==0 and {j.provider for j in jobs}=={"robinhood","alpha_vantage"} and "get_equity_historicals" in {j.dataset for j in jobs}
    finally:db.close()
