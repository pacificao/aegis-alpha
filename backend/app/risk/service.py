from __future__ import annotations
from datetime import UTC,datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import DevelopmentActivity,RiskAssessment,RiskControlState,RiskPolicy,StrategyDecision,StrategyScenario,StrategyVersion
from ..strategy_engine import canonical_checksum
from .engine import evaluate

DEFAULT_POLICY={"min_order_notional":1.0,"max_position_pct":1.0,"max_portfolio_exposure_pct":100.0,"max_sector_exposure_pct":20.0,"max_correlated_exposure_pct":30.0,"max_daily_loss_pct":2.0,"max_drawdown_pct":10.0,"max_annualized_volatility_pct":40.0,"max_buying_power_use_pct":100.0,"max_order_notional":10000.0,"max_order_quantity":10000.0,"max_price_deviation_bps":100.0,"max_open_orders":20,"max_market_data_age_seconds":300,"max_proposal_age_seconds":300,"micro_account_trial_enabled":True,"micro_account_portfolio_threshold":100.0,"micro_account_max_position_notional":2.0}

def ensure_defaults(db:Session):
    if db.scalar(select(RiskPolicy).where(RiskPolicy.active.is_(True))) is None:
        db.add(RiskPolicy(version=1,name="Default conservative policy",configuration=DEFAULT_POLICY,checksum=canonical_checksum(DEFAULT_POLICY),active=True,created_by="system"))
    policy=db.scalar(select(RiskPolicy).where(RiskPolicy.active.is_(True)).order_by(RiskPolicy.version.desc()))
    if policy and float(policy.configuration.get("micro_account_max_position_notional",1.0))<2.0:
        configuration=dict(policy.configuration);configuration["micro_account_max_position_notional"]=2.0;policy.configuration=configuration;policy.checksum=canonical_checksum(configuration)
    if db.get(RiskControlState,1) is None:db.add(RiskControlState(id=1,kill_switch_engaged=False,circuit_breaker_engaged=False,reason="Phase 6 initialized; execution absent; trading disabled",updated_by="system"))
    db.commit()

def effective_policy(db:Session,configuration:dict,strategy_decision_id:int|None)->dict:
    """A strategy may tighten, but can never loosen, the active global policy."""
    effective=dict(configuration)
    if strategy_decision_id is None:return effective
    decision=db.get(StrategyDecision,strategy_decision_id);version=db.get(StrategyVersion,decision.version_id) if decision else None
    if version is None:return effective
    spec=version.specification or {};sizing=spec.get("position_sizing",{});parameters=spec.get("parameters",{})
    limits={"max_position_pct":sizing.get("max_position_pct",parameters.get("max_position_pct")),"max_portfolio_exposure_pct":sizing.get("max_strategy_allocation_pct",parameters.get("max_allocation_pct")),"max_drawdown_pct":parameters.get("max_drawdown_pct"),"max_daily_loss_pct":parameters.get("max_daily_loss_pct")}
    for key,value in limits.items():
        if isinstance(value,(int,float)) and value>=0:effective[key]=min(float(effective[key]),float(value))
    scenario=db.get(StrategyScenario,version.scenario_id)
    effective["micro_account_trial_eligible"]=bool(effective.get("micro_account_trial_enabled",True) and scenario and scenario.strategy_type=="DIVIDEND_FARM" and decision.decision in {"ENTRY","EXIT"})
    return effective

def assess(db:Session,payload,actor:str,now:datetime|None=None):
    policy=db.scalar(select(RiskPolicy).where(RiskPolicy.active.is_(True)).order_by(RiskPolicy.version.desc()));controls=db.get(RiskControlState,1)
    if policy is None or controls is None:raise ValueError("Risk controls are not initialized")
    request=payload.model_dump(mode="python");configuration=effective_policy(db,policy.configuration,payload.strategy_decision_id);identity=canonical_checksum({"policy":canonical_checksum(configuration),"proposal":payload.model_dump(mode="json")})
    existing=db.scalar(select(RiskAssessment).where(RiskAssessment.request_checksum==identity))
    if existing:return existing
    duplicate=db.scalar(select(RiskAssessment).where(RiskAssessment.proposal_id==payload.proposal_id))
    if duplicate:
        result={"outcome":"REJECTED","reason_codes":["DUPLICATE_PROPOSAL"],"checks":[{"code":"DUPLICATE_PROPOSAL","passed":False,"actual":payload.proposal_id,"limit":"unique","detail":"Proposal identifier was already evaluated"}],"notional":payload.quantity*payload.price,"risk_authorized":False}
    else:result=evaluate(configuration,request,{"kill_switch_engaged":controls.kill_switch_engaged,"circuit_breaker_engaged":controls.circuit_breaker_engaged},now)
    breaker_codes={"DAILY_LOSS","DRAWDOWN","VOLATILITY"}.intersection(result["reason_codes"])
    if breaker_codes:
        controls.circuit_breaker_engaged=True;controls.reason=f"Automatic breaker: {chr(44).join(sorted(breaker_codes))}";controls.updated_by="risk-engine"
    row=RiskAssessment(policy_id=policy.id,proposal_id=payload.proposal_id,strategy_decision_id=payload.strategy_decision_id,request_checksum=identity,request_snapshot=payload.model_dump(mode="json"),outcome=result["outcome"],reason_codes=result["reason_codes"],checks=result["checks"],notional=result["notional"],risk_authorized=result["risk_authorized"],created_by=actor)
    db.add(row);db.flush();db.add(DevelopmentActivity(actor=actor,action="risk_assessment_completed",entity_type="risk_assessment",entity_id=row.id,detail=f"proposal={payload.proposal_id}; outcome={row.outcome}; reasons={','.join(row.reason_codes)}; executable=false; trading=DISABLED"));db.commit();db.refresh(row);return row

def serialize(row):
    return {"id":row.id,"policy_id":row.policy_id,"proposal_id":row.proposal_id,"strategy_decision_id":row.strategy_decision_id,"request_checksum":row.request_checksum,"request_snapshot":row.request_snapshot,"outcome":row.outcome,"reason_codes":row.reason_codes,"checks":row.checks,"notional":row.notional,"risk_authorized":row.risk_authorized,"executable":False,"trading":"DISABLED","created_by":row.created_by,"created_at":row.created_at}
