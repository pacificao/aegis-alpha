"""Aegis-owned Robinhood OAuth client and read-only MCP enforcement gateway."""
import secrets
import asyncio
import os
from datetime import UTC, datetime

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from .policy import READ_ONLY_TOOLS, enforce_tool_allowed, validate_authorization_url
from .storage import EncryptedFileTokenStorage

MCP_URL = "https://agent.robinhood.com/mcp/trading"
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://aegis-alpha.pacificao.com")
CALLBACK_URL = f"{PUBLIC_BASE_URL}/api/broker/robinhood/oauth/callback"
SHARED_SECRET = os.environ.get("BROKER_GATEWAY_SHARED_SECRET", "")
AUTHORIZATION_ENABLED = os.environ.get("BROKER_AUTHORIZATION_ENABLED", "false").lower() == "true"
if not PUBLIC_BASE_URL.startswith("https://"):
    raise RuntimeError("PUBLIC_BASE_URL must use HTTPS")
if len(SHARED_SECRET) < 32:
    raise RuntimeError("BROKER_GATEWAY_SHARED_SECRET must be at least 32 characters")
storage = EncryptedFileTokenStorage(
    os.environ.get("BROKER_GATEWAY_DATA_DIR", "/var/lib/aegis-broker"),
    os.environ.get("BROKER_GATEWAY_KEY_FILE", "/run/secrets/broker_key"),
)
app = FastAPI(title="Aegis Broker Gateway", docs_url=None, redoc_url=None, openapi_url=None)
_flow_task: asyncio.Task | None = None
_auth_url: asyncio.Future | None = None
_callback: asyncio.Future | None = None
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
        server_url="https://agent.robinhood.com",
        client_metadata=OAuthClientMetadata(
            client_name="Aegis Alpha Read-Only Gateway",
            redirect_uris=[AnyUrl(CALLBACK_URL)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
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
    global _flow_task, _auth_url, _callback
    if not AUTHORIZATION_ENABLED:
        raise HTTPException(status_code=403, detail="Broker authorization is disabled in this environment")
    if _flow_task and not _flow_task.done():
        raise HTTPException(status_code=409, detail="Authorization is already in progress")
    loop = asyncio.get_running_loop()
    _auth_url = loop.create_future()
    _callback = loop.create_future()
    _state.update(status="AUTHORIZING", detail="Waiting for browser authorization")
    _flow_task = asyncio.create_task(connect_and_validate())
    done, _ = await asyncio.wait(
        {_auth_url, _flow_task}, timeout=30, return_when=asyncio.FIRST_COMPLETED
    )
    if _auth_url in done:
        return {"authorization_url": _auth_url.result(), "status": "AUTHORIZING"}
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
    return RedirectResponse(url=f"{PUBLIC_BASE_URL}/system?robinhood=authorized", status_code=303)


@app.post("/internal/disconnect", dependencies=[Depends(internal_auth)])
def disconnect():
    storage.clear()
    _state.update(status="NOT_CONFIGURED", detail="Authorization removed", last_sync_at=None, allowed_tools=0, blocked_tools=0)
    return public_state()
