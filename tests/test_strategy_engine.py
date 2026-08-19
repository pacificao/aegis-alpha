from datetime import UTC, datetime
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import Principal, csrf_protected, current_principal
from app.main import app
from app.strategy_engine import canonical_checksum, evaluate

principal=Principal(username="test-operator",session_id="session",csrf_token="csrf")
SPEC={
 "schema_version":1,"name":"Dividend Farm Research","universe":{"symbols":["AAPL"],"exclude_symbols":[],"asset_types":["EQUITY"]},
 "indicators":[{"name":"event_yield_pct","kind":"EVENT_YIELD","source":"dividend_per_share"}],
 "entry_rules":[{"field":"event_yield_pct","operator":"gte","value":0.25,"reason":"EVENT_YIELD_ELIGIBLE"}],
 "exit_rules":[{"field":"recovered","operator":"eq","value":True,"reason":"PRICE_RECOVERED"}],
 "filters":[{"field":"earnings_excluded","operator":"eq","value":False,"reason":"EARNINGS_WINDOW_CLEAR"}],
 "position_sizing":{"method":"FIXED_PERCENT","max_position_pct":1.0,"max_strategy_allocation_pct":25.0,"cash_buffer_pct":10.0},
 "schedule":{"calendar":"NYSE","timezone":"America/New_York","frequency":"EVENT_DRIVEN","evaluation_time":"15:45"},
 "parameters":{"max_holding_days":90}
}

def test_deterministic_engine_boundaries():
    facts={"event_yield_pct":0.4,"recovered":False,"earnings_excluded":False}
    first=evaluate(SPEC,"aapl",facts,datetime(2026,8,18,tzinfo=UTC)); second=evaluate(SPEC,"AAPL",facts,datetime(2026,8,18,tzinfo=UTC))
    assert first==second
    assert first["decision"]=="ENTRY" and first["proposed_weight_pct"]==1.0
    assert first["risk_authorized"] is False and first["executable"] is False and first["trading"]=="DISABLED"
    assert evaluate(SPEC,"MSFT",facts)["decision"]=="EXCLUDE"
    assert evaluate(SPEC,"AAPL",{**facts,"recovered":True})["decision"]=="EXIT"
    assert len(canonical_checksum(SPEC))==64


def test_versioning_evaluation_and_authentication():
    app.dependency_overrides[current_principal]=lambda:principal
    app.dependency_overrides[csrf_protected]=lambda:principal
    try:
      with TestClient(app) as client:
        name=f"Phase4 {uuid4().hex[:8]}"
        scenario=client.post("/api/scenarios",json={"name":name,"strategy_type":"CUSTOM_RESEARCH","description":"phase4","lifecycle":"RESEARCH","parameters":{}},headers={"X-CSRF-Token":"csrf"})
        assert scenario.status_code==201; scenario_id=scenario.json()["id"]
        created=client.post(f"/api/strategy-engine/scenarios/{scenario_id}/versions",json={"specification":SPEC},headers={"X-CSRF-Token":"csrf"})
        assert created.status_code==201; body=created.json(); assert body["version"]==1 and body["trading"]=="DISABLED"
        assert client.post(f"/api/strategy-engine/scenarios/{scenario_id}/versions",json={"specification":SPEC},headers={"X-CSRF-Token":"csrf"}).status_code==409
        decision=client.post(f"/api/strategy-engine/versions/{body['id']}/evaluate",json={"symbol":"AAPL","as_of":"2026-08-18T12:00:00Z","facts":{"event_yield_pct":0.4,"recovered":False,"earnings_excluded":False}},headers={"X-CSRF-Token":"csrf"})
        assert decision.status_code==201; result=decision.json()
        assert result["decision"]=="ENTRY" and result["executable"] is False and result["risk_authorized"] is False
        history=client.get(f"/api/strategy-engine/versions/{body['id']}/decisions")
        assert history.status_code==200 and history.json()[0]["trading"]=="DISABLED"
        unsafe={**SPEC,"position_sizing":{**SPEC["position_sizing"],"max_position_pct":50}}
        assert client.post(f"/api/strategy-engine/scenarios/{scenario_id}/versions",json={"specification":unsafe},headers={"X-CSRF-Token":"csrf"}).status_code==422
    finally: app.dependency_overrides.clear()


def test_strategy_engine_routes_reject_unauthenticated_access():
    with TestClient(app) as client:
        assert client.get("/api/strategy-engine/scenarios/1/versions").status_code==401
        assert client.get("/api/strategy-engine/versions/1/decisions").status_code==401
