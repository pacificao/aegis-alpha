import os,tempfile
from pathlib import Path
from datetime import UTC,datetime
from cryptography.fernet import Fernet
_fixture=Path(tempfile.mkdtemp(prefix="aegis-gateway-test-"));_key=_fixture/"key";_key.write_bytes(Fernet.generate_key());_key.chmod(0o600)
os.environ.setdefault("BROKER_GATEWAY_SHARED_SECRET","x"*32);os.environ.setdefault("AEGIS_UI_URL","https://aegis-alpha.pacificao.com");os.environ["BROKER_GATEWAY_DATA_DIR"]=str(_fixture/"data");os.environ["BROKER_GATEWAY_KEY_FILE"]=str(_key)
from pydantic import ValidationError
from app.main import ACCOUNT_SNAPSHOT_TOOLS,AccountSnapshotRequest,ExecutionRequest,_account_number,_opaque,_records,_sanitize,_argument_sets,_execution_arguments
from app.policy import READ_ONLY_TOOLS,is_tool_allowed

def test_snapshot_tools_are_exact_reads_only():
 assert set(ACCOUNT_SNAPSHOT_TOOLS).issubset(READ_ONLY_TOOLS);assert all(is_tool_allowed(name) for name in ACCOUNT_SNAPSHOT_TOOLS);assert not any(name.startswith(("place_","cancel_","review_","create_","update_")) for name in ACCOUNT_SNAPSHOT_TOOLS)
def test_account_helpers_hash_private_identifiers():
 raw={"account_number":"123456789","id":"order-private","symbol":"SPY","nested":{"token":"never"}};safe=_sanitize(raw);rendered=str(safe)
 assert "123456789" not in rendered and "order-private" not in rendered and "never" not in rendered;assert safe["symbol"]=="SPY" and safe["account_number"].startswith("ref_");assert _account_number(raw)=="123456789" and _opaque("123456789")!="123456789"
def test_records_unwraps_official_result_shapes():assert _records({"accounts":[{"account_number":"1"}]})==[{"account_number":"1"}]
def test_account_snapshot_request_requires_opaque_account_scope():
 assert AccountSnapshotRequest(selected_account_ref="ref_0123456789abcdef01234567").selected_account_ref.startswith("ref_")
 try:AccountSnapshotRequest(selected_account_ref="raw-account-number");assert False
 except ValidationError:pass

def test_parameterized_account_reads_are_bounded_and_fail_closed():
 observed=datetime(2026,8,19,tzinfo=UTC);positions={"results":[{"symbol":"spy"},{"ticker":"AAPL"}]}
 tax=_argument_sets("get_equity_tax_lots",{"required":["account_number","symbol"],"properties":{"account_number":{},"symbol":{}}},"private",{"get_equity_positions":positions},observed)
 assert tax==[{"account_number":"private","symbol":"AAPL"},{"account_number":"private","symbol":"SPY"}]
 pnl=_argument_sets("get_realized_pnl",{"required":["account_number","start_date","end_date"],"properties":{"account_number":{},"start_date":{},"end_date":{}}},"private",{},observed)
 assert pnl==[{"account_number":"private","start_date":"2025-08-18","end_date":"2026-08-19"}]
 pnl_optional=_argument_sets("get_realized_pnl",{"required":["account_number"],"properties":{"account_number":{},"start_date":{},"end_date":{},"span":{}}},"private",{},observed)
 assert pnl_optional==[{"account_number":"private","start_date":"2025-08-18","end_date":"2026-08-19"}]
 assert _argument_sets("unknown",{"required":["account_number","unsafe_mode"],"properties":{"account_number":{},"unsafe_mode":{}}},"private",{},observed) is None

def test_execution_schema_mapping_is_exact_and_bounded():
 payload=ExecutionRequest(selected_account_ref="ref_0123456789abcdef01234567",symbol="SPY",side="BUY",quantity=0.01,limit_price=500,intent_checksum="a"*64,approval_checksum="b"*64)
 schema={"required":["account_number","symbol","side","quantity","order_type","limit_price","time_in_force"],"properties":{k:{} for k in ["account_number","symbol","side","quantity","order_type","limit_price","time_in_force"]}}
 args=_execution_arguments(schema,"private",payload);assert args=={"account_number":"private","symbol":"SPY","side":"buy","quantity":0.01,"order_type":"limit","limit_price":500,"time_in_force":"gfd"}
 string_schema={"required":["account_number","symbol","side","type"],"properties":{k:{"type":"string"} for k in ["account_number","symbol","side","type","quantity","limit_price","time_in_force"]}}
 string_args=_execution_arguments(string_schema,"private",payload);assert string_args=={"account_number":"private","symbol":"SPY","side":"buy","type":"limit","quantity":"0.01","limit_price":"500.0","time_in_force":"gfd"}
 try:ExecutionRequest(selected_account_ref="ref_0123456789abcdef01234567",symbol="SPY",side="BUY",quantity=0.001,limit_price=500,intent_checksum="a"*64,approval_checksum="b"*64);assert False
 except ValueError:pass
 assert _execution_arguments({"required":["unsupported"],"properties":{"unsupported":{}}},"private",payload) is None

def test_execution_actual_order_requires_broker_reference():
    from app.main import _actual_order
    assert _actual_order({"symbol":"SPY","side":"buy","quantity":"0.002","type":"limit","price":"500"}) is None
    actual=_actual_order({"id":"order-1","symbol":"SPY","side":"buy","quantity":"0.002","type":"limit","price":"500"})
    assert actual["order_ref"]=="order-1" and actual["symbol"]=="SPY"
