from datetime import UTC, date, datetime, timedelta

import httpx
from fastapi.testclient import TestClient

from app.auth import Principal, csrf_protected, current_principal
from app.data.calendar import market_session, sessions
from app.data.providers import AlphaVantageProvider, FredProvider, ProviderError, SecEdgarProvider
from app.data.quality import checksum, validate
from app.main import app

principal=Principal(username="test-operator",session_id="data-test",csrf_token="csrf")

def client_for(payload):
    def handler(request): return httpx.Response(200,json=payload,request=request)
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_alpha_vantage_normalizes_adjusted_daily_history():
    payload={"Time Series (Daily)":{"2026-08-17":{"1. open":"100","2. high":"104","3. low":"99","4. close":"103","5. adjusted close":"102.5","6. volume":"12345","7. dividend amount":"0.25","8. split coefficient":"1.0"}}}
    item=AlphaVantageProvider("fixture-key",client_for(payload)).historical_daily("AAPL")[0]
    assert item.data_type=="OHLCV" and item.payload["dividend"]==0.25 and item.payload["volume"]==12345

def test_official_fred_and_sec_normalization():
    fred=FredProvider("fixture-key",client_for({"observations":[{"date":"2026-08-01","value":"4.2"}]})).observations("UNRATE")
    assert fred[0].data_type=="ECONOMIC" and fred[0].payload["series_id"]=="UNRATE"
    sec=SecEdgarProvider("Aegis Alpha admin@pacificao.com",client_for({"cik":320193,"entityName":"Apple Inc.","facts":{}})).company_facts("320193")
    assert sec[0].data_type=="FUNDAMENTAL" and "CIK0000320193" in sec[0].external_id

def test_provider_credentials_fail_closed():
    for factory in (lambda:AlphaVantageProvider(""),lambda:SecEdgarProvider("Aegis Alpha")):
        try: factory(); assert False
        except ProviderError: pass

def test_quality_checks_and_deterministic_checksum():
    when=datetime.now(UTC)-timedelta(minutes=20); payload={"price":10.0}
    assert any(code=="STALE_QUOTE" for _,code,_ in validate("QUOTE",when,payload))
    invalid={"open":10.0,"high":9.0,"low":8.0,"close":11.0,"volume":-1}
    codes={code for _,code,_ in validate("OHLCV",datetime.now(UTC),invalid)}
    assert {"OHLC_RANGE","NEGATIVE_VOLUME"}.issubset(codes)
    assert checksum("QUOTE","A",when,payload)==checksum("QUOTE","A",when,{"price":10.0})

def test_market_calendar_handles_weekends_and_holidays():
    assert market_session(date(2026,7,3))["is_open"] is False
    assert market_session(date(2026,7,6))["is_open"] is True
    assert len(sessions(date(2026,8,17),date(2026,8,21)))==5

def test_phase3_data_routes_are_authenticated_and_safe():
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
            missing=client.post("/api/data/ingest",json={"provider":"alpha_vantage","dataset":"historical","symbol":"AAPL"},headers={"X-CSRF-Token":"csrf"})
            assert missing.status_code==503 and "not configured" in missing.json()["detail"]
            invalid=client.post("/api/data/ingest",json={"provider":"fred","dataset":"economic"},headers={"X-CSRF-Token":"csrf"})
            assert invalid.status_code==422
    finally:
        app.dependency_overrides.clear()
