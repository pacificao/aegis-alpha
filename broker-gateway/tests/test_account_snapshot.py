import os,tempfile
from pathlib import Path
from cryptography.fernet import Fernet
_fixture=Path(tempfile.mkdtemp(prefix="aegis-gateway-test-"));_key=_fixture/"key";_key.write_bytes(Fernet.generate_key());_key.chmod(0o600)
os.environ.setdefault("BROKER_GATEWAY_SHARED_SECRET","x"*32);os.environ.setdefault("AEGIS_UI_URL","https://aegis-alpha.pacificao.com");os.environ["BROKER_GATEWAY_DATA_DIR"]=str(_fixture/"data");os.environ["BROKER_GATEWAY_KEY_FILE"]=str(_key)
from pydantic import ValidationError
from app.main import ACCOUNT_SNAPSHOT_TOOLS,AccountSnapshotRequest,_account_number,_opaque,_records,_sanitize
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
