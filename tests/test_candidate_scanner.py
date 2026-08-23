from datetime import UTC,datetime,timedelta
from uuid import uuid4
from sqlalchemy import select
from app.candidate_scanner import scan_batch
from app.config import Settings
from app.database import SessionLocal
from app.models import CandidateScanState,DataProvider,DataRecord,Instrument,StrategyDecision,StrategyScenario,StrategyVersion
from app.strategy_engine import canonical_checksum

def test_continuous_scanner_prioritizes_dividends_rotates_and_deduplicates():
    db=SessionLocal();now=datetime(2026,8,21,18,tzinfo=UTC);marker=uuid4().hex[:8].upper();symbols=[f"N{marker}",f"L{marker}",f"X{marker}"]
    try:
        provider=DataProvider(name=f"scanner-{marker}",provider_type="market_data",enabled=True,credential_status="NONE",base_url="https://example.test");scenario=StrategyScenario(name=f"Scanner {marker}",strategy_type="DIVIDEND_FARM",lifecycle="RESEARCH",parameters={});db.add_all([provider,scenario]);db.flush()
        spec={"schema_version":1,"name":"Scanner fixture","universe":{"symbols":symbols,"exclude_symbols":[],"asset_types":["EQUITY"]},"indicators":[],"entry_rules":[{"field":"event_yield_pct","operator":"gte","value":0.1,"reason":"YIELD"}],"exit_rules":[{"field":"recovered","operator":"eq","value":True,"reason":"RECOVERED"}],"filters":[{"field":"average_daily_volume","operator":"gte","value":100,"reason":"LIQUID"}],"position_sizing":{"method":"FIXED_PERCENT","max_position_pct":1,"max_strategy_allocation_pct":10,"cash_buffer_pct":10},"schedule":{"calendar":"NYSE","timezone":"America/New_York","frequency":"EVENT_DRIVEN","evaluation_time":"15:45"},"parameters":{}}
        version=StrategyVersion(scenario_id=scenario.id,version=1,specification=spec,checksum=canonical_checksum(spec),created_by="test");db.add(version);db.flush()
        for index,symbol in enumerate(symbols):
            instrument=Instrument(symbol=symbol,asset_type="EQUITY",active=True);db.add(instrument);db.flush()
            for offset in range(20):
                day=now-timedelta(days=19-offset);db.add(DataRecord(provider_id=provider.id,instrument_id=instrument.id,data_type="OHLCV",external_id=f"{symbol}:{offset}",event_time=day,interval="day",payload={"close":10,"volume":1000000},source_url="https://example.test",observed_at=now,quality_status="VALID",checksum=f"{marker}-{index}-{offset}"))
            if index<2:
                ex=now+timedelta(days=2 if index==0 else 10);db.add(DataRecord(provider_id=provider.id,instrument_id=instrument.id,data_type="CORPORATE_ACTION",external_id=f"{symbol}:dividend",event_time=ex,interval="event",payload={"action":"DIVIDEND","amount":0.1,"ex_dividend_date":ex.date().isoformat()},source_url="https://example.test",observed_at=now,quality_status="VALID",checksum=f"{marker}-div-{index}"))
                db.add(DataRecord(provider_id=provider.id,instrument_id=instrument.id,data_type="CORPORATE_ACTION",external_id=f"{symbol}:dividend:duplicate",event_time=ex,interval="event",payload={"action":"DIVIDEND","amount":0.1,"ex_dividend_date":ex.date().isoformat()},source_url="https://second.example.test",observed_at=now,quality_status="VALID",checksum=f"{marker}-div-duplicate-{index}"))
        db.commit();settings=Settings(candidate_scanner_enabled=True,candidate_scanner_batch_size=1,candidate_scanner_interval_seconds=300,candidate_scanner_max_price_age_days=7,broker_gateway_shared_secret="x"*32)
        first=scan_batch(db,settings,now);second=scan_batch(db,settings,now);third=scan_batch(db,settings,now);repeat=scan_batch(db,settings,now+timedelta(minutes=5))
        decisions=db.scalars(select(StrategyDecision).where(StrategyDecision.version_id==version.id).order_by(StrategyDecision.id)).all();states=db.scalars(select(CandidateScanState).where(CandidateScanState.version_id==version.id)).all()
        assert [row.symbol for row in decisions[:2]]==symbols[:2] and decisions[0].decision=="ENTRY"
        assert first["entries"]==1 and second["entries"]==1 and third["scanned"]==1 and repeat["decisions"]==0
        assert len(states)==3 and first["risk_authorized"] is False and first["executable"] is False and first["trading"]=="DISABLED"
    finally:db.close()
