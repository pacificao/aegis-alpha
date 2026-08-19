import time
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

import redis
import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
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
from .models import BrokerConnectionConfig, DataRecord, DevelopmentActivity, Instrument, LabRun, LabTrade, OperatorPreference, Phase, IntelligenceArtifact, IntelligenceReview, PaperAccount, PaperFill, PaperOrder, PaperPosition, RiskAssessment, RiskControlState, RiskPolicy, StrategyDecision, StrategyScenario, StrategyVersion, Task, TaskStatus
from .schemas import DataIngestRequest, IntelligenceArtifactCreate, IntelligenceReviewCreate, PaperOrderCreate, LabBacktestRequest, OperatorPreferenceOut, OperatorPreferenceUpdate, PhaseOut, RiskAssessmentRequest, RiskControlUpdate, RiskPolicyCreate, RobinhoodConfigOut, RobinhoodConfigUpdate, ScenarioCreate, ScenarioOut, RobinhoodDataIngestRequest, ScenarioUpdate, StrategyEvaluationRequest, StrategyVersionCreate, TaskOut, TaskUpdate
from .data.cache import DataCache
from .data.calendar import sessions
from .data.providers import ProviderError
from .data.service import ingest as ingest_data, ingest_robinhood, status as data_service_status
from .seed import seed_roadmap
from .strategy_engine import canonical_checksum, evaluate
from .lab.service import run_backtest, serialize_run
from .risk.service import assess as assess_risk, serialize as serialize_risk
from .intelligence import validate_artifact, consensus
from .paper.service import execute as execute_paper, snapshot as paper_snapshot

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
    return {"username": principal.username, "csrf_token": principal.csrf_token, "session_idle_seconds": settings.session_idle_ttl_seconds, "session_absolute_seconds": settings.session_ttl_seconds, "cookie_security": "HttpOnly; SameSite=Strict; Secure" if settings.is_secure_cookie else "HttpOnly; SameSite=Strict"}


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
    return {"version": settings.aegis_version, "environment": settings.aegis_env, "current_phase": 8, "overall_completion": round(complete * 100 / len(tasks)) if tasks else 0, "backend": "HEALTHY", "postgresql": postgres, "redis": redis_status, "robinhood": BrokerGatewayClient(settings).status()["status"], "trading": "DISABLED", "uptime_seconds": round(time.monotonic() - started_at)}


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
def activity(limit: int = Query(default=20, ge=1, le=100), _: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.scalars(select(DevelopmentActivity).order_by(DevelopmentActivity.created_at.desc()).limit(limit)).all()
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


@app.get("/api/portfolio")
def portfolio(_: Principal = Depends(current_principal)):
    broker = BrokerGatewayClient(settings).status()
    return {"broker": "Robinhood", "connection": broker["status"], "mode": "READ_ONLY", "holdings_available": False, "positions": [], "detail": "Portfolio holdings synchronization belongs to Phase 9; Phase 2 exposes connection state only.", "trading": "DISABLED"}


@app.get("/api/scenarios", response_model=list[ScenarioOut])
def scenarios(_: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return db.scalars(select(StrategyScenario).order_by(StrategyScenario.updated_at.desc())).all()


@app.post("/api/scenarios", response_model=ScenarioOut, status_code=201)
def create_scenario(payload: ScenarioCreate, principal: Principal = Depends(csrf_protected), db: Session = Depends(get_db)):
    scenario = StrategyScenario(**payload.model_dump())
    db.add(scenario)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A scenario with that name already exists") from None
    db.add(DevelopmentActivity(actor=principal.username, action="scenario_created", entity_type="strategy_scenario", entity_id=scenario.id, detail=f"Created research-only scenario: {scenario.name}"))
    db.commit()
    db.refresh(scenario)
    return scenario


@app.patch("/api/scenarios/{scenario_id}", response_model=ScenarioOut)
def update_scenario(scenario_id: int, payload: ScenarioUpdate, principal: Principal = Depends(csrf_protected), db: Session = Depends(get_db)):
    scenario = db.get(StrategyScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    for key, value in payload.model_dump().items():
        setattr(scenario, key, value)
    db.add(DevelopmentActivity(actor=principal.username, action="scenario_updated", entity_type="strategy_scenario", entity_id=scenario.id, detail=f"Updated research-only scenario: {scenario.name}; lifecycle={scenario.lifecycle}"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A scenario with that name already exists") from None
    db.refresh(scenario)
    return scenario


def operator_preference(db: Session, username: str) -> OperatorPreference:
    preference = db.scalar(select(OperatorPreference).where(OperatorPreference.username == username))
    if preference is None:
        preference = OperatorPreference(username=username, compact_mode=False, page_size=20, confirm_sensitive_actions=True)
        db.add(preference)
        db.commit()
        db.refresh(preference)
    return preference


@app.get("/api/settings", response_model=OperatorPreferenceOut)
def get_preferences(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return operator_preference(db, principal.username)


@app.patch("/api/settings", response_model=OperatorPreferenceOut)
def update_preferences(payload: OperatorPreferenceUpdate, principal: Principal = Depends(csrf_protected), db: Session = Depends(get_db)):
    preference = operator_preference(db, principal.username)
    preference.compact_mode = payload.compact_mode
    preference.page_size = payload.page_size
    preference.confirm_sensitive_actions = True
    db.add(DevelopmentActivity(actor=principal.username, action="operator_preferences_updated", entity_type="operator_preference", entity_id=preference.id, detail="Updated console display preferences; sensitive-action confirmation remains required"))
    db.commit()
    db.refresh(preference)
    return preference

@app.get("/api/data/status")
def data_status(_: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    cache=DataCache(settings.redis_url,settings.data_cache_ttl_seconds)
    try:
        cached=cache.get("status")
        if cached is not None: return cached
    except redis.RedisError:
        cached=None
    value=data_service_status(db)
    try: cache.set("status",value)
    except redis.RedisError: pass
    return value

@app.get("/api/data/records")
def data_records(data_type: str | None = Query(default=None,max_length=40), symbol: str | None = Query(default=None,max_length=16), limit: int = Query(default=100,ge=1,le=1000), _: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    statement=select(DataRecord,Instrument.symbol).outerjoin(Instrument,DataRecord.instrument_id==Instrument.id).order_by(DataRecord.event_time.desc()).limit(limit)
    if data_type: statement=statement.where(DataRecord.data_type==data_type.upper())
    if symbol: statement=statement.where(Instrument.symbol==symbol.upper())
    rows=db.execute(statement).all()
    return [{"id":record.id,"symbol":record_symbol,"data_type":record.data_type,"event_time":record.event_time,"payload":record.payload,"quality_status":record.quality_status,"source_url":record.source_url} for record,record_symbol in rows]

@app.get("/api/data/calendar")
def data_calendar(start: date = Query(), end: date = Query(), _: Principal = Depends(current_principal)):
    try: return sessions(start,end)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from None

@app.post("/api/data/robinhood/ingest")
def robinhood_data_ingest(payload: RobinhoodDataIngestRequest, principal: Principal = Depends(csrf_protected), db: Session = Depends(get_db)):
    run=ingest_robinhood(db,settings,payload.tool,payload.arguments,payload.symbol)
    db.add(DevelopmentActivity(actor=principal.username,action="robinhood_data_ingestion_requested",entity_type="ingestion_run",entity_id=run.id,detail=f"tool={payload.tool}; status={run.status}; accepted={run.accepted}; rejected={run.rejected}; trading=DISABLED"))
    db.commit()
    try: DataCache(settings.redis_url,settings.data_cache_ttl_seconds).invalidate()
    except redis.RedisError: pass
    if run.status=="ERROR": raise HTTPException(status_code=503,detail=run.detail)
    return {"id":run.id,"provider":"robinhood","dataset":run.dataset,"status":run.status,"accepted":run.accepted,"rejected":run.rejected,"detail":run.detail,"completed_at":run.completed_at,"trading":"DISABLED"}

@app.post("/api/data/ingest")
def data_ingest(payload: DataIngestRequest, principal: Principal = Depends(csrf_protected), db: Session = Depends(get_db)):
    try: run=ingest_data(db,settings,payload.provider,payload.dataset,payload.symbol,payload.series_id,payload.cik)
    except ProviderError as exc: raise HTTPException(status_code=422,detail=str(exc)) from None
    db.add(DevelopmentActivity(actor=principal.username,action="data_ingestion_requested",entity_type="ingestion_run",entity_id=run.id,detail=f"provider={payload.provider}; dataset={payload.dataset}; status={run.status}; accepted={run.accepted}; rejected={run.rejected}")); db.commit()
    try: DataCache(settings.redis_url,settings.data_cache_ttl_seconds).invalidate()
    except redis.RedisError: pass
    if run.status=="ERROR": raise HTTPException(status_code=503,detail=run.detail)
    return {"id":run.id,"provider":payload.provider,"dataset":run.dataset,"status":run.status,"accepted":run.accepted,"rejected":run.rejected,"detail":run.detail,"completed_at":run.completed_at,"trading":"DISABLED"}

@app.get("/api/strategy-engine/scenarios/{scenario_id}/versions")
def strategy_versions(scenario_id: int, _: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if db.get(StrategyScenario,scenario_id) is None: raise HTTPException(status_code=404,detail="Scenario not found")
    rows=db.scalars(select(StrategyVersion).where(StrategyVersion.scenario_id==scenario_id).order_by(StrategyVersion.version.desc())).all()
    return [{"id":row.id,"scenario_id":row.scenario_id,"version":row.version,"specification":row.specification,"checksum":row.checksum,"created_by":row.created_by,"created_at":row.created_at,"trading":"DISABLED"} for row in rows]

@app.post("/api/strategy-engine/scenarios/{scenario_id}/versions",status_code=201)
def create_strategy_version(scenario_id: int,payload: StrategyVersionCreate,principal: Principal = Depends(csrf_protected),db: Session = Depends(get_db)):
    scenario=db.get(StrategyScenario,scenario_id)
    if scenario is None: raise HTTPException(status_code=404,detail="Scenario not found")
    specification=payload.specification.model_dump(mode="json")
    checksum=canonical_checksum(specification)
    duplicate=db.scalar(select(StrategyVersion).where(StrategyVersion.scenario_id==scenario_id,StrategyVersion.checksum==checksum))
    if duplicate is not None: raise HTTPException(status_code=409,detail=f"Identical immutable version already exists as v{duplicate.version}")
    version=(db.scalar(select(func.max(StrategyVersion.version)).where(StrategyVersion.scenario_id==scenario_id)) or 0)+1
    row=StrategyVersion(scenario_id=scenario_id,version=version,specification=specification,checksum=checksum,created_by=principal.username)
    db.add(row); db.flush()
    db.add(DevelopmentActivity(actor=principal.username,action="strategy_version_created",entity_type="strategy_version",entity_id=row.id,detail=f"Created immutable research specification v{version}; trading=DISABLED"))
    db.commit(); db.refresh(row)
    return {"id":row.id,"scenario_id":row.scenario_id,"version":row.version,"specification":row.specification,"checksum":row.checksum,"created_by":row.created_by,"created_at":row.created_at,"trading":"DISABLED"}

@app.post("/api/strategy-engine/versions/{version_id}/evaluate",status_code=201)
def evaluate_strategy_version(version_id: int,payload: StrategyEvaluationRequest,principal: Principal = Depends(csrf_protected),db: Session = Depends(get_db)):
    version=db.get(StrategyVersion,version_id)
    if version is None: raise HTTPException(status_code=404,detail="Strategy version not found")
    result=evaluate(version.specification,payload.symbol,payload.facts,payload.as_of)
    row=StrategyDecision(version_id=version.id,symbol=result["symbol"],as_of=result["as_of"],decision=result["decision"],reason_codes=result["reason_codes"],proposed_weight_pct=result["proposed_weight_pct"],inputs=result["inputs"])
    db.add(row); db.flush()
    db.add(DevelopmentActivity(actor=principal.username,action="strategy_research_evaluated",entity_type="strategy_decision",entity_id=row.id,detail=f"v{version.version} {row.symbol}={row.decision}; non-executable; trading=DISABLED"))
    db.commit(); db.refresh(row)
    return {"id":row.id,"version_id":version.id,**result}

@app.get("/api/strategy-engine/versions/{version_id}/decisions")
def strategy_decisions(version_id: int,limit: int=Query(default=50,ge=1,le=500),_: Principal = Depends(current_principal),db: Session = Depends(get_db)):
    if db.get(StrategyVersion,version_id) is None: raise HTTPException(status_code=404,detail="Strategy version not found")
    rows=db.scalars(select(StrategyDecision).where(StrategyDecision.version_id==version_id).order_by(StrategyDecision.created_at.desc()).limit(limit)).all()
    return [{"id":row.id,"version_id":row.version_id,"symbol":row.symbol,"as_of":row.as_of,"decision":row.decision,"reason_codes":row.reason_codes,"proposed_weight_pct":row.proposed_weight_pct,"inputs":row.inputs,"risk_authorized":False,"executable":False,"trading":"DISABLED","created_at":row.created_at} for row in rows]

@app.get("/api/lab/readiness")
def lab_readiness(_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    bars=db.scalar(select(func.count()).select_from(DataRecord).where(DataRecord.data_type=="OHLCV",DataRecord.quality_status!="REJECTED")) or 0
    actions=db.scalar(select(func.count()).select_from(DataRecord).where(DataRecord.data_type=="CORPORATE_ACTION",DataRecord.quality_status!="REJECTED")) or 0
    versions=db.scalar(select(func.count()).select_from(StrategyVersion)) or 0;runs=db.scalar(select(func.count()).select_from(LabRun)) or 0
    return {"historical_bars":bars,"corporate_actions":actions,"strategy_versions":versions,"completed_runs":runs,"ready":bars>1 and versions>0,"next_requirement":None if bars>1 and versions>0 else "Ingest normalized OHLCV and create a strategy version","trading":"DISABLED"}

@app.post("/api/lab/backtests",status_code=201)
def create_lab_backtest(payload:LabBacktestRequest,principal:Principal=Depends(csrf_protected),db:Session=Depends(get_db)):
    try:run=run_backtest(db,payload,principal.username)
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from None
    return serialize_run(run,include_curve=True)

@app.get("/api/lab/backtests")
def lab_backtests(limit:int=Query(default=25,ge=1,le=100),_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    return [serialize_run(run) for run in db.scalars(select(LabRun).order_by(LabRun.created_at.desc()).limit(limit)).all()]

@app.get("/api/lab/backtests/{run_id}")
def lab_backtest(run_id:int,_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    run=db.get(LabRun,run_id)
    if run is None:raise HTTPException(status_code=404,detail="Lab run not found")
    return serialize_run(run,include_curve=True)

@app.get("/api/lab/backtests/{run_id}/trades")
def lab_trades(run_id:int,limit:int=Query(default=500,ge=1,le=5000),_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    if db.get(LabRun,run_id) is None:raise HTTPException(status_code=404,detail="Lab run not found")
    rows=db.scalars(select(LabTrade).where(LabTrade.run_id==run_id).order_by(LabTrade.entry_day).limit(limit)).all()
    return [{"id":row.id,"symbol":row.symbol,"entry_day":row.entry_day,"exit_day":row.exit_day,"shares":row.shares,"entry_price":row.entry_price,"exit_price":row.exit_price,"dividends":row.dividends,"costs":row.costs,"pnl":row.pnl,"return_pct":row.return_pct,"holding_days":row.holding_days,"exit_reason":row.exit_reason,"max_drawdown_pct":row.max_drawdown_pct,"trading":"DISABLED"} for row in rows]


@app.get("/api/risk/status")
def risk_status(_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    policy=db.scalar(select(RiskPolicy).where(RiskPolicy.active.is_(True)).order_by(RiskPolicy.version.desc()));controls=db.get(RiskControlState,1)
    if policy is None or controls is None:raise HTTPException(status_code=503,detail="Risk controls are not initialized")
    counts=dict(db.execute(select(RiskAssessment.outcome,func.count()).group_by(RiskAssessment.outcome)).all())
    return {"policy":{"id":policy.id,"version":policy.version,"name":policy.name,"configuration":policy.configuration,"checksum":policy.checksum},"controls":{"kill_switch_engaged":controls.kill_switch_engaged,"circuit_breaker_engaged":controls.circuit_breaker_engaged,"reason":controls.reason,"updated_by":controls.updated_by,"updated_at":controls.updated_at},"assessment_counts":counts,"execution_available":False,"trading":"DISABLED"}

@app.post("/api/risk/assessments",status_code=201)
def create_risk_assessment(payload:RiskAssessmentRequest,principal:Principal=Depends(csrf_protected),db:Session=Depends(get_db)):
    if payload.strategy_decision_id is not None and db.get(StrategyDecision,payload.strategy_decision_id) is None:raise HTTPException(status_code=404,detail="Strategy decision not found")
    try:row=assess_risk(db,payload,principal.username)
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from None
    return serialize_risk(row)

@app.get("/api/risk/assessments")
def risk_assessments(limit:int=Query(default=50,ge=1,le=500),_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    return [serialize_risk(row) for row in db.scalars(select(RiskAssessment).order_by(RiskAssessment.created_at.desc()).limit(limit)).all()]

@app.patch("/api/risk/controls")
def update_risk_controls(payload:RiskControlUpdate,principal:Principal=Depends(csrf_protected),db:Session=Depends(get_db)):
    controls=db.get(RiskControlState,1)
    if controls is None:raise HTTPException(status_code=503,detail="Risk controls are not initialized")
    controls.kill_switch_engaged=payload.kill_switch_engaged;controls.circuit_breaker_engaged=payload.circuit_breaker_engaged;controls.reason=payload.reason;controls.updated_by=principal.username
    db.add(DevelopmentActivity(actor=principal.username,action="risk_controls_updated",entity_type="risk_control_state",entity_id=1,detail=f"kill_switch={payload.kill_switch_engaged}; circuit_breaker={payload.circuit_breaker_engaged}; trading=DISABLED"));db.commit();db.refresh(controls)
    return {"kill_switch_engaged":controls.kill_switch_engaged,"circuit_breaker_engaged":controls.circuit_breaker_engaged,"reason":controls.reason,"updated_by":controls.updated_by,"updated_at":controls.updated_at,"trading":"DISABLED"}


@app.post("/api/risk/policies",status_code=201)
def create_risk_policy(payload:RiskPolicyCreate,principal:Principal=Depends(csrf_protected),db:Session=Depends(get_db)):
    configuration=payload.configuration.model_dump(mode="json");checksum=canonical_checksum(configuration)
    if db.scalar(select(RiskPolicy).where(RiskPolicy.checksum==checksum)) is not None:raise HTTPException(status_code=409,detail="Identical risk policy already exists")
    for active in db.scalars(select(RiskPolicy).where(RiskPolicy.active.is_(True))).all():active.active=False
    version=(db.scalar(select(func.max(RiskPolicy.version))) or 0)+1;row=RiskPolicy(version=version,name=payload.name,configuration=configuration,checksum=checksum,active=True,created_by=principal.username);db.add(row);db.flush()
    db.add(DevelopmentActivity(actor=principal.username,action="risk_policy_created",entity_type="risk_policy",entity_id=row.id,detail=f"Created immutable risk policy v{version}; execution unavailable; trading=DISABLED"));db.commit();db.refresh(row)
    return {"id":row.id,"version":row.version,"name":row.name,"configuration":row.configuration,"checksum":row.checksum,"active":row.active,"executable":False,"trading":"DISABLED"}


def serialize_intelligence(row: IntelligenceArtifact, reviews: list[IntelligenceReview] | None = None):
    reviews=reviews or []
    governance,reason=consensus(row,reviews)
    return {"id":row.id,"artifact_type":row.artifact_type,"subject":row.subject,"thesis":row.thesis,"recommendation":row.recommendation,"confidence":row.confidence,"evidence":row.evidence,"analysis":row.analysis,"checksum":row.checksum,"status":row.status,"human_review_required":governance!="ELIGIBLE_FOR_RISK_REVIEW","governance":governance,"governance_reason":reason,"reviews":[{"id":r.id,"reviewer":r.reviewer,"verdict":r.verdict,"confidence":r.confidence,"rationale":r.rationale,"evidence_checksum":r.evidence_checksum,"independent":r.independent,"created_at":r.created_at} for r in reviews],"risk_authorized":False,"executable":False,"trading":"DISABLED","created_by":row.created_by,"created_at":row.created_at}

@app.get("/api/intelligence/status")
def intelligence_status(_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    counts=dict(db.execute(select(IntelligenceArtifact.artifact_type,func.count()).group_by(IntelligenceArtifact.artifact_type)).all())
    return {"artifact_counts":counts,"supported_types":["STRATEGY_CREATION","STRATEGY_CRITIQUE","MARKET_REGIME","NEWS_ANALYSIS","FUNDAMENTAL_ANALYSIS","PARAMETER_RESEARCH","POST_TRADE_REVIEW","ANOMALY_DETECTION","PREMARKET_BRIEFING","POSTMARKET_DIGEST","ATTENTION_ALERT"],"strategy_council":"AVAILABLE","independent_verification":"AVAILABLE","model_provider":"PROVIDER_NEUTRAL","risk_authority":False,"execution_available":False,"trading":"DISABLED"}

@app.post("/api/intelligence/artifacts",status_code=201)
def create_intelligence_artifact(payload:IntelligenceArtifactCreate,principal:Principal=Depends(csrf_protected),db:Session=Depends(get_db)):
    snapshot,checksum,status,reasons=validate_artifact(payload)
    duplicate=db.scalar(select(IntelligenceArtifact).where(IntelligenceArtifact.checksum==checksum))
    if duplicate is not None:raise HTTPException(status_code=409,detail=f"Identical intelligence artifact already exists as {duplicate.id}")
    row=IntelligenceArtifact(**snapshot,checksum=checksum,status=status,human_review_required=True,risk_authorized=False,created_by=principal.username);db.add(row);db.flush()
    db.add(DevelopmentActivity(actor=principal.username,action="intelligence_artifact_created",entity_type="intelligence_artifact",entity_id=row.id,detail=f"type={row.artifact_type}; status={status}; evidence={len(row.evidence)}; reasons={','.join(reasons) or 'NONE'}; risk_authorized=false; trading=DISABLED"));db.commit();db.refresh(row)
    return serialize_intelligence(row)

@app.get("/api/intelligence/artifacts")
def intelligence_artifacts(limit:int=Query(default=50,ge=1,le=500),_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    rows=db.scalars(select(IntelligenceArtifact).order_by(IntelligenceArtifact.created_at.desc()).limit(limit)).all();result=[]
    for row in rows:result.append(serialize_intelligence(row,db.scalars(select(IntelligenceReview).where(IntelligenceReview.artifact_id==row.id).order_by(IntelligenceReview.created_at)).all()))
    return result

@app.post("/api/intelligence/artifacts/{artifact_id}/reviews",status_code=201)
def create_intelligence_review(artifact_id:int,payload:IntelligenceReviewCreate,principal:Principal=Depends(csrf_protected),db:Session=Depends(get_db)):
    artifact=db.get(IntelligenceArtifact,artifact_id)
    if artifact is None:raise HTTPException(status_code=404,detail="Intelligence artifact not found")
    if payload.evidence_checksum!=artifact.checksum:raise HTTPException(status_code=409,detail="Review evidence checksum does not match immutable artifact")
    if db.scalar(select(IntelligenceReview).where(IntelligenceReview.artifact_id==artifact_id,IntelligenceReview.reviewer==payload.reviewer)) is not None:raise HTTPException(status_code=409,detail="Reviewer already assessed this artifact")
    row=IntelligenceReview(artifact_id=artifact_id,**payload.model_dump(),independent=True,created_by=principal.username);db.add(row);db.flush();reviews=db.scalars(select(IntelligenceReview).where(IntelligenceReview.artifact_id==artifact_id)).all();governance,reason=consensus(artifact,reviews);artifact.status=governance;artifact.human_review_required=governance!="ELIGIBLE_FOR_RISK_REVIEW"
    db.add(DevelopmentActivity(actor=principal.username,action="intelligence_review_recorded",entity_type="intelligence_artifact",entity_id=artifact.id,detail=f"reviewer={row.reviewer}; verdict={row.verdict}; governance={governance}; reason={reason}; risk_authorized=false; trading=DISABLED"));db.commit();db.refresh(artifact)
    return serialize_intelligence(artifact,db.scalars(select(IntelligenceReview).where(IntelligenceReview.artifact_id==artifact_id).order_by(IntelligenceReview.created_at)).all())

@app.get("/api/simulator/status")
def simulator_status(_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    value=paper_snapshot(db);value["order_count"]=db.scalar(select(func.count()).select_from(PaperOrder)) or 0;return value

@app.post("/api/simulator/orders",status_code=201)
def create_paper_order(payload:PaperOrderCreate,principal:Principal=Depends(csrf_protected),db:Session=Depends(get_db)):
    try:order=execute_paper(db,payload.risk_assessment_id,payload.quote_record_id,principal.username)
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from None
    fill=db.scalar(select(PaperFill).where(PaperFill.order_id==order.id))
    return {"id":order.id,"risk_assessment_id":order.risk_assessment_id,"quote_record_id":order.quote_record_id,"symbol":order.symbol,"side":order.side,"quantity":order.quantity,"status":order.status,"reason":order.reason,"fill":{"id":fill.id,"price":fill.price,"quantity":fill.quantity,"commission":fill.commission,"slippage_bps":fill.slippage_bps,"filled_at":fill.filled_at},"environment":"PAPER","broker_called":False,"executable_live":False,"trading":"DISABLED","created_at":order.created_at}

@app.get("/api/simulator/orders")
def paper_orders(limit:int=Query(default=100,ge=1,le=500),_:Principal=Depends(current_principal),db:Session=Depends(get_db)):
    rows=db.scalars(select(PaperOrder).order_by(PaperOrder.created_at.desc()).limit(limit)).all();result=[]
    for order in rows:
        fill=db.scalar(select(PaperFill).where(PaperFill.order_id==order.id));result.append({"id":order.id,"risk_assessment_id":order.risk_assessment_id,"quote_record_id":order.quote_record_id,"symbol":order.symbol,"side":order.side,"quantity":order.quantity,"status":order.status,"reason":order.reason,"fill":{"price":fill.price,"quantity":fill.quantity,"commission":fill.commission,"slippage_bps":fill.slippage_bps,"filled_at":fill.filled_at} if fill else None,"environment":"PAPER","broker_called":False,"executable_live":False,"trading":"DISABLED","created_at":order.created_at})
    return result
