from datetime import UTC,datetime,timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.auth import Principal,csrf_protected,current_principal
from app.database import SessionLocal
from app.main import app,settings
from app.models import BrokerConnectionConfig,BrokerSnapshot,ControlledExecutionRecord,LiveTradingAuthorization,RiskAssessment,RiskControlState,StrategyDecision,StrategyScenario,StrategyVersion

P=Principal(username="test-operator",session_id="live",csrf_token="csrf")

def fixture():
    marker=uuid4().hex;now=datetime.now(UTC)
    with SessionLocal() as db:
        scenario=StrategyScenario(name=f"Live {marker}",strategy_type="DIVIDEND_FARM",description="live fixture",lifecycle="RESEARCH",parameters={});db.add(scenario);db.flush()
        version=StrategyVersion(scenario_id=scenario.id,version=1,specification={"bounded":True},checksum=marker.ljust(64,"0")[:64],created_by="test");db.add(version);db.flush()
        decision=StrategyDecision(version_id=version.id,symbol="SPY",as_of=now,decision="ENTRY",reason_codes=["QUALIFIED"],proposed_weight_pct=.1,inputs={});db.add(decision);db.flush()
        request={"symbol":"SPY","side":"BUY","quantity":.002,"price":500.0,"market_data_as_of":now.isoformat(),"proposal_created_at":now.isoformat()}
        risk=RiskAssessment(proposal_id=f"live-{marker}",strategy_decision_id=decision.id,policy_id=1,outcome="AUTHORIZED",reason_codes=[],checks=[],request_snapshot=request,request_checksum=marker.ljust(64,"1")[:64],notional=1,risk_authorized=True,created_by="test");db.add(risk)
        config=db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider=="robinhood"))
        if config is None:config=BrokerConnectionConfig(provider="robinhood",connection_name="Test",endpoint="https://agent.robinhood.com/mcp/trading",mode="READ_ONLY");db.add(config)
        config.selected_account_ref="ref_123456789012345678901234"
        controls=db.get(RiskControlState,1)
        if controls is None:controls=RiskControlState(id=1,kill_switch_engaged=False,circuit_breaker_engaged=False,reason="test",updated_by="test");db.add(controls)
        controls.kill_switch_engaged=False;controls.circuit_breaker_engaged=False
        auth=db.get(LiveTradingAuthorization,1)
        if auth is None:auth=LiveTradingAuthorization(id=1,enabled=False,max_order_notional=1,authorized_by="test",reason="disabled");db.add(auth)
        auth.enabled=False;auth.expires_at=now;db.commit();return risk.id

def prepare(client,risk_id,monkeypatch):
    monkeypatch.setattr(settings,"aegis_trading_enabled",True)
    monkeypatch.setattr("app.main.BrokerGatewayClient.status",lambda self:{"status":"CONNECTED","execution_adapter_deployed":True,"execution_enabled":True})
    monkeypatch.setattr("app.main.BrokerGatewayClient.execution_review",lambda self,payload:{"status":"REVIEWED","review":{"verified":True},"order_placed":False})
    created=client.post("/api/controlled-live/intents",json={"risk_assessment_id":risk_id,"order_type":"LIMIT"});assert created.status_code==201,created.text;intent=created.json()
    approved=client.post(f"/api/controlled-live/intents/{intent['id']}/approve",json={"intent_checksum":intent["intent_checksum"],"confirmation":"APPROVE CONTROLLED TRIAL"});assert approved.status_code==200
    reviewed=client.post(f"/api/controlled-live/intents/{intent['id']}/review");assert reviewed.status_code==200,reviewed.text
    authorized=client.patch("/api/controlled-live/authorization",json={"enabled":True,"max_order_notional":1,"duration_minutes":5,"confirmation":"AUTHORIZE CONTROLLED LIVE TRADING","reason":"Controlled one dollar production acceptance"});assert authorized.status_code==200,authorized.text
    return intent

@pytest.fixture
def client():
    app.dependency_overrides[current_principal]=lambda:P;app.dependency_overrides[csrf_protected]=lambda:P
    with TestClient(app) as value:yield value
    app.dependency_overrides.clear();settings.aegis_trading_enabled=False

def test_exact_order_submits_once_and_duplicate_is_idempotent(client,monkeypatch):
    intent=prepare(client,fixture(),monkeypatch);calls=[]
    def place(self,payload):
        calls.append(payload);return {"status":"SUBMITTED","actual_order":{"symbol":"SPY","side":"BUY","quantity":.002,"order_type":"LIMIT","limit_price":500,"order_ref":"order-1"}}
    monkeypatch.setattr("app.execution.live.BrokerGatewayClient.execution_place",place)
    first=client.post(f"/api/controlled-live/intents/{intent['id']}/execute");assert first.status_code==200,first.text;assert first.json()["order_placed"] is True
    again=client.post(f"/api/controlled-live/intents/{intent['id']}/execute");assert again.status_code==200 and again.json()["idempotent"] is True and len(calls)==1

def test_kill_switch_blocks_before_broker_call(client,monkeypatch):
    intent=prepare(client,fixture(),monkeypatch);called=[]
    with SessionLocal() as db:controls=db.get(RiskControlState,1);controls.kill_switch_engaged=True;db.commit()
    monkeypatch.setattr("app.execution.live.BrokerGatewayClient.execution_place",lambda self,payload:called.append(payload))
    response=client.post(f"/api/controlled-live/intents/{intent['id']}/execute");assert response.status_code==409 and called==[]

def test_known_rejection_is_terminal_without_duplicate(client,monkeypatch):
    intent=prepare(client,fixture(),monkeypatch);calls=[]
    def reject(self,payload):calls.append(payload);return {"status":"REJECTED"}
    monkeypatch.setattr("app.execution.live.BrokerGatewayClient.execution_place",reject)
    response=client.post(f"/api/controlled-live/intents/{intent['id']}/execute");assert response.status_code==200 and response.json()["status"]=="REJECTED"
    again=client.post(f"/api/controlled-live/intents/{intent['id']}/execute");assert again.status_code==200 and len(calls)==1

def test_unknown_or_mismatched_submission_engages_breaker(client,monkeypatch):
    intent=prepare(client,fixture(),monkeypatch)
    monkeypatch.setattr("app.execution.live.BrokerGatewayClient.execution_place",lambda self,payload:{"status":"ERROR"})
    response=client.post(f"/api/controlled-live/intents/{intent['id']}/execute");assert response.status_code==502
    with SessionLocal() as db:assert db.get(RiskControlState,1).circuit_breaker_engaged is True

def test_fresh_snapshot_reconciles_partial_fill_without_resubmission(client,monkeypatch):
    intent=prepare(client,fixture(),monkeypatch);calls=[]
    def place(self,payload):calls.append(payload);return {"status":"SUBMITTED","actual_order":{"symbol":"SPY","side":"BUY","quantity":.002,"order_type":"LIMIT","limit_price":500,"order_ref":"partial-1"}}
    monkeypatch.setattr("app.execution.live.BrokerGatewayClient.execution_place",place)
    assert client.post(f"/api/controlled-live/intents/{intent['id']}/execute").status_code==200
    marker=uuid4().hex
    with SessionLocal() as db:
        db.add(BrokerSnapshot(provider="robinhood",status="VERIFIED",account_count=1,account_refs=["ref_123456789012345678901234"],balances=[],holdings=[],orders=[{"dataset":"get_equity_orders","records":[{"id":"partial-1","symbol":"SPY","side":"BUY","quantity":.002,"order_type":"LIMIT","limit_price":500,"executions":[{"quantity":.001,"price":499.9}]}]}],fills=[],reconciliation={"status":"MATCHED"},checksum=marker.ljust(64,"0")[:64],source_observed_at=datetime.now(UTC),created_by="test"));db.commit()
    reconciled=client.post(f"/api/controlled-live/intents/{intent['id']}/reconcile");assert reconciled.status_code==200,reconciled.text
    assert reconciled.json()["status"]=="PARTIALLY_FILLED" and reconciled.json()["fill_quantity"]==.001
    repeated=client.post(f"/api/controlled-live/intents/{intent['id']}/execute");assert repeated.status_code==200 and repeated.json()["idempotent"] is True and len(calls)==1

def test_open_order_cancel_is_bounded_and_idempotent(client,monkeypatch):
    intent=prepare(client,fixture(),monkeypatch);placements=[];cancellations=[]
    monkeypatch.setattr("app.execution.live.BrokerGatewayClient.execution_place",lambda self,payload:(placements.append(payload) or {"status":"SUBMITTED","actual_order":{"symbol":"SPY","side":"BUY","quantity":.002,"order_type":"LIMIT","limit_price":500,"order_ref":"cancel-1"}}))
    assert client.post(f"/api/controlled-live/intents/{intent['id']}/execute").status_code==200
    monkeypatch.setattr("app.main.BrokerGatewayClient.execution_cancel",lambda self,payload:(cancellations.append(payload) or {"status":"CANCEL_REQUESTED"}))
    body={"confirmation":"CANCEL LIVE ORDER","reason":"Operator cancellation acceptance test"}
    first=client.post(f"/api/controlled-live/intents/{intent['id']}/cancel",json=body);assert first.status_code==200,first.text
    again=client.post(f"/api/controlled-live/intents/{intent['id']}/cancel",json=body);assert again.status_code==200 and again.json()["idempotent"] is True
    assert len(placements)==1 and len(cancellations)==1
