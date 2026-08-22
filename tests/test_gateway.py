from datetime import UTC,datetime
from pathlib import Path
from fastapi.testclient import TestClient
from app.auth import Principal,csrf_protected,current_principal
from app.database import SessionLocal
from app.gateway import BrokerGatewayClient
from app.main import app
from app.broker_sync.service import normalize,synchronize
from app.data.worker import _run_broker_sync
from app.models import BrokerSnapshot,DevelopmentActivity
P=Principal(username="test-operator",session_id="test",csrf_token="csrf")
def payload():
 return {"status":"COMPLETE","provider":"robinhood","observed_at":datetime.now(UTC).isoformat(),"accounts":[{"account_ref":"ref_0123456789abcdef01234567","datasets":{"get_portfolio":{"equity":"1000.00","buying_power":"250.00"},"get_equity_positions":[{"symbol":"SPY","quantity":"1","equity":"500"}],"get_equity_orders":[{"id":"ref_order","state":"filled","executions":[{"quantity":"1","price":"500"}]}]},"failures":[]}],"trading":"DISABLED","mode":"READ_ONLY"}
def test_normalizes_balances_holdings_orders_fills_and_reconciles():
 n=normalize(payload());assert n["status"]=="VERIFIED";assert len(n["balances"])==1;assert len(n["holdings"])==1;assert len(n["orders"])==1;assert len(n["fills"])==1;assert n["reconciliation"]["status"]=="MATCHED";assert len(n["checksum"])==64
def test_normalizes_official_nested_data_without_counting_guide_as_position():
 p=payload();p["accounts"][0]["datasets"]["get_equity_positions"]={"data":{"positions":[]},"guide":"display guidance"}
 n=normalize(p);assert n["holdings"][0]["records"]==[]
def test_unsafe_gateway_response_fails_closed():
 p=payload();p["trading"]="ENABLED"
 try:normalize(p);assert False
 except ValueError:pass
 p=payload();p["accounts"][0]["datasets"]["place_equity_order"]={}
 try:normalize(p);assert False
 except ValueError:pass
def test_retry_persistence_audit_and_no_secret(monkeypatch):
 calls={"n":0}
 def snap(self,selected_account_ref):calls["n"]+=1;return {"status":"ERROR"} if calls["n"]<3 else payload()
 monkeypatch.setattr(BrokerGatewayClient,"account_snapshot",snap);db=SessionLocal();run=synchronize(db,BrokerGatewayClient(__import__("app.config",fromlist=["get_settings"]).get_settings()),"test","ref_0123456789abcdef01234567")
 assert run.status=="COMPLETE" and run.attempts==3
 row=db.get(BrokerSnapshot,run.snapshot_id);assert row.reconciliation["status"]=="MATCHED";assert "account_number" not in str(row.balances)
 audit=db.query(DevelopmentActivity).filter_by(entity_type="broker_sync_run",entity_id=run.id).one();assert "trading=DISABLED" in audit.detail;db.close()
def test_authenticated_sync_and_portfolio_projection(monkeypatch):
 db=SessionLocal();cfg=__import__("app.models",fromlist=["BrokerConnectionConfig"]).BrokerConnectionConfig;row=db.query(cfg).filter_by(provider="robinhood").one();row.selected_account_ref="ref_0123456789abcdef01234567";db.commit();db.close()
 monkeypatch.setattr(BrokerGatewayClient,"status",lambda self:{"status":"CONNECTED","trading":"DISABLED","mode":"READ_ONLY"});monkeypatch.setattr(BrokerGatewayClient,"account_snapshot",lambda self,selected_account_ref:payload())
 app.dependency_overrides[current_principal]=lambda:P;app.dependency_overrides[csrf_protected]=lambda:P
 try:
  with TestClient(app) as client:
   sync=client.post("/api/broker/robinhood/sync",headers={"X-CSRF-Token":"csrf"});assert sync.status_code==200;assert sync.json()["executable"] is False;assert sync.json()["trading"]=="DISABLED"
   view=client.get("/api/portfolio");assert view.status_code==200;body=view.json();assert body["holdings_available"] is True;assert body["snapshot"]["reconciliation"]["status"]=="MATCHED"
   readiness=client.get("/api/performance/readiness");assert readiness.status_code==200;assert readiness.json()["broker_snapshots"]>=1;assert readiness.json()["trading"]=="DISABLED"
 finally:app.dependency_overrides.clear()
def test_no_execution_surface_exists():
 root=Path(__file__).parents[1];sources=((root/"backend/app/broker.py").read_text()+(root/"backend/app/gateway.py").read_text())
 assert "place_order" not in sources and "cancel_order" not in sources and "execute_order" not in sources
 with TestClient(app) as client:assert client.post("/api/broker/orders",json={}).status_code in {401,404,405}
def test_reconciliation_detects_duplicates_and_overfills():
 p=payload();order=p["accounts"][0]["datasets"]["get_equity_orders"][0];order["quantity"]="0.5";p["accounts"][0]["datasets"]["get_equity_orders"].append(dict(order))
 n=normalize(p);r=n["reconciliation"];assert r["status"]=="ATTENTION";assert r["order_refs_unique"] is False;assert r["fill_quantities_valid"] is False
def test_persisted_disconnected_authorization_can_revalidate_by_read(monkeypatch):
 db=SessionLocal();cfg=__import__("app.models",fromlist=["BrokerConnectionConfig"]).BrokerConnectionConfig;row=db.query(cfg).filter_by(provider="robinhood").one();row.selected_account_ref="ref_0123456789abcdef01234567";db.commit();db.close()
 monkeypatch.setattr(BrokerGatewayClient,"status",lambda self:{"status":"DISCONNECTED","trading":"DISABLED","mode":"READ_ONLY"});monkeypatch.setattr(BrokerGatewayClient,"account_snapshot",lambda self,selected_account_ref:payload());app.dependency_overrides[csrf_protected]=lambda:P
 try:
  with TestClient(app) as client:r=client.post("/api/broker/robinhood/sync",headers={"X-CSRF-Token":"csrf"});assert r.status_code==200 and r.json()["trading"]=="DISABLED"
 finally:app.dependency_overrides.clear()
def test_multi_account_snapshot_is_rejected():
 p=payload();p["accounts"].append({**p["accounts"][0],"account_ref":"ref_abcdefabcdefabcdefabcdef"})
 try:normalize(p);assert False
 except ValueError:pass
def test_unattended_worker_refreshes_selected_account_without_user_session(monkeypatch):
 db=SessionLocal();cfg=__import__("app.models",fromlist=["BrokerConnectionConfig"]).BrokerConnectionConfig;row=db.query(cfg).filter_by(provider="robinhood").one();row.selected_account_ref="ref_0123456789abcdef01234567";before=db.query(BrokerSnapshot).count();db.commit();db.close()
 monkeypatch.setattr(BrokerGatewayClient,"status",lambda self:{"status":"CONNECTED","trading":"DISABLED","mode":"READ_ONLY"});monkeypatch.setattr(BrokerGatewayClient,"account_snapshot",lambda self,selected_account_ref:payload())
 _run_broker_sync(__import__("app.config",fromlist=["get_settings"]).get_settings());db=SessionLocal();assert db.query(BrokerSnapshot).count()>=before;assert db.query(DevelopmentActivity).filter_by(actor="system:broker-sync",action="broker_snapshot_synchronized").count()>=1;db.close()
def test_gateway_account_scope_mismatch_fails_closed(monkeypatch):
 monkeypatch.setattr(BrokerGatewayClient,"account_snapshot",lambda self,selected_account_ref:payload())
 db=SessionLocal();run=synchronize(db,BrokerGatewayClient(__import__("app.config",fromlist=["get_settings"]).get_settings()),"test","ref_abcdefabcdefabcdefabcdef")
 assert run.status=="FAILED" and run.error_code=="BROKER_READ_FAILED";db.close()
