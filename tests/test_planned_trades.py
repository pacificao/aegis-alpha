from datetime import date, datetime, UTC, timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import Principal,csrf_protected,current_principal
from app.database import SessionLocal
from app.main import app
from app.models import BrokerSnapshot,CandidateScanState,DevelopmentActivity,Instrument,PlannedTrade,StrategyDecision,StrategyScenario,StrategyVersion
from app.data.calendar import next_sessions
from app.planning import create_qualified_plans,expire_missed_plans
from sqlalchemy import func,select

P=Principal(username="test-operator",session_id="plans",csrf_token="csrf")
def test_planned_trade_reserves_deployable_cash_and_cancel_releases(monkeypatch):
    marker=uuid4().hex
    with SessionLocal() as db:
        scenario=StrategyScenario(name=f"Plan {marker}",strategy_type="DIVIDEND_FARM",description="planned entry test",lifecycle="RESEARCH",parameters={});db.add(scenario);db.flush()
        version=StrategyVersion(scenario_id=scenario.id,version=1,specification={},checksum=marker.ljust(64,"0")[:64],created_by="test");db.add(version);db.flush()
        decision=StrategyDecision(version_id=version.id,symbol="SPY",as_of=datetime.now(UTC),decision="ENTRY",reason_codes=["QUALIFIED"],proposed_weight_pct=.1,inputs={});db.add(decision);db.commit();decision_id=decision.id
    monkeypatch.setattr("app.main._buying_power",lambda db:10.0)
    app.dependency_overrides[current_principal]=lambda:P;app.dependency_overrides[csrf_protected]=lambda:P
    try:
        with TestClient(app) as client:
            entry=next_sessions(1)[0]["session_date"]
            created=client.post("/api/planned-trades",json={"strategy_decision_id":decision_id,"planned_entry_date":entry,"quantity":1,"reference_price":4,"rationale":"Qualified deterministic opportunity"})
            assert created.status_code==201,created.text
            body=created.json();assert body["capacity"]["planned_reservations"]>=4 and body["capacity"]["deployable_cash"]<=6
            assert body["plan"]["executable"] is False and body["plan"]["broker_called"] is False and body["plan"]["notification_status"]=="PENDING"
            too_large=client.post("/api/planned-trades",json={"strategy_decision_id":decision_id,"planned_entry_date":entry,"quantity":2,"reference_price":4,"rationale":"Would exceed remaining deployable cash"})
            assert too_large.status_code==409
            cancelled=client.post(f"/api/planned-trades/{body['plan']['id']}/cancel",json={"reason":"Operator cancelled this proposed allocation"})
            assert cancelled.status_code==200 and cancelled.json()["plan"]["status"]=="CANCELLED"
            assert cancelled.json()["capacity"]["deployable_cash"]==10
    finally:app.dependency_overrides.clear()

def test_planned_trade_routes_require_authentication():
    with TestClient(app) as client:assert client.get("/api/planned-trades").status_code==401

def test_missed_approval_states_expire_release_capital_and_audit():
    marker=uuid4().hex
    with SessionLocal() as db:
        scenario=StrategyScenario(name=f"Expiry {marker}",strategy_type="DIVIDEND_FARM",description="expiry fixture",lifecycle="RESEARCH",parameters={});db.add(scenario);db.flush()
        version=StrategyVersion(scenario_id=scenario.id,version=1,specification={},checksum=marker.ljust(64,"0")[:64],created_by="test");db.add(version);db.flush()
        for index,status in enumerate(("PLANNED","REVALIDATION_BLOCKED","READY_FOR_FINAL_APPROVAL")):
            decision=StrategyDecision(version_id=version.id,symbol=f"X{index}",as_of=datetime.now(UTC),decision="ENTRY",reason_codes=["QUALIFIED"],proposed_weight_pct=.1,inputs={});db.add(decision);db.flush()
            db.add(PlannedTrade(strategy_decision_id=decision.id,symbol=decision.symbol,side="BUY",quantity=1,reference_price=2,reserved_notional=2,planned_entry_date=date.today()-timedelta(days=1),status=status,rationale="Missed approval fixture",plan_checksum=(marker+str(index)).ljust(64,"0")[:64],created_by="test"))
        db.commit();expired=expire_missed_plans(db,date.today());assert len(expired)==3
        assert db.query(PlannedTrade).filter(PlannedTrade.id.in_(expired),PlannedTrade.status=="EXPIRED").count()==3
        assert db.query(DevelopmentActivity).filter(DevelopmentActivity.entity_type=="planned_trade",DevelopmentActivity.entity_id.in_(expired),DevelopmentActivity.action=="planned_trade_expired").count()==3


def test_fully_qualified_entry_is_planned_without_risk_or_broker_call():
    marker=uuid4().hex;symbol=f"A{marker[:8].upper()}";today=date(2026,8,22);entry=date(2026,8,24);ex_date=date(2026,8,25)
    with SessionLocal() as db:
        scenario=db.scalar(select(StrategyScenario).where(StrategyScenario.name=="Dividend Farm"))
        version_number=(db.scalar(select(func.max(StrategyVersion.version)).where(StrategyVersion.scenario_id==scenario.id)) or 0)+1
        spec={"universe":{"symbols":[symbol],"exclude_symbols":[],"asset_types":["EQUITY"]},"entry_rules":[{"field":"event_yield_pct","operator":"gte","value":0.1,"reason":"YIELD"}],"exit_rules":[{"field":"recovered","operator":"eq","value":True,"reason":"RECOVERED"}],"filters":[],"parameters":{"entry_days_before_ex_date":1},"position_sizing":{"max_position_pct":1,"max_strategy_allocation_pct":25}};version=StrategyVersion(scenario_id=scenario.id,version=version_number,specification=spec,checksum=marker.ljust(64,"0")[:64],created_by="test");db.add(version);db.flush()
        instrument=Instrument(symbol=symbol,asset_type="EQUITY",active=True);db.add(instrument);db.flush();decision=StrategyDecision(version_id=version.id,symbol=symbol,as_of=datetime.now(UTC),decision="ENTRY",reason_codes=["ALL_STRATEGY_GATES_PASSED"],proposed_weight_pct=1,inputs={"latest_close":10,"next_ex_dividend_date":ex_date.isoformat()});db.add(decision);db.flush();state=CandidateScanState(version_id=version.id,instrument_id=instrument.id,last_decision_id=decision.id,evidence_checksum=marker.ljust(64,"1")[:64],outcome="ENTRY",detail="READY",last_scanned_at=datetime.now(UTC),next_scan_at=datetime.now(UTC));db.add(state)
        snapshot=BrokerSnapshot(provider="robinhood",status="VERIFIED",account_count=1,account_refs=["ref_test"],balances=[{"dataset":"get_portfolio","records":[{"total_value":"5","buying_power":{"buying_power":"5"}}]}],holdings=[],orders=[],fills=[],reconciliation={},checksum=marker.ljust(64,"2")[:64],source_observed_at=datetime.now(UTC),created_by="test");db.add(snapshot);db.commit()
        created=create_qualified_plans(db,today);assert len(created)==1;plan=db.get(PlannedTrade,created[0]);assert plan.symbol==symbol and plan.planned_entry_date==entry and plan.reserved_notional==1 and plan.created_by=="system:qualified-planner" and plan.final_risk_assessment_id is None
        assert create_qualified_plans(db,today)==[]
