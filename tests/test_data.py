from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from sqlalchemy import select

import httpx
from fastapi.testclient import TestClient

from app.auth import Principal, csrf_protected, current_principal
from app.data.calendar import calendar_entry_gate, dividend_entry_plan, market_session, next_sessions, sessions
from app.schemas import RobinhoodDataIngestRequest
from app.data.providers import AlpacaDataProvider, AlphaVantageProvider, FredProvider, ProviderError, SecEdgarProvider
from app.data.quality import checksum, validate
from app.data.service import _safe_error, ingest_robinhood
from app.config import Settings
from app.database import SessionLocal
from app.gateway import BrokerGatewayClient
from app.models import DataRecord
from app.main import app
from app import main as main_module

principal=Principal(username="test-operator",session_id="data-test",csrf_token="csrf")

def client_for(payload):
    def handler(request): return httpx.Response(200,json=payload,request=request)
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_alpaca_normalizes_dividends_and_daily_bars():
    actions={"corporate_actions":{"cash_dividends":[{"id":"ca-1","symbol":"SPY","ex_date":"2026-06-20","process_date":"2026-06-20","rate":1.25,"special":False,"foreign":False}]},"next_page_token":None}
    item=AlpacaDataProvider("key","secret",client=client_for(actions)).dividends("SPY")[0]
    assert item.data_type=="CORPORATE_ACTION" and item.payload["amount"]==1.25 and item.payload["source_provider"]=="ALPACA"
    bars={"bars":[{"t":"2026-08-17T04:00:00Z","o":100,"h":104,"l":99,"c":103,"v":12345,"n":100,"vw":102.5}],"next_page_token":None}
    bar=AlpacaDataProvider("key","secret",client=client_for(bars)).historical_daily("SPY")[0]
    assert bar.data_type=="OHLCV" and bar.payload["close"]==103 and bar.payload["vwap"]==102.5

def test_alpha_vantage_normalizes_daily_history():
    payload={"Time Series (Daily)":{"2026-08-17":{"1. open":"100","2. high":"104","3. low":"99","4. close":"103","5. volume":"12345"}}}
    item=AlphaVantageProvider("fixture-key",client_for(payload)).historical_daily("AAPL")[0]
    assert item.data_type=="OHLCV" and item.payload["close"]==103 and item.payload["volume"]==12345

def test_alpha_vantage_news_uses_publisher_article_url():
    payload={"feed":[{"title":"Market report","url":"https://publisher.example/article","time_published":"20260820T120000"}]}
    item=AlphaVantageProvider("fixture-key",client_for(payload)).news("AAPL")[0]
    assert item.source_url=="https://publisher.example/article" and "apikey" not in item.source_url

def test_robinhood_fundamentals_create_dividend_event(monkeypatch):
    symbol="D"+uuid4().hex[:7].upper();ex_date="2026-09-01"
    response={"data":{"data":{"results":[{"symbol":symbol,"dividend_yield":"2.5","dividend_per_share":"0.25","distribution_frequency":"Quarterly","payable_date":"2026-09-15","ex_dividend_date":ex_date,"record_date":"2026-09-01"}]}}}
    monkeypatch.setattr(BrokerGatewayClient,"market_data",lambda self,tool,arguments:response)
    db=SessionLocal()
    try:
        run=ingest_robinhood(db,Settings(),"get_equity_fundamentals",{"symbols":[symbol]},symbol)
        record=db.scalar(select(DataRecord).where(DataRecord.external_id==f"{symbol}:robinhood:dividend:{ex_date}"))
        assert run.status=="COMPLETE" and record is not None and record.payload["source_provider"]=="ROBINHOOD"
    finally:db.close()

def test_official_fred_and_sec_normalization():
    fred=FredProvider("fixture-key",client_for({"observations":[{"date":"2026-08-01","value":"4.2"}]})).observations("UNRATE")
    assert fred[0].data_type=="ECONOMIC" and fred[0].payload["series_id"]=="UNRATE"
    sec=SecEdgarProvider("Aegis Alpha admin@pacificao.com",client_for({"cik":320193,"entityName":"Apple Inc.","facts":{}})).company_facts("320193")
    assert sec[0].data_type=="FUNDAMENTAL" and "CIK0000320193" in sec[0].external_id

def test_provider_credentials_fail_closed():
    for factory in (lambda:AlpacaDataProvider("",""),lambda:AlphaVantageProvider(""),lambda:SecEdgarProvider("Aegis Alpha")):
        try: factory(); assert False
        except ProviderError: pass

def test_provider_errors_redact_credentials():
    message="API key as SUPERSECRET123 and https://example.test/?apikey=SECONDSECRET"
    safe=_safe_error(ProviderError(message))
    assert "SUPERSECRET123" not in safe and "SECONDSECRET" not in safe
    assert safe.count("<redacted>")==2

def test_quality_checks_and_deterministic_checksum():
    when=datetime.now(UTC)-timedelta(minutes=20); payload={"price":10.0}
    assert any(code=="STALE_QUOTE" for _,code,_ in validate("QUOTE",when,payload))
    invalid={"open":10.0,"high":9.0,"low":8.0,"close":11.0,"volume":-1}
    codes={code for _,code,_ in validate("OHLCV",datetime.now(UTC),invalid)}
    assert {"OHLC_RANGE","NEGATIVE_VOLUME"}.issubset(codes)
    assert checksum("QUOTE","A",when,payload)==checksum("QUOTE","A",when,{"price":10.0})
    future=datetime.now(UTC)+timedelta(days=10)
    assert not any(code=="FUTURE_TIMESTAMP" for _,code,_ in validate("CORPORATE_ACTION",future,{"action":"DIVIDEND"}))

def test_market_calendar_handles_weekends_and_holidays():
    assert market_session(date(2026,7,3))["is_open"] is False
    assert market_session(date(2026,7,6))["is_open"] is True
    assert len(sessions(date(2026,8,17),date(2026,8,21)))==5
    upcoming=next_sessions(10,date(2026,8,17));assert len(upcoming)==10 and all(row["is_open"] for row in upcoming)

def test_dividend_entry_uses_prior_trading_session_and_fails_closed():
    monday=date(2026,8,31)
    assert dividend_entry_plan(monday)["planned_entry_date"]=="2026-08-28"
    assert dividend_entry_plan(date(2026,7,6))["planned_entry_date"]=="2026-07-02"
    assert dividend_entry_plan(monday,exceptional_closures={date(2026,8,28)})["planned_entry_date"]=="2026-08-27"
    assert calendar_entry_gate(date(2026,8,28),date(2026,8,28),True,False)=="BLOCKED_TRADING_DISABLED"
    assert calendar_entry_gate(date(2026,8,28),date(2026,8,28),False,True)=="BLOCKED_MARKET_OPEN_UNCONFIRMED"
    assert calendar_entry_gate(date(2026,8,28),date(2026,8,28),True,True)=="CALENDAR_ELIGIBLE_RISK_REVIEW_REQUIRED"

def test_phase3_data_routes_are_authenticated_and_safe(monkeypatch):
    monkeypatch.setattr(main_module.settings,"alpha_vantage_api_key","")
    with TestClient(app) as client:
        for route in ("/api/data/status","/api/data/records","/api/data/calendar?start=2026-08-17&end=2026-08-21"): assert client.get(route).status_code==401
    app.dependency_overrides[current_principal]=lambda:principal
    app.dependency_overrides[csrf_protected]=lambda:principal
    try:
        with TestClient(app) as client:
            calendar=client.get("/api/data/calendar?start=2026-08-17&end=2026-08-21")
            assert calendar.status_code==200 and len(calendar.json())==5
            status=client.get("/api/data/status")
            assert status.status_code==200 and status.json()["trading"]=="DISABLED"
            queue=client.get("/api/data/queue")
            assert queue.status_code==200 and queue.json()["trading"]=="DISABLED"
            dividends=client.get("/api/data/dividend-calendar?trading_days=10")
            assert dividends.status_code==200 and len(dividends.json()["sessions"])==10 and dividends.json()["primary_provider"]=="ROBINHOOD"
            assert dividends.json()["coverage"]["status"] in {"BACKFILLING","COMPLETE"}
            missing=client.post("/api/data/ingest",json={"provider":"alpha_vantage","dataset":"historical","symbol":"AAPL"},headers={"X-CSRF-Token":"csrf"})
            assert missing.status_code==503 and "not configured" in missing.json()["detail"]
            invalid=client.post("/api/data/ingest",json={"provider":"fred","dataset":"economic"},headers={"X-CSRF-Token":"csrf"})
            assert invalid.status_code==422
    finally:
        app.dependency_overrides.clear()


def test_robinhood_market_data_request_is_fail_closed():
    valid=RobinhoodDataIngestRequest(tool="get_equity_quotes",symbol="SPY",arguments={"symbols":["SPY"]})
    assert valid.tool=="get_equity_quotes"
    for payload in (
        {"tool":"place_equity_order","arguments":{}},
        {"tool":"get_equity_quotes","arguments":{"token":"prohibited"}},
    ):
        try: RobinhoodDataIngestRequest(**payload); assert False
        except ValueError: pass


def test_actionable_session_rolls_forward_after_close():
    from app.data.calendar import EASTERN, actionable_session_start
    assert actionable_session_start(datetime(2026,8,24,15,59,tzinfo=EASTERN))==date(2026,8,24)
    assert actionable_session_start(datetime(2026,8,24,16,0,tzinfo=EASTERN))==date(2026,8,25)
    assert actionable_session_start(datetime(2026,8,28,16,1,tzinfo=EASTERN))==date(2026,8,31)
