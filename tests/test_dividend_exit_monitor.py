from datetime import UTC,date,datetime,timedelta
from uuid import uuid4
from sqlalchemy import select
from app.database import SessionLocal
from app.dividend_exit_monitor import authorize_recovery_exits,capture_filled_entries,monitor_recovery_exits
from app.risk.service import ensure_defaults
from app.models import BrokerSnapshot,ControlledExecutionRecord,ControlledTradeIntent,DataProvider,DataRecord,DividendFarmPosition,Instrument,PlannedTrade,RiskAssessment,RiskPolicy,StrategyDecision,StrategyScenario,StrategyVersion


def fixture(db,symbol,now,ex_date):
    ensure_defaults(db)
    marker=uuid4().hex
    scenario=StrategyScenario(name=f"Exit {marker}",strategy_type="DIVIDEND_FARM",description="exit test",lifecycle="RESEARCH",parameters={});db.add(scenario);db.flush()
    version=StrategyVersion(scenario_id=scenario.id,version=1,specification={"parameters":{"exit_method":"PURCHASE_PRICE"}},checksum=marker.ljust(64,"0")[:64],created_by="test");db.add(version);db.flush()
    decision=StrategyDecision(version_id=version.id,symbol=symbol,as_of=now-timedelta(days=2),decision="ENTRY",reason_codes=["QUALIFIED"],proposed_weight_pct=1,inputs={"next_ex_dividend_date":ex_date.isoformat()});db.add(decision);db.flush()
    plan=PlannedTrade(strategy_decision_id=decision.id,symbol=symbol,side="BUY",quantity=.1,reference_price=10,reserved_notional=1,planned_entry_date=ex_date-timedelta(days=1),status="READY_FOR_FINAL_APPROVAL",rationale="fixture",plan_checksum=marker.ljust(64,"1")[:64],created_by="test");db.add(plan);db.flush()
    policy=db.scalar(select(RiskPolicy).where(RiskPolicy.active.is_(True)))
    risk=RiskAssessment(policy_id=policy.id,proposal_id=f"exit-{marker}",strategy_decision_id=decision.id,request_checksum=marker.ljust(64,"2")[:64],request_snapshot={},outcome="AUTHORIZED",reason_codes=["ALL_CONTROLS_PASSED"],checks=[],notional=1,risk_authorized=True,created_by="test");db.add(risk);db.flush()
    intent=ControlledTradeIntent(risk_assessment_id=risk.id,strategy_decision_id=decision.id,symbol=symbol,side="BUY",quantity=.1,order_type="LIMIT",limit_price=10,status="APPROVED_TRIAL_ONLY",intent_checksum=marker.ljust(64,"3")[:64],intent_snapshot={},expires_at=now+timedelta(minutes=5),created_by="test");db.add(intent);db.flush()
    execution=ControlledExecutionRecord(intent_id=intent.id,environment="FIXTURE",status="RECONCILED",intended_snapshot={},review_snapshot={},actual_order={"symbol":symbol},fills=[{"quantity":"0.1","price":"10.00","filled_at":(now-timedelta(days=2)).isoformat()}],reconciliation={"status":"MATCHED"},created_by="test");db.add(execution);db.flush()
    instrument=Instrument(symbol=symbol,asset_type="EQUITY",active=True);db.add(instrument);db.flush()
    provider=db.scalar(select(DataProvider).where(DataProvider.name=="robinhood"))
    if provider is None:provider=DataProvider(name="robinhood",provider_type="BROKER",enabled=True,credential_status="CONFIGURED",base_url="https://agent.robinhood.com/mcp/trading");db.add(provider);db.flush()
    snapshot=BrokerSnapshot(provider="robinhood",status="VERIFIED",account_count=1,account_refs=["ref_test"],balances=[{"dataset":"get_portfolio","records":[{"total_value":"5","buying_power":"5","cash":"4"}]}],holdings=[{"dataset":"get_equity_positions","records":[{"symbol":symbol,"quantity":"0.1"}]}],orders=[],fills=[],reconciliation={},checksum=marker.ljust(64,"4")[:64],source_observed_at=now,created_by="test");db.add(snapshot);db.commit()
    return decision,plan,execution,instrument,provider,snapshot


def test_reconciled_fill_opens_position_and_recovery_creates_one_exit_plan():
    now=datetime(2026,8,25,15,0,tzinfo=UTC);symbol=f"Z{uuid4().hex[:5].upper()}"
    with SessionLocal() as db:
        decision,plan,execution,instrument,provider,snapshot=fixture(db,symbol,now,date(2026,8,25))
        opened=capture_filled_entries(db);assert len(opened)==1
        position=db.get(DividendFarmPosition,opened[0]);assert position.entry_price==10 and position.exit_target_price==10 and position.status=="OPEN"
        assert db.get(PlannedTrade,plan.id).status=="FILLED"
        db.add(DataRecord(provider_id=provider.id,instrument_id=instrument.id,data_type="BROKER_QUOTE",external_id=f"{symbol}:quote",event_time=now,interval="snapshot",payload={"last_trade_price":"10.01"},source_url="https://agent.robinhood.com/mcp/trading",observed_at=now,quality_status="VALID",checksum=uuid4().hex.ljust(64,"0")[:64]));db.commit()
        exits=monitor_recovery_exits(db,now);assert len(exits)==1
        exit_plan=db.get(PlannedTrade,exits[0]);assert exit_plan.side=="SELL" and exit_plan.quantity==.1 and exit_plan.status=="EXIT_RISK_REVIEW_REQUIRED" and exit_plan.final_risk_assessment_id is None
        authorized=authorize_recovery_exits(db,now);assert authorized==[exit_plan.id];db.refresh(exit_plan);assert exit_plan.status=="RISK_AUTHORIZED_EXIT" and exit_plan.final_risk_assessment_id is not None
        assert db.get(DividendFarmPosition,position.id).status=="EXIT_SIGNALLED"
        assert monitor_recovery_exits(db,now)==[]
        snapshot.source_observed_at=datetime(2000,1,1,tzinfo=UTC);db.commit()


def test_exit_monitor_fails_closed_before_ex_date_stale_price_below_target_or_missing_shares():
    now=datetime(2026,8,24,15,0,tzinfo=UTC);symbol=f"Y{uuid4().hex[:5].upper()}"
    with SessionLocal() as db:
        _,_,_,instrument,provider,snapshot=fixture(db,symbol,now,date(2026,8,25));position_id=capture_filled_entries(db)[0]
        db.add(DataRecord(provider_id=provider.id,instrument_id=instrument.id,data_type="BROKER_QUOTE",external_id=f"{symbol}:stale",event_time=now-timedelta(minutes=10),interval="snapshot",payload={"last_trade_price":"11"},source_url="https://agent.robinhood.com/mcp/trading",observed_at=now,quality_status="VALID",checksum=uuid4().hex.ljust(64,"0")[:64]));db.commit()
        assert monitor_recovery_exits(db,now)==[]
        after=now+timedelta(days=1);assert monitor_recovery_exits(db,after)==[]
        db.add(DataRecord(provider_id=provider.id,instrument_id=instrument.id,data_type="BROKER_QUOTE",external_id=f"{symbol}:low",event_time=after,interval="snapshot",payload={"last_trade_price":"9.99"},source_url="https://agent.robinhood.com/mcp/trading",observed_at=after,quality_status="VALID",checksum=uuid4().hex.ljust(64,"1")[:64]));
        snapshot.source_observed_at=after;db.commit();assert monitor_recovery_exits(db,after)==[]
        snapshot.holdings=[];db.commit();assert monitor_recovery_exits(db,after)==[] and db.get(DividendFarmPosition,position_id).status=="OPEN"
        snapshot.source_observed_at=datetime(2000,1,1,tzinfo=UTC);db.commit()
