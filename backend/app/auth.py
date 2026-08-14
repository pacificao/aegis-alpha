import asyncio
import hashlib
import json
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

import redis
import structlog
from fastapi import Cookie, Depends, Header, HTTPException, Request, status

from .config import Settings, get_settings

log = structlog.get_logger()
_attempts: dict[str, deque[float]] = defaultdict(deque)


@dataclass
class Principal:
    username: str
    session_id: str
    csrf_token: str


class SessionStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def create(self, username: str) -> tuple[str, str]:
        session_id = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = int(time.time())
        self.client.hset(f"session:{session_id}", mapping={"username": username, "csrf": csrf, "created_at": now})
        self.client.expire(f"session:{session_id}", min(self.settings.session_idle_ttl_seconds, self.settings.session_ttl_seconds))
        return session_id, csrf

    def get(self, session_id: str) -> dict[str, str] | None:
        data = self.client.hgetall(f"session:{session_id}")
        if not data:
            return None
        created_at = int(data.get("created_at", "0"))
        absolute_remaining = self.settings.session_ttl_seconds - (int(time.time()) - created_at)
        if created_at <= 0 or absolute_remaining <= 0:
            self.delete(session_id)
            return None
        self.client.expire(f"session:{session_id}", min(self.settings.session_idle_ttl_seconds, absolute_remaining))
        return data

    def delete(self, session_id: str) -> None:
        self.client.delete(f"session:{session_id}")


def session_store(settings: Settings = Depends(get_settings)) -> SessionStore:
    return SessionStore(settings)


def enforce_login_rate_limit(request: Request, username: str) -> None:
    source = request.client.host if request.client else "unknown"
    key = hashlib.sha256(f"{source}:{username}".encode()).hexdigest()
    now = time.monotonic()
    window = _attempts[key]
    while window and window[0] < now - 300:
        window.popleft()
    if len(window) >= 5:
        raise HTTPException(status_code=429, detail="Too many login attempts; retry later")
    window.append(now)


async def authenticate_with_pam_bridge(username: str, password: str, settings: Settings) -> bool:
    if username != "nathan":
        return False
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(settings.pam_bridge_socket), timeout=2)
        request = json.dumps({"username": username, "password": password}, separators=(",", ":")) + "\n"
        writer.write(request.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), timeout=5)
        writer.close()
        await writer.wait_closed()
        response = json.loads(raw)
        return response.get("authenticated") is True
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        log.warning("pam_bridge_unavailable", error=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from None


def current_principal(
    aegis_session: str | None = Cookie(default=None),
    store: SessionStore = Depends(session_store),
) -> Principal:
    if not aegis_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        data = store.get(aegis_session)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Session service unavailable") from None
    if not data or data.get("username") != "nathan":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return Principal(username="nathan", session_id=aegis_session, csrf_token=data["csrf"])


def csrf_protected(
    principal: Principal = Depends(current_principal),
    x_csrf_token: str | None = Header(default=None),
) -> Principal:
    if not x_csrf_token or not secrets.compare_digest(x_csrf_token, principal.csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    return principal

