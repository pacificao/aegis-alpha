from datetime import UTC,datetime,timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import Principal,csrf_protected,current_principal
from app.database import SessionLocal
from app.main import app
from app.models import DataProvider,DataRecord,Instrument
from app.paper.service import execute,snapshot
from app.risk.service import assess,ensure_defaults
from app.schemas import RiskAssessmentRequest


def setup_order(stale=False):
    db=SessionLocal();ensure_defaults(db);tag=uuid4().hex[:8].upper();symbol="P"+tag;provider=db.query(DataProvider).filter_by(name="paper-test-"+tag).first() or DataProvider(name="paper-test-"+tag,provider_type="TEST",enabled=True,base_url="https://example.com",credential_status="NOT_REQUIRED");db.add(provider);inst=Instrument(symbol=symbol,name="Paper test",metadata_json={});db.add(inst);db.flush();now=datetime.now(UTC);observed=now-timedelta(seconds=301 if stale else 1);quote=DataRecord(provider_id=provider.id,instrument_id=inst.id,data_type="QUOTE",external_id=tag,event_time=observed,interval="snapshot",payload={"price":100.0},source_url="https://example.com/quote",observed_at=observed,quality_status="VALID",checksum=uuid4().hex*2);db.add(quote);db.flush();payload=RiskAssessmentRequest(proposal_id="paper-"+uuid4().hex,strategy_decision_id=None,symbol=symbol,side="BUY",quantity=1,price=100,reference_price=100,portfolio_value=100000,buying_power=50000,current_position_value=0,total_exposure_value=10000,sector_exposure_value=5000,correlated_exposure_value=5000,daily_pnl_pct=0,drawdown_pct=0,annualized_volatility_pct=10,open_order_count=0,market_data_as_of=now,proposal_created_at=now);risk=assess(db,payload,"test",now);db.refresh(quote);return db,risk.id,quote.id,now,symbol

def test_paper_fill_portfolio_and_isolation():
    db,risk_id,quote_id,now,symbol=setup_order();order=execute(db,risk_id,quote_id,"test",now);state=snapshot(db)
    assert order.status=="FILLED" and any(p["symbol"]==symbol for p in state["positions"]) and state["fill_count"]>=1
    assert state["environment"]=="PAPER" and state["broker_called"] is False and state["live_execution_available"] is False and state["trading"]=="DISABLED"
    try:execute(db,risk_id,quote_id,"test",now);assert False
    except ValueError as exc:assert "already consumed" in str(exc)
    db.close()

def test_stale_live_quote_fails_closed():
    db,risk_id,quote_id,now,_=setup_order(stale=True)
    try:execute(db,risk_id,quote_id,"test",now);assert False
    except ValueError as exc:assert "stale" in str(exc)
    db.close()

def test_simulator_api_auth_and_no_live_execution():
    principal=Principal(username="test-operator",session_id="paper",csrf_token="csrf")
    with TestClient(app) as anonymous:assert anonymous.get("/api/simulator/status").status_code==401
    db,risk_id,quote_id,_,_=setup_order();db.close();app.dependency_overrides[current_principal]=lambda:principal;app.dependency_overrides[csrf_protected]=lambda:principal
    try:
      with TestClient(app) as client:
        result=client.post("/api/simulator/orders",json={"risk_assessment_id":risk_id,"quote_record_id":quote_id},headers={"X-CSRF-Token":"csrf"});assert result.status_code==201,result.text
        body=result.json();assert body["environment"]=="PAPER" and body["broker_called"] is False and body["executable_live"] is False and body["trading"]=="DISABLED"
        assert client.get("/api/simulator/status").status_code==200
    finally:app.dependency_overrides.clear()

def test_paper_module_has_no_broker_dependency():
    from pathlib import Path
    source=Path("app/paper/service.py").read_text()
    assert "BrokerGateway" not in source and "Robinhood" not in source and "app.broker" not in source
