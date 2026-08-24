"""Governed controlled-live execution; strategies and RiskEngine remain authoritative."""
from datetime import UTC,datetime
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..gateway import BrokerGatewayClient
from ..models import BrokerConnectionConfig,BrokerSnapshot,ControlledExecutionRecord,ControlledTradeIntent,DevelopmentActivity,LiveTradingAuthorization,RiskAssessment,RiskControlState,RiskPolicy
from ..strategy_engine import canonical_checksum
from .service import reconcile

FINAL=frozenset({"SUBMITTED","PARTIALLY_FILLED","FILLED","REJECTED","RECONCILIATION_ATTENTION","UNKNOWN"})

def aware(value):
    if value is None:return datetime.min.replace(tzinfo=UTC)
    parsed=datetime.fromisoformat(str(value).replace("Z","+00:00")) if not isinstance(value,datetime) else value
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

def authorization_effective(row:LiveTradingAuthorization|None,settings,gateway:dict,now:datetime|None=None)->bool:
    now=now or datetime.now(UTC)
    return bool(settings.aegis_trading_enabled and gateway.get("execution_enabled") is True and row and row.enabled and row.expires_at and aware(row.expires_at)>now)

def serialize_authorization(row,settings,gateway):
    effective=authorization_effective(row,settings,gateway)
    return {"enabled":bool(row and row.enabled),"effective":effective,"max_order_notional":row.max_order_notional if row else 2,"authorized_by":row.authorized_by if row else None,"authorized_at":row.authorized_at if row else None,"expires_at":row.expires_at if row else None,"reason":row.reason if row else "Not initialized","backend_enabled":settings.aegis_trading_enabled,"gateway_enabled":gateway.get("execution_enabled") is True,"trading":"ENABLED" if effective else "DISABLED"}

def _attention(db,controls,record,row,code,actor):
    record.status="UNKNOWN";record.reconciliation={"status":"ATTENTION","code":code,"requires_human_attention":True};row.status="EXECUTION_ATTENTION"
    controls.circuit_breaker_engaged=True;controls.reason=f"Automatic breaker: {code}";controls.updated_by="execution-engine"
    db.add(DevelopmentActivity(actor=actor,action="controlled_execution_attention",entity_type="controlled_execution_record",entity_id=record.id,detail=f"code={code}; circuit_breaker=true; duplicate_submission_blocked=true"));db.commit()

def execute(db:Session,client:BrokerGatewayClient,settings,intent_id:int,actor:str)->dict:
    now=datetime.now(UTC);gateway=client.status();auth=db.get(LiveTradingAuthorization,1);controls=db.get(RiskControlState,1)
    if not authorization_effective(auth,settings,gateway,now):raise HTTPException(403,"Operator live authorization or execution-domain enablement is inactive")
    if not controls or controls.kill_switch_engaged or controls.circuit_breaker_engaged:raise HTTPException(409,"Risk controls block execution")
    row=db.scalar(select(ControlledTradeIntent).where(ControlledTradeIntent.id==intent_id).with_for_update())
    if row is None:raise HTTPException(404,"Intent not found")
    record=db.scalar(select(ControlledExecutionRecord).where(ControlledExecutionRecord.intent_id==row.id).with_for_update())
    if record and record.status in FINAL:return {"id":record.id,"intent_id":row.id,"status":record.status,"order_placed":record.status=="SUBMITTED","reconciliation":record.reconciliation,"idempotent":True}
    if row.status!="REVIEWED_TRIAL_ONLY" or not record or record.status!="REVIEWED_ONLY":raise HTTPException(409,"Exact reviewed intent is required")
    if aware(row.expires_at)<=now:row.status="EXPIRED";db.commit();raise HTTPException(409,"Intent expired before execution")
    risk=db.get(RiskAssessment,row.risk_assessment_id);policy=db.get(RiskPolicy,risk.policy_id) if risk else None;request=risk.request_snapshot if risk else {};limits=policy.configuration if policy else {}
    fresh=bool(risk and risk.risk_authorized and risk.outcome=="AUTHORIZED" and risk.strategy_decision_id==row.strategy_decision_id and (now-aware(request.get("market_data_as_of"))).total_seconds()<=int(limits.get("max_market_data_age_seconds",300)) and (now-aware(request.get("proposal_created_at"))).total_seconds()<=int(limits.get("max_proposal_age_seconds",300)))
    exact=bool(fresh and request.get("symbol")==row.symbol and request.get("side")==row.side and abs(float(request.get("quantity",0))-row.quantity)<1e-9 and abs(float(request.get("price",0))-row.limit_price)<1e-9)
    if not exact:raise HTTPException(409,"Fresh exact deterministic RiskEngine authorization is required")
    if row.quantity*row.limit_price>auth.max_order_notional+1e-9:raise HTTPException(409,"Order exceeds operator-authorized notional")
    if canonical_checksum(row.intent_snapshot)!=row.intent_checksum:raise HTTPException(409,"Intent checksum mismatch")
    expected_approval=canonical_checksum({"intent":row.intent_checksum,"approved_by":row.approved_by,"approved_at":aware(row.approved_at).isoformat()})
    if row.approval_checksum!=expected_approval:raise HTTPException(409,"Approval checksum mismatch")
    config=db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider=="robinhood"))
    if not config or not config.selected_account_ref:raise HTTPException(409,"Selected account unavailable")
    payload={"selected_account_ref":config.selected_account_ref,"symbol":row.symbol,"side":row.side,"quantity":row.quantity,"order_type":row.order_type,"limit_price":row.limit_price,"time_in_force":"GFD","intent_checksum":row.intent_checksum,"approval_checksum":row.approval_checksum}
    record.status="SUBMITTING";row.status="SUBMITTING";db.add(DevelopmentActivity(actor=actor,action="controlled_execution_submitting",entity_type="controlled_execution_record",entity_id=record.id,detail="Immutable intent locked; duplicate submission blocked"));db.commit()
    result=client.execution_place(payload)
    if result.get("status")=="REJECTED":record.status="REJECTED";row.status="BROKER_REJECTED";record.reconciliation={"status":"REJECTED","requires_human_attention":False};db.commit();return {"id":record.id,"intent_id":row.id,"status":record.status,"order_placed":False,"reconciliation":record.reconciliation,"idempotent":False}
    if result.get("status")!="SUBMITTED":_attention(db,controls,record,row,"SUBMISSION_OUTCOME_UNKNOWN",actor);raise HTTPException(502,"Broker submission outcome is unknown; circuit breaker engaged")
    actual=result.get("actual_order") if isinstance(result.get("actual_order"),dict) else {};check=reconcile(row.intent_snapshot,actual,[]);record.actual_order=actual;record.actual_checksum=check["actual_checksum"];record.reconciliation=check
    if check["status"]!="MATCHED":_attention(db,controls,record,row,"INTENDED_ACTUAL_MISMATCH",actor);raise HTTPException(409,"Broker order evidence mismatched intent; circuit breaker engaged")
    record.status="SUBMITTED";row.status="SUBMITTED";db.add(DevelopmentActivity(actor=actor,action="controlled_order_submitted",entity_type="controlled_execution_record",entity_id=record.id,detail="Broker order submitted once; intended and actual order matched; fill reconciliation pending"));db.commit()
    return {"id":record.id,"intent_id":row.id,"status":record.status,"order_placed":True,"reconciliation":record.reconciliation,"idempotent":False}

def _fills(value):
    found=[]
    if isinstance(value,dict):
        for key,child in value.items():
            if key.lower() in {"fills","executions"} and isinstance(child,list):found.extend(x for x in child if isinstance(x,dict))
            else:found.extend(_fills(child))
    elif isinstance(value,list):
        for child in value:found.extend(_fills(child))
    return found

def reconcile_from_snapshot(db:Session,intent_id:int,actor:str)->dict:
    now=datetime.now(UTC);row=db.get(ControlledTradeIntent,intent_id);record=db.scalar(select(ControlledExecutionRecord).where(ControlledExecutionRecord.intent_id==intent_id));controls=db.get(RiskControlState,1)
    if not row or not record:raise HTTPException(404,"Execution record not found")
    if record.status not in {"SUBMITTED","PARTIALLY_FILLED","RECONCILIATION_ATTENTION","UNKNOWN"}:raise HTTPException(409,"Execution is not awaiting broker reconciliation")
    order_ref=str((record.actual_order or {}).get("order_ref",""))
    if not order_ref:raise HTTPException(409,"Broker order reference unavailable; human reconciliation required")
    snapshot=db.scalar(select(BrokerSnapshot).order_by(BrokerSnapshot.source_observed_at.desc()))
    if not snapshot or (now-aware(snapshot.source_observed_at)).total_seconds()>300:raise HTTPException(409,"Fresh broker snapshot required")
    order=None
    for group in snapshot.orders or []:
        for candidate in group.get("records",[]):
            if isinstance(candidate,dict) and str(candidate.get("id") or candidate.get("order_id") or candidate.get("client_order_id") or "")==order_ref:order=candidate;break
        if order:break
    if order is None:return {"id":record.id,"intent_id":row.id,"status":record.status,"fill_status":"PENDING_BROKER_EVIDENCE","requires_human_attention":False}
    actual={"symbol":order.get("symbol",order.get("ticker")),"side":order.get("side"),"quantity":order.get("quantity",order.get("total_quantity")),"order_type":order.get("order_type",order.get("type")),"limit_price":order.get("limit_price",order.get("price"))}
    fills=_fills(order);check=reconcile(row.intent_snapshot,actual,fills);record.actual_order={**record.actual_order,"snapshot_order":order};record.fills=fills;record.actual_checksum=check["actual_checksum"];record.reconciliation=check
    if check["status"]!="MATCHED":_attention(db,controls,record,row,"BROKER_RECONCILIATION_MISMATCH",actor);raise HTTPException(409,"Broker reconciliation mismatch; circuit breaker engaged")
    record.status={"FILLED":"FILLED","PARTIALLY_FILLED":"PARTIALLY_FILLED"}.get(check["fill_status"],"SUBMITTED");row.status=record.status
    db.add(DevelopmentActivity(actor=actor,action="controlled_execution_reconciled",entity_type="controlled_execution_record",entity_id=record.id,detail=f"fill_status={check['fill_status']}; fill_quantity={check['fill_quantity']}; broker_snapshot={snapshot.id}"));db.commit()
    return {"id":record.id,"intent_id":row.id,"status":record.status,"fill_status":check["fill_status"],"fill_quantity":check["fill_quantity"],"requires_human_attention":False}
