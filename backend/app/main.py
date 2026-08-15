import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import redis
import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from .auth import (
    Principal,
    authenticate_with_pam_bridge,
    csrf_protected,
    current_principal,
    enforce_login_rate_limit,
    session_store,
    SessionStore,
)
from .broker import RobinhoodBrokerAdapter
from .gateway import BrokerGatewayClient
from .config import Settings, get_settings
from .database import SessionLocal, engine, get_db
from .logging import configure_logging
from .models import BrokerConnectionConfig, DevelopmentActivity, Phase, Task, TaskStatus
from .schemas import PhaseOut, RobinhoodConfigOut, RobinhoodConfigUpdate, TaskOut, TaskUpdate
from .seed import seed_roadmap

configure_logging()
log = structlog.get_logger()
started_at = time.monotonic()


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as db:
        seed_roadmap(db)
    log.info("application_started", trading_enabled=False)
    yield
    engine.dispose()


app = FastAPI(title="Aegis Alpha API", version=get_settings().aegis_version, lifespan=lifespan)
settings = get_settings()
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[x.strip() for x in settings.trusted_hosts.split(",")])
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "PATCH", "POST"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "")[:64]
    before = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info("http_request", method=request.method, path=request.url.path, status=response.status_code, duration_ms=round((time.monotonic() - before) * 1000, 2), request_id=request_id)
    return response


class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=1024)


@app.get("/health")
def health():
    return {"status": "ok", "service": "aegis-backend", "version": settings.aegis_version, "trading": "DISABLED"}


@app.post("/api/auth/login")
async def login(payload: LoginRequest, request: Request, response: Response, store: SessionStore = Depends(session_store)):
    enforce_login_rate_limit(request, payload.username)
    if not await authenticate_with_pam_bridge(payload.username, payload.password, settings):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        session_id, csrf = store.create(settings.authorized_user)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Session service unavailable") from None
    response.set_cookie(settings.auth_cookie_name, session_id, max_age=settings.session_ttl_seconds, httponly=True, secure=settings.is_secure_cookie, samesite="strict", path="/")
    return {"username": settings.authorized_user, "csrf_token": csrf, "expires_in": settings.session_ttl_seconds}


@app.post("/api/auth/logout")
def logout(response: Response, principal: Principal = Depends(csrf_protected), store: SessionStore = Depends(session_store)):
    store.delete(principal.session_id)
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return {"status": "logged_out"}


@app.get("/api/auth/me")
def me(principal: Principal = Depends(current_principal)):
    return {"username": principal.username, "csrf_token": principal.csrf_token}


def service_checks(db: Session) -> tuple[str, str]:
    try:
        db.execute(text("SELECT 1"))
        postgres = "CONNECTED"
    except Exception:
        postgres = "ERROR"
    try:
        redis.Redis.from_url(settings.redis_url).ping()
        redis_status = "CONNECTED"
    except redis.RedisError:
        redis_status = "ERROR"
    return postgres, redis_status


@app.get("/api/status")
def api_status(_: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    postgres, redis_status = service_checks(db)
    tasks = db.scalars(select(Task)).all()
    complete = sum(task.status == TaskStatus.COMPLETE for task in tasks)
    return {"version": settings.aegis_version, "environment": settings.aegis_env, "current_phase": 1, "overall_completion": round(complete * 100 / len(tasks)) if tasks else 0, "backend": "HEALTHY", "postgresql": postgres, "redis": redis_status, "robinhood": BrokerGatewayClient(settings).status()["status"], "trading": "DISABLED", "uptime_seconds": round(time.monotonic() - started_at)}


def phase_status(tasks: list[Task]) -> TaskStatus:
    statuses = {task.status for task in tasks}
    if statuses == {TaskStatus.COMPLETE}:
        return TaskStatus.COMPLETE
    if TaskStatus.BLOCKED in statuses:
        return TaskStatus.BLOCKED
    if TaskStatus.WAITING_FOR_CREDENTIALS in statuses:
        return TaskStatus.WAITING_FOR_CREDENTIALS
    if TaskStatus.IN_PROGRESS in statuses or TaskStatus.COMPLETE in statuses:
        return TaskStatus.IN_PROGRESS
    return TaskStatus.NOT_STARTED


@app.get("/api/roadmap", response_model=list[PhaseOut])
def roadmap(_: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    phases = db.scalars(select(Phase).options(selectinload(Phase.tasks)).order_by(Phase.number)).all()
    return [PhaseOut(id=p.id, number=p.number, name=p.name, description=p.description, status=phase_status(p.tasks), completion_percentage=round(sum(t.status == TaskStatus.COMPLETE for t in p.tasks) * 100 / len(p.tasks)) if p.tasks else 0, tasks=[TaskOut.model_validate(t) for t in p.tasks]) for p in phases]


@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, principal: Principal = Depends(csrf_protected), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    changed = []
    if payload.status is not None and payload.status != task.status:
        task.status = payload.status
        changed.append(f"status={payload.status.value}")
    if payload.notes is not None and payload.notes != task.notes:
        task.notes = payload.notes
        changed.append("notes updated")
    if changed:
        db.add(DevelopmentActivity(actor=principal.username, action="task_updated", entity_type="task", entity_id=task.id, detail=", ".join(changed)))
        db.commit()
        db.refresh(task)
    return task


@app.get("/api/activity")
def activity(_: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.scalars(select(DevelopmentActivity).order_by(DevelopmentActivity.created_at.desc()).limit(20)).all()
    return [{"id": row.id, "actor": row.actor, "action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id, "detail": row.detail, "created_at": row.created_at} for row in rows]


@app.get("/api/broker/status")
def broker_status(_: Principal = Depends(current_principal)):
    return BrokerGatewayClient(settings).status()


@app.get("/api/broker/robinhood/config", response_model=RobinhoodConfigOut)
def robinhood_config(_: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    config = db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider == "robinhood"))
    if config is None:
        raise HTTPException(status_code=503, detail="Robinhood configuration is not initialized")
    return RobinhoodConfigOut.model_validate(config).model_copy(update={"status": BrokerGatewayClient(settings).status()["status"]})


@app.patch("/api/broker/robinhood/config", response_model=RobinhoodConfigOut)
def update_robinhood_config(payload: RobinhoodConfigUpdate, principal: Principal = Depends(csrf_protected), db: Session = Depends(get_db)):
    config = db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider == "robinhood"))
    if config is None:
        raise HTTPException(status_code=503, detail="Robinhood configuration is not initialized")
    config.connection_name = payload.connection_name
    config.endpoint = payload.endpoint
    db.add(DevelopmentActivity(actor=principal.username, action="broker_config_updated", entity_type="broker_connection_config", entity_id=config.id, detail="Updated non-secret Robinhood MCP metadata; mode=READ_ONLY"))
    db.commit()
    db.refresh(config)
    return RobinhoodConfigOut.model_validate(config).model_copy(update={"status": BrokerGatewayClient(settings).status()["status"]})


@app.post("/api/broker/robinhood/connect")
def robinhood_connect(principal: Principal = Depends(csrf_protected), db: Session = Depends(get_db)):
    result = BrokerGatewayClient(settings).start_authorization()
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=503, detail=result.get("detail", "Broker gateway unavailable"))
    db.add(DevelopmentActivity(actor=principal.username, action="broker_authorization_started", entity_type="broker_connection_config", entity_id=1, detail="Started official Robinhood browser authorization; no credentials entered into Aegis"))
    db.commit()
    return result


@app.post("/api/broker/robinhood/disconnect")
def robinhood_disconnect(principal: Principal = Depends(csrf_protected), db: Session = Depends(get_db)):
    result = BrokerGatewayClient(settings).disconnect()
    db.add(DevelopmentActivity(actor=principal.username, action="broker_authorization_removed", entity_type="broker_connection_config", entity_id=1, detail="Removed protected Robinhood authorization material"))
    db.commit()
    return result


@app.get("/api/system")
def system(_: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    postgres, redis_status = service_checks(db)
    return {"application": "AEGIS ALPHA", "backend_version": settings.aegis_version, "environment": settings.aegis_env, "postgresql": postgres, "redis": redis_status, "uptime_seconds": round(time.monotonic() - started_at), "server_time": datetime.now(UTC), "trading": "DISABLED"}
