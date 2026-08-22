from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import Principal, csrf_protected, current_principal
from app.database import SessionLocal
from app.main import app
from app.models import (
    BrokerConnectionConfig,
    RiskAssessment,
    RiskControlState,
    StrategyDecision,
    StrategyScenario,
    StrategyVersion,
)


def test_controlled_trial_requires_risk_and_human_approval_but_never_executes():
    principal = Principal(username="test-operator", session_id="trial", csrf_token="csrf")
    marker = uuid4().hex
    with SessionLocal() as db:
        scenario = StrategyScenario(name=f"Trial {marker}", strategy_type="DIVIDEND_FARM", description="Controlled trial fixture", lifecycle="RESEARCH", parameters={})
        db.add(scenario); db.flush()
        version = StrategyVersion(scenario_id=scenario.id, version=1, specification={"risk": "bounded"}, checksum=marker.ljust(64, "0")[:64], created_by="test")
        db.add(version); db.flush()
        decision = StrategyDecision(version_id=version.id, symbol="SPY", as_of=datetime.now(UTC), decision="ENTRY", reason_codes=["FIXTURE"], proposed_weight_pct=0.1, inputs={"fixture": True})
        db.add(decision); db.flush()
        request = {"symbol": "SPY", "side": "BUY", "quantity": 0.001, "price": 500.0}
        risk = RiskAssessment(proposal_id=f"trial-{marker}", strategy_decision_id=decision.id, policy_id=1, outcome="AUTHORIZED", reason_codes=[], checks=[], request_snapshot=request, request_checksum=("c" + marker).ljust(64, "0")[:64], notional=0.5, risk_authorized=True, created_by="test")
        db.add(risk)
        config = db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider == "robinhood"))
        if config is None:
            config = BrokerConnectionConfig(provider="robinhood", connection_name="Test", endpoint="https://example.invalid", mode="READ_ONLY")
            db.add(config)
        config.selected_account_ref = config.selected_account_ref or "test-account"
        controls = db.get(RiskControlState, 1)
        if controls is None:
            controls = RiskControlState(id=1, kill_switch_engaged=False, circuit_breaker_engaged=False, reason="test", updated_by="test")
            db.add(controls)
        controls.kill_switch_engaged = False; controls.circuit_breaker_engaged = False
        db.commit(); risk_id = risk.id

    app.dependency_overrides[current_principal] = lambda: principal
    app.dependency_overrides[csrf_protected] = lambda: principal
    try:
        with TestClient(app) as client:
            created = client.post("/api/controlled-live/intents", json={"risk_assessment_id": risk_id, "order_type": "LIMIT"})
            assert created.status_code == 201, created.text
            body = created.json()
            assert body["status"] == "PROPOSED"
            assert body["executable"] is False and body["broker_called"] is False and body["trading"] == "DISABLED"
            bad = client.post(f"/api/controlled-live/intents/{body['id']}/approve", json={"intent_checksum": "0" * 64, "confirmation": "APPROVE CONTROLLED TRIAL"})
            assert bad.status_code == 409
            approved = client.post(f"/api/controlled-live/intents/{body['id']}/approve", json={"intent_checksum": body["intent_checksum"], "confirmation": "APPROVE CONTROLLED TRIAL"})
            assert approved.status_code == 200
            assert approved.json()["status"] == "APPROVED_TRIAL_ONLY"
            assert approved.json()["executable"] is False and approved.json()["broker_called"] is False
            readiness = client.get("/api/controlled-live/readiness")
            assert readiness.status_code == 200
            assert readiness.json()["live_ready"] is False
            assert readiness.json()["gates"]["controlled_live_acceptance"] is False
            assert readiness.json()["gates"]["autonomy_acceptance"] is False
            assert readiness.json()["gates"]["evolution_safety_acceptance"] is False
            assert readiness.json()["order_submission_available"] is False
            history = client.get("/api/portfolio/history")
            assert history.status_code == 200 and history.json()["trading"] == "DISABLED"
    finally:
        app.dependency_overrides.clear()


def test_controlled_trial_routes_require_authentication():
    with TestClient(app) as client:
        assert client.get("/api/controlled-live/readiness").status_code == 401
        assert client.get("/api/controlled-live/intents").status_code == 401
