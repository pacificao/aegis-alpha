"""Aegis-owned Robinhood OAuth client and read-only MCP enforcement gateway."""
import json
import hashlib
import hmac
import secrets
import asyncio
import os
from contextlib import suppress
from datetime import UTC, datetime

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl, BaseModel, Field

from .policy import MARKET_DATA_TOOLS, READ_ONLY_TOOLS, SENSITIVE_ARGUMENT_KEYS, contains_sensitive_argument, enforce_tool_allowed, parse_loopback_callback, validate_authorization_url
from .storage import EncryptedFileTokenStorage

MCP_URL = "https://agent.robinhood.com/mcp/trading"
AEGIS_UI_URL = os.environ.get("AEGIS_UI_URL", "https://aegis-alpha.pacificao.com").rstrip("/")
OAUTH_CALLBACK_BASE_URL = os.environ.get("OAUTH_CALLBACK_BASE_URL", AEGIS_UI_URL).rstrip("/")
CALLBACK_URL = f"{OAUTH_CALLBACK_BASE_URL}/api/broker/robinhood/oauth/callback"
OAUTH_REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", CALLBACK_URL)
SHARED_SECRET = os.environ.get("BROKER_GATEWAY_SHARED_SECRET", "")
AUTHORIZATION_ENABLED = os.environ.get("BROKER_AUTHORIZATION_ENABLED", "false").lower() == "true"
if not AEGIS_UI_URL.startswith("https://") or not OAUTH_CALLBACK_BASE_URL.startswith("https://"):
    raise RuntimeError("Aegis UI and OAuth callback URLs must use HTTPS")
if len(SHARED_SECRET) < 32:
    raise RuntimeError("BROKER_GATEWAY_SHARED_SECRET must be at least 32 characters")
storage = EncryptedFileTokenStorage(
    os.environ.get("BROKER_GATEWAY_DATA_DIR", "/var/lib/aegis-broker"),
    os.environ.get("BROKER_GATEWAY_KEY_FILE", "/run/secrets/broker_key"),
)
app = FastAPI(title="Aegis Broker Gateway", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=[AEGIS_UI_URL], allow_methods=["POST"], allow_headers=["Content-Type"])
_flow_task: asyncio.Task | None = None
_auth_url: asyncio.Future | None = None
_callback: asyncio.Future | None = None
_completion_nonce: str | None = None
_state = {"status": "NOT_CONFIGURED", "detail": "authorization has not been completed", "last_sync_at": None, "allowed_tools": 0, "blocked_tools": 0}


async def call_read_only_tool(session: ClientSession, name: str, arguments: dict):
    """The gateway's only MCP invocation path; every call is policy checked."""
    enforce_tool_allowed(name)
    return await session.call_tool(name, arguments)


def internal_auth(x_aegis_gateway_key: str = Header(default="")) -> None:
    if not SHARED_SECRET or not secrets.compare_digest(x_aegis_gateway_key, SHARED_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")


def public_state() -> dict:
    status = _state["status"]
    if status == "NOT_CONFIGURED" and storage.configured():
        status = "DISCONNECTED"
    return {**_state, "status": status, "trading": "DISABLED", "mode": "READ_ONLY", "authorization_enabled": AUTHORIZATION_ENABLED}


@app.get("/health")
def health():
    return {"status": "ok", "trading": "DISABLED"}


@app.get("/internal/status", dependencies=[Depends(internal_auth)])
def status():
    return public_state()


def tool_payload(result) -> object:
    structured=getattr(result,"structuredContent",None)
    if structured is not None: return structured
    values = []
    for item in result.content:
        value = getattr(item, "text", None)
        if value is None:
            continue
        try:
            values.append(json.loads(value))
        except (TypeError, json.JSONDecodeError):
            values.append(value)
    return values[0] if len(values) == 1 else values


class MarketDataRequest(BaseModel):
    tool: str = Field(min_length=3, max_length=80)
    arguments: dict = Field(default_factory=dict)


@app.post("/internal/market-data", dependencies=[Depends(internal_auth)])
async def market_data(payload: MarketDataRequest):
    if payload.tool not in MARKET_DATA_TOOLS:
        raise HTTPException(status_code=403, detail="Tool is not an approved public market-data read")
    if len(json.dumps(payload.arguments, separators=(",", ":"))) > 8192:
        raise HTTPException(status_code=422, detail="Market-data arguments are too large")
    if contains_sensitive_argument(payload.arguments):
        raise HTTPException(status_code=422, detail="Credentials are prohibited in market-data arguments")

    async def no_redirect(_: str) -> None:
        raise RuntimeError("Robinhood reauthorization is required")

    async def no_callback() -> tuple[str, str | None]:
        raise RuntimeError("Robinhood reauthorization is required")

    provider = OAuthClientProvider(
        server_url=MCP_URL,
        client_metadata=OAuthClientMetadata(
            client_name="Aegis Alpha Read-Only Gateway",
            redirect_uris=[AnyUrl(OAUTH_REDIRECT_URI)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="internal",
        ),
        storage=storage,
        redirect_handler=no_redirect,
        callback_handler=no_callback,
    )
    try:
        async with httpx.AsyncClient(auth=provider, follow_redirects=True, timeout=30) as client:
            async with streamable_http_client(MCP_URL, http_client=client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await call_read_only_tool(session, payload.tool, payload.arguments)
                    if result.isError:
                        raise RuntimeError("Robinhood market-data tool failed")
                    return {"tool": payload.tool, "data": tool_payload(result), "trading": "DISABLED"}
    except Exception:
        raise HTTPException(status_code=502, detail="Robinhood market-data request failed") from None


@app.get("/internal/market-data/capabilities", dependencies=[Depends(internal_auth)])
async def market_data_capabilities():
    async def no_redirect(_: str) -> None: raise RuntimeError("Robinhood reauthorization is required")
    async def no_callback() -> tuple[str, str | None]: raise RuntimeError("Robinhood reauthorization is required")
    provider=OAuthClientProvider(server_url=MCP_URL,client_metadata=OAuthClientMetadata(client_name="Aegis Alpha Read-Only Gateway",redirect_uris=[AnyUrl(OAUTH_REDIRECT_URI)],grant_types=["authorization_code","refresh_token"],response_types=["code"],scope="internal"),storage=storage,redirect_handler=no_redirect,callback_handler=no_callback)
    try:
        async with httpx.AsyncClient(auth=provider,follow_redirects=True,timeout=30) as client:
            async with streamable_http_client(MCP_URL,http_client=client) as (read,write,_):
                async with ClientSession(read,write) as session:
                    await session.initialize(); tools=await session.list_tools()
                    return {"tools":[{"name":tool.name,"description":tool.description,"input_schema":tool.inputSchema} for tool in tools.tools if tool.name in MARKET_DATA_TOOLS],"trading":"DISABLED"}
    except Exception: raise HTTPException(status_code=502,detail="Robinhood capability discovery failed") from None

async def connect_and_validate() -> None:
    global _auth_url, _callback

    async def redirect_handler(url: str) -> None:
        if _auth_url and not _auth_url.done():
            _auth_url.set_result(validate_authorization_url(url))

    async def callback_handler() -> tuple[str, str | None]:
        if _callback is None:
            raise RuntimeError("OAuth callback state is unavailable")
        return await asyncio.wait_for(_callback, timeout=600)

    provider = OAuthClientProvider(
        # OAuth protected-resource metadata identifies the full MCP URL as the
        # RFC 8707 resource. Using only the origin fails the SDK's resource
        # binding validation before browser authorization can begin.
        server_url=MCP_URL,
        client_metadata=OAuthClientMetadata(
            client_name="Aegis Alpha Read-Only Gateway",
            redirect_uris=[AnyUrl(OAUTH_REDIRECT_URI)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="internal",
        ),
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )
    try:
        async with httpx.AsyncClient(auth=provider, follow_redirects=True, timeout=30) as client:
            async with streamable_http_client(MCP_URL, http_client=client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    allowed = names & READ_ONLY_TOOLS
                    blocked = names - allowed
                    if not {"get_accounts", "get_portfolio"}.issubset(allowed):
                        raise RuntimeError("Required read-only Robinhood tools were not advertised")
                    result = await call_read_only_tool(session, "get_accounts", {})
                    if result.isError:
                        raise RuntimeError("Read-only account synchronization failed")
                    _state.update(status="CONNECTED", detail="Official MCP authorized; mutation tools blocked", last_sync_at=datetime.now(UTC).isoformat(), allowed_tools=len(allowed), blocked_tools=len(blocked))
    except Exception:
        _state.update(status="ERROR", detail="Authorization or read-only validation failed")
        raise


@app.post("/internal/connect/start", dependencies=[Depends(internal_auth)])
async def connect_start():
    global _flow_task, _auth_url, _callback, _completion_nonce
    if not AUTHORIZATION_ENABLED:
        raise HTTPException(status_code=403, detail="Broker authorization is disabled in this environment")
    if _flow_task and not _flow_task.done():
        raise HTTPException(status_code=409, detail="Authorization is already in progress")
    loop = asyncio.get_running_loop()
    _auth_url = loop.create_future()
    _callback = loop.create_future()
    _completion_nonce = secrets.token_urlsafe(32)
    _state.update(status="AUTHORIZING", detail="Waiting for browser authorization")
    _flow_task = asyncio.create_task(connect_and_validate())
    done, _ = await asyncio.wait(
        {_auth_url, _flow_task}, timeout=30, return_when=asyncio.FIRST_COMPLETED
    )
    if _auth_url in done:
        return {"authorization_url": _auth_url.result(), "completion_nonce": _completion_nonce, "status": "AUTHORIZING"}
    if _flow_task in done:
        try:
            _flow_task.result()
        except Exception:
            raise HTTPException(
                status_code=502, detail="Unable to validate Robinhood authorization"
            ) from None
        return {"authorization_url": None, "status": "CONNECTED"}
    _flow_task.cancel()
    _state.update(status="ERROR", detail="Robinhood did not provide an authorization URL")
    raise HTTPException(
        status_code=502, detail="Unable to start Robinhood authorization"
    )


class CallbackRelay(BaseModel):
    callback_url: str = Field(min_length=20, max_length=4096)
    completion_nonce: str = Field(min_length=32, max_length=128)


@app.post("/api/broker/robinhood/oauth/complete")
async def oauth_complete(payload: CallbackRelay, request: Request):
    global _completion_nonce
    if request.headers.get("origin") != AEGIS_UI_URL:
        raise HTTPException(status_code=403, detail="Untrusted completion origin")
    if not _completion_nonce or not secrets.compare_digest(payload.completion_nonce, _completion_nonce):
        raise HTTPException(status_code=403, detail="Invalid or expired completion request")
    try:
        code, state = parse_loopback_callback(payload.callback_url)
    except PermissionError:
        _completion_nonce = None
        _state.update(status="ERROR", detail="Robinhood authorization was denied")
        raise HTTPException(status_code=400, detail="Robinhood authorization was denied")
    except ValueError:
        raise HTTPException(status_code=422, detail="Paste the complete Robinhood localhost callback URL") from None
    if _callback is None or _callback.done() or _flow_task is None:
        raise HTTPException(status_code=400, detail="No active authorization request")
    _completion_nonce = None
    _callback.set_result((code, state))
    try:
        await asyncio.wait_for(asyncio.shield(_flow_task), timeout=45)
    except Exception:
        raise HTTPException(status_code=502, detail="Robinhood authorization validation failed") from None
    return public_state()


@app.get("/api/broker/robinhood/oauth/callback")
async def oauth_callback(code: str | None = Query(default=None), state: str | None = Query(default=None), error: str | None = Query(default=None)):
    if not AUTHORIZATION_ENABLED:
        raise HTTPException(status_code=403, detail="Broker authorization is disabled in this environment")
    if error:
        _state.update(status="ERROR", detail="Robinhood authorization was denied")
        raise HTTPException(status_code=400, detail="Robinhood authorization was denied")
    if not code or _callback is None or _callback.done():
        raise HTTPException(status_code=400, detail="No active authorization request")
    _callback.set_result((code, state))
    return RedirectResponse(url=f"{AEGIS_UI_URL}/system?robinhood=authorized", status_code=303)


@app.post("/internal/disconnect", dependencies=[Depends(internal_auth)])
async def disconnect():
    global _flow_task, _auth_url, _callback, _completion_nonce
    if _flow_task and not _flow_task.done():
        _flow_task.cancel()
        with suppress(asyncio.CancelledError):
            await _flow_task
    for pending in (_auth_url, _callback):
        if pending and not pending.done():
            pending.cancel()
    _flow_task = None
    _auth_url = None
    _callback = None
    _completion_nonce = None
    storage.clear()
    _state.update(status="NOT_CONFIGURED", detail="Authorization removed", last_sync_at=None, allowed_tools=0, blocked_tools=0)
    return public_state()

# Phase 9 account synchronization is deliberately bounded to immutable reads.
ACCOUNT_SNAPSHOT_TOOLS = (
    "get_portfolio", "get_equity_positions", "get_equity_tax_lots", "get_equity_orders",
    "get_option_positions", "get_option_orders", "get_crypto_positions", "get_crypto_orders",
    "get_realized_pnl", "get_pnl_trade_history",
)

def _records(value: object) -> list[dict]:
    if isinstance(value, list): return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("accounts", "results", "items", "data"):
            if key in value:
                rows=_records(value[key])
                if rows:return rows
        return [value]
    return []

def _account_number(row: dict) -> str | None:
    for key in ("account_number", "account_id", "number"):
        value=row.get(key)
        if isinstance(value,(str,int)) and str(value):return str(value)
    return None

def _opaque(value: object) -> str:
    return "ref_"+hmac.new(SHARED_SECRET.encode(),str(value).encode(),hashlib.sha256).hexdigest()[:24]

def _sanitize(value: object, key: str="") -> object:
    lower=key.lower()
    if lower in SENSITIVE_ARGUMENT_KEYS:return "<redacted>"
    if isinstance(value,dict):return {str(k):_sanitize(v,str(k)) for k,v in value.items() if str(k).lower() not in SENSITIVE_ARGUMENT_KEYS}
    if isinstance(value,list):return [_sanitize(v,key) for v in value]
    if value is not None and ("account" in lower or lower in {"id","order_id","position_id","instrument_id","url"}):return _opaque(value)
    return value

async def _account_snapshot_session(session: ClientSession,selected_account_ref:str) -> dict:
    advertised={tool.name:tool for tool in (await session.list_tools()).tools}
    account_result=await call_read_only_tool(session,"get_accounts",{})
    if account_result.isError:raise RuntimeError("Account read failed")
    accounts=_records(tool_payload(account_result))
    output=[]
    for account in accounts:
        number=_account_number(account)
        if not number or not secrets.compare_digest(_opaque(number),selected_account_ref):continue
        datasets={};failures=[]
        for name in ACCOUNT_SNAPSHOT_TOOLS:
            tool=advertised.get(name)
            if tool is None:continue
            schema=tool.inputSchema or {};required=schema.get("required",[]);properties=schema.get("properties",{})
            args={}
            for candidate in ("account_number","account_id"):
                if candidate in properties:args[candidate]=number;break
            if any(item not in args for item in required):
                failures.append({"tool":name,"code":"UNSUPPORTED_REQUIRED_ARGUMENT"});continue
            try:
                result=await call_read_only_tool(session,name,args)
                if result.isError:failures.append({"tool":name,"code":"READ_FAILED"})
                else:
                    safe=_sanitize(tool_payload(result))
                    if len(json.dumps(safe,separators=(",",":"),default=str))>1_000_000:failures.append({"tool":name,"code":"RESPONSE_TOO_LARGE"})
                    else:datasets[name]=safe
            except Exception:failures.append({"tool":name,"code":"READ_FAILED"})
        output.append({"account_ref":_opaque(number),"datasets":datasets,"failures":failures})
    if not output:raise RuntimeError("No readable brokerage accounts")
    for account in output:
        for required in ("get_portfolio","get_equity_positions","get_equity_orders"):
            if required not in advertised:account["failures"].append({"tool":required,"code":"NOT_ADVERTISED"})
            elif required not in account["datasets"] and not any(x["tool"]==required for x in account["failures"]):account["failures"].append({"tool":required,"code":"READ_FAILED"})
    return {"status":"COMPLETE","provider":"robinhood","observed_at":datetime.now(UTC).isoformat(),"accounts":output,"trading":"DISABLED","mode":"READ_ONLY"}

class AccountSnapshotRequest(BaseModel):
    selected_account_ref: str = Field(pattern=r"^ref_[0-9a-f]{24}$")

@app.post("/internal/account-snapshot",dependencies=[Depends(internal_auth)])
async def account_snapshot(payload: AccountSnapshotRequest):
    async def no_redirect(_:str)->None:raise RuntimeError("Robinhood reauthorization is required")
    async def no_callback()->tuple[str,str|None]:raise RuntimeError("Robinhood reauthorization is required")
    provider=OAuthClientProvider(server_url=MCP_URL,client_metadata=OAuthClientMetadata(client_name="Aegis Alpha Read-Only Gateway",redirect_uris=[AnyUrl(OAUTH_REDIRECT_URI)],grant_types=["authorization_code","refresh_token"],response_types=["code"],scope="internal"),storage=storage,redirect_handler=no_redirect,callback_handler=no_callback)
    try:
        async with httpx.AsyncClient(auth=provider,follow_redirects=True,timeout=30) as client:
            async with streamable_http_client(MCP_URL,http_client=client) as (read,write,_):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    snapshot=await _account_snapshot_session(session,payload.selected_account_ref)
                    _state.update(status="CONNECTED",detail="Official MCP read-only account snapshot verified",last_sync_at=snapshot["observed_at"])
                    return snapshot
    except Exception:
        raise HTTPException(status_code=502,detail="Robinhood read-only account synchronization failed") from None
