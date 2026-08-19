from datetime import UTC,datetime,timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import Principal,csrf_protected,current_principal
from app.database import SessionLocal
from app.main import app
from app.risk.engine import evaluate
from app.risk.service import DEFAULT_POLICY,effective_policy
from app.models import StrategyScenario,StrategyVersion,StrategyDecision

NOW=datetime(2026,8,19,15,0,tzinfo=UTC)
def proposal(**changes):
    value={"proposal_id":f"risk-{uuid4().hex}","strategy_decision_id":None,"symbol":"SPY","side":"BUY","quantity":1.0,"price":500.0,"reference_price":500.0,"portfolio_value":100000.0,"buying_power":50000.0,"current_position_value":0.0,"total_exposure_value":10000.0,"sector_exposure_value":5000.0,"correlated_exposure_value":5000.0,"daily_pnl_pct":0.0,"drawdown_pct":0.0,"annualized_volatility_pct":10.0,"open_order_count":0,"market_data_as_of":NOW-timedelta(seconds=10),"proposal_created_at":NOW-timedelta(seconds=10)}
    value.update(changes);return value

def test_all_controls_authorize_but_never_execute():
    result=evaluate(DEFAULT_POLICY,proposal(),{"kill_switch_engaged":False,"circuit_breaker_engaged":False},NOW)
    assert result["outcome"]=="AUTHORIZED" and result["risk_authorized"] is True
    assert result["executable"] is False and result["trading"]=="DISABLED" and len(result["checks"])==17

def test_every_phase6_control_fails_closed():
    cases=[
      ({}, {"kill_switch_engaged":True,"circuit_breaker_engaged":False},"KILL_SWITCH_CLEAR"),
      ({}, {"kill_switch_engaged":False,"circuit_breaker_engaged":True},"CIRCUIT_BREAKER_CLEAR"),
      ({"quantity":20000},None,"ORDER_QUANTITY"),({"quantity":30},None,"ORDER_NOTIONAL"),({"price":510},None,"PRICE_SANITY"),
      ({"current_position_value":900,"quantity":1},None,"POSITION_LIMIT"),({"total_exposure_value":24900},None,"PORTFOLIO_EXPOSURE"),
      ({"sector_exposure_value":19900},None,"SECTOR_EXPOSURE"),({"correlated_exposure_value":29900},None,"CORRELATION_EXPOSURE"),
      ({"daily_pnl_pct":-3},None,"DAILY_LOSS"),({"drawdown_pct":11},None,"DRAWDOWN"),({"annualized_volatility_pct":41},None,"VOLATILITY"),
      ({"buying_power":1000,"quantity":1},None,"BUYING_POWER"),({"side":"SELL","current_position_value":0},None,"SELL_POSITION_AVAILABLE"),({"open_order_count":20},None,"OPEN_ORDERS"),
      ({"market_data_as_of":NOW-timedelta(seconds=301)},None,"MARKET_DATA_FRESH"),({"proposal_created_at":NOW-timedelta(seconds=301)},None,"PROPOSAL_FRESH")]
    for changes,controls,code in cases:
        result=evaluate(DEFAULT_POLICY,proposal(**changes),controls or {"kill_switch_engaged":False,"circuit_breaker_engaged":False},NOW)
        assert result["outcome"]=="REJECTED" and code in result["reason_codes"] and result["risk_authorized"] is False

def test_risk_api_auth_persistence_deduplication_and_controls():
    principal=Principal(username="test-operator",session_id="risk",csrf_token="csrf")
    with TestClient(app) as anonymous:assert anonymous.get("/api/risk/status").status_code==401
    app.dependency_overrides[current_principal]=lambda:principal;app.dependency_overrides[csrf_protected]=lambda:principal
    try:
      with TestClient(app) as client:
        status=client.get("/api/risk/status");assert status.status_code==200 and status.json()["execution_available"] is False
        payload=proposal();payload["market_data_as_of"]=datetime.now(UTC).isoformat();payload["proposal_created_at"]=datetime.now(UTC).isoformat()
        created=client.post("/api/risk/assessments",json=payload,headers={"X-CSRF-Token":"csrf"});assert created.status_code==201,created.text
        body=created.json();assert body["outcome"]=="AUTHORIZED" and body["executable"] is False and body["trading"]=="DISABLED"
        repeat=client.post("/api/risk/assessments",json=payload,headers={"X-CSRF-Token":"csrf"});assert repeat.json()["id"]==body["id"]
        payload["price"]=499;duplicate=client.post("/api/risk/assessments",json=payload,headers={"X-CSRF-Token":"csrf"});assert "DUPLICATE_PROPOSAL" in duplicate.json()["reason_codes"]
        changed=client.patch("/api/risk/controls",json={"kill_switch_engaged":True,"circuit_breaker_engaged":False,"reason":"Acceptance kill-switch test"},headers={"X-CSRF-Token":"csrf"});assert changed.status_code==200
        payload=proposal();payload["market_data_as_of"]=datetime.now(UTC).isoformat();payload["proposal_created_at"]=datetime.now(UTC).isoformat()
        rejected=client.post("/api/risk/assessments",json=payload,headers={"X-CSRF-Token":"csrf"});assert "KILL_SWITCH_CLEAR" in rejected.json()["reason_codes"]
        client.patch("/api/risk/controls",json={"kill_switch_engaged":False,"circuit_breaker_engaged":False,"reason":"Reset after test"},headers={"X-CSRF-Token":"csrf"})
    finally:app.dependency_overrides.clear()


def test_strategy_limits_can_only_tighten_global_policy():
    marker=uuid4().hex
    with SessionLocal() as db:
        scenario=StrategyScenario(name=f"Risk overlay {marker}",strategy_type="MEAN_REVERSION",description="fixture",lifecycle="RESEARCH",parameters={});db.add(scenario);db.flush()
        version=StrategyVersion(scenario_id=scenario.id,version=1,specification={"position_sizing":{"max_position_pct":0.25,"max_strategy_allocation_pct":5.0},"parameters":{"max_drawdown_pct":4.0}},checksum=marker.ljust(64,"0"),created_by="test");db.add(version);db.flush()
        decision=StrategyDecision(version_id=version.id,symbol="SPY",as_of=NOW,decision="ENTRY",reason_codes=[],proposed_weight_pct=0.25,inputs={});db.add(decision);db.flush()
        bounded=effective_policy(db,DEFAULT_POLICY,decision.id)
        assert bounded["max_position_pct"]==0.25 and bounded["max_portfolio_exposure_pct"]==5.0 and bounded["max_drawdown_pct"]==4.0
        assert effective_policy(db,{**DEFAULT_POLICY,"max_position_pct":0.1},decision.id)["max_position_pct"]==0.1
