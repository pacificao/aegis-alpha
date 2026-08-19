from __future__ import annotations
from datetime import UTC,datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import DevelopmentActivity,RiskAssessment,RiskControlState,RiskPolicy
from ..strategy_engine import canonical_checksum
from .engine import evaluate

DEFAULT_POLICY={"max_position_pct":1.0,"max_portfolio_exposure_pct":25.0,"max_sector_exposure_pct":20.0,"max_correlated_exposure_pct":30.0,"max_daily_loss_pct":2.0,"max_drawdown_pct":10.0,"max_annualized_volatility_pct":40.0,"max_buying_power_use_pct":25.0,"max_order_notional":10000.0,"max_order_quantity":10000.0,"max_price_deviation_bps":100.0,"max_open_orders":20,"max_market_data_age_seconds":300,"max_proposal_age_seconds":300}

def ensure_defaults(db:Session):
    if db.scalar(select(RiskPolicy).where(RiskPolicy.active.is_(True))) is None:
        db.add(RiskPolicy(version=1,name="Default conservative policy",configuration=DEFAULT_POLICY,checksum=canonical_checksum(DEFAULT_POLICY),active=True,created_by="system"))
    if db.get(RiskControlState,1) is None:db.add(RiskControlState(id=1,kill_switch_engaged=False,circuit_breaker_engaged=False,reason="Phase 6 initialized; execution absent; trading disabled",updated_by="system"))
    db.commit()

def assess(db:Session,payload,actor:str,now:datetime|None=None):
    policy=db.scalar(select(RiskPolicy).where(RiskPolicy.active.is_(True)).order_by(RiskPolicy.version.desc()));controls=db.get(RiskControlState,1)
    if policy is None or controls is None:raise ValueError("Risk controls are not initialized")
    request=payload.model_dump(mode="python");identity=canonical_checksum({"policy":policy.checksum,"proposal":payload.model_dump(mode="json")})
    existing=db.scalar(select(RiskAssessment).where(RiskAssessment.request_checksum==identity))
    if existing:return existing
    duplicate=db.scalar(select(RiskAssessment).where(RiskAssessment.proposal_id==payload.proposal_id))
    if duplicate:
        result={"outcome":"REJECTED","reason_codes":["DUPLICATE_PROPOSAL"],"checks":[{"code":"DUPLICATE_PROPOSAL","passed":False,"actual":payload.proposal_id,"limit":"unique","detail":"Proposal identifier was already evaluated"}],"notional":payload.quantity*payload.price,"risk_authorized":False}
    else:result=evaluate(policy.configuration,request,{"kill_switch_engaged":controls.kill_switch_engaged,"circuit_breaker_engaged":controls.circuit_breaker_engaged},now)
    breaker_codes={"DAILY_LOSS","DRAWDOWN","VOLATILITY"}.intersection(result["reason_codes"])
    if breaker_codes:
        controls.circuit_breaker_engaged=True;controls.reason=f"Automatic breaker: {chr(44).join(sorted(breaker_codes))}";controls.updated_by="risk-engine"
    row=RiskAssessment(policy_id=policy.id,proposal_id=payload.proposal_id,strategy_decision_id=payload.strategy_decision_id,request_checksum=identity,request_snapshot=payload.model_dump(mode="json"),outcome=result["outcome"],reason_codes=result["reason_codes"],checks=result["checks"],notional=result["notional"],risk_authorized=result["risk_authorized"],created_by=actor)
    db.add(row);db.flush();db.add(DevelopmentActivity(actor=actor,action="risk_assessment_completed",entity_type="risk_assessment",entity_id=row.id,detail=f"proposal={payload.proposal_id}; outcome={row.outcome}; reasons={','.join(row.reason_codes)}; executable=false; trading=DISABLED"));db.commit();db.refresh(row);return row

def serialize(row):
    return {"id":row.id,"policy_id":row.policy_id,"proposal_id":row.proposal_id,"strategy_decision_id":row.strategy_decision_id,"request_checksum":row.request_checksum,"request_snapshot":row.request_snapshot,"outcome":row.outcome,"reason_codes":row.reason_codes,"checks":row.checks,"notional":row.notional,"risk_authorized":row.risk_authorized,"executable":False,"trading":"DISABLED","created_by":row.created_by,"created_at":row.created_at}
