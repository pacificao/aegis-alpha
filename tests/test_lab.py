from datetime import UTC,date,datetime,timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import Principal,csrf_protected,current_principal
from app.lab.engine import Action,Bar,checksum,sensitivity,simulate
from app.main import app
from app.schemas import LabBacktestRequest

principal=Principal(username="test-operator",session_id="lab",csrf_token="csrf")
def fixtures():
 start=date(2026,1,1);bars=[]
 for i in range(80):
  day=start+timedelta(days=i);price=100+i*.08
  if i==20:price=99
  bars.append(Bar(day,"AAPL",price,price+1,price-1,price,1_000_000));bars.append(Bar(day,"SPY",500+i*.2,501+i*.2,499+i*.2,500+i*.2,2_000_000))
 return bars,[Action(start+timedelta(days=20),"AAPL","DIVIDEND",1.0),Action(start+timedelta(days=25),"SPY","DIVIDEND",2.0),Action(start+timedelta(days=45),"AAPL","SPLIT",2.0)]
def config():return {"initial_capital":100000.0,"commission_per_trade":1.0,"slippage_bps":5.0,"spread_bps":4.0,"max_position_pct":1.0,"max_allocation_pct":25.0,"entry_days_before_ex_date":1,"exit_method":"PURCHASE_PRICE","profit_target_pct":0.0,"historical_recovery_days":30,"volatility_multiplier":1.0,"hybrid_time_stop_days":30,"max_holding_days":30,"benchmark_symbol":"SPY","monte_carlo_iterations":100,"random_seed":42,"run_sensitivity":True,"start_date":"2026-01-01","end_date":"2026-03-21","strategy_version_id":1,"symbols":["AAPL"]}

def test_reproducible_portfolio_backtest_covers_phase5_analytics():
 bars,actions=fixtures();first=simulate(bars,actions,config());second=simulate(bars,actions,config())
 assert first==second and first["trading"]=="DISABLED" and first["executable"] is False and first["risk_authorized"] is False
 metrics=first["metrics"];assert metrics["trade_count"]==1 and first["trades"][0]["symbol"]=="AAPL" and metrics["total_dividends"]>0 and metrics["benchmark_return_pct"]>0
 for key in ("cagr_pct","maximum_drawdown_pct","sharpe_ratio","sortino_ratio","average_exposure_pct","turnover_pct","return_per_capital_day_pct"):assert key in metrics
 assert first["walk_forward"]["split_date"] and first["monte_carlo"]["iterations"]==100
 assert first["trades"][0]["costs"]>0 and first["trades"][0]["holding_days"]>=1
 assert len(sensitivity(bars,actions,config()))==36
 assert checksum(first)==checksum(second)

def test_friction_and_corporate_action_behavior():
 bars,actions=fixtures();base=simulate(bars,actions,{**config(),"commission_per_trade":0,"slippage_bps":0,"spread_bps":0});costly=simulate(bars,actions,config())
 assert costly["metrics"]["ending_equity"]<base["metrics"]["ending_equity"]
 assert base["trades"][0]["dividends"]>0

def test_lab_request_validation_and_authentication():
 valid={**config(),"start_date":"2026-01-01T00:00:00Z","end_date":"2026-03-21T00:00:00Z"};assert LabBacktestRequest(**valid).random_seed==42
 for invalid in ({**valid,"max_position_pct":11},{**valid,"start_date":"2026-04-01T00:00:00Z"},{**valid,"symbols":["AAPL","AAPL"]}):
  try:LabBacktestRequest(**invalid);assert False
  except ValueError:pass
 with TestClient(app) as client:
  assert client.get("/api/lab/readiness").status_code==401
  assert client.get("/api/lab/backtests").status_code==401

def test_split_adjusts_open_position_without_creating_capital():
 start=date(2026,4,1);bars=[]
 for i in range(10):
  price=100 if i<2 else 90 if i<4 else 45
  bars.append(Bar(start+timedelta(days=i),"XYZ",price,price+1,price-1,price,500000))
 actions=[Action(start+timedelta(days=2),"XYZ","DIVIDEND",1),Action(start+timedelta(days=4),"XYZ","SPLIT",2)]
 result=simulate(bars,actions,{**config(),"symbols":["XYZ"],"benchmark_symbol":"XYZ","exit_method":"FIXED_5"})
 assert result["metrics"]["trade_count"]==1
 assert abs(result["trades"][0]["shares"]-19.98)<.01
 assert result["trades"][0]["exit_reason"]=="FIXED_EXIT"

def test_small_account_backtest_uses_fractional_shares_above_one_dollar():
 bars,actions=fixtures();result=simulate(bars,actions,{**config(),"initial_capital":5,"commission_per_trade":0,"max_position_pct":25,"max_allocation_pct":25})
 assert result["trades"] and 0<result["trades"][0]["shares"]<1

def test_lab_api_persists_reproducible_artifact():
 from sqlalchemy import select
 from app.database import SessionLocal
 from app.models import DataProvider,DataRecord,Instrument,StrategyScenario,StrategyVersion
 from app.strategy_engine import canonical_checksum
 with TestClient(app):pass
 with SessionLocal() as db:
  suffix=uuid4().hex[:6].upper();labx=f"LX{suffix}";labb=f"LB{suffix}"
  provider=db.scalar(select(DataProvider).where(DataProvider.name=="alpha_vantage"));assert provider
  scenario=StrategyScenario(name=f"Lab API Fixture {uuid4().hex[:8]}",strategy_type="CUSTOM_RESEARCH",description="fixture",lifecycle="RESEARCH",parameters={});db.add(scenario);db.flush()
  spec={"fixture":"phase5"};version=StrategyVersion(scenario_id=scenario.id,version=1,specification=spec,checksum=canonical_checksum(spec),created_by="test-operator");db.add(version)
  instruments={}
  for symbol in (labx,labb):
   item=db.scalar(select(Instrument).where(Instrument.symbol==symbol)) or Instrument(symbol=symbol,metadata_json={});db.add(item);db.flush();instruments[symbol]=item
  bars,actions=fixtures()
  for index,bar in enumerate(bars):
   symbol=labx if bar.symbol=="AAPL" else labb;db.add(DataRecord(provider_id=provider.id,instrument_id=instruments[symbol].id,data_type="OHLCV",external_id=f"{symbol}:{bar.day}",event_time=datetime.combine(bar.day,datetime.min.time(),tzinfo=UTC),interval="1d",payload={"open":bar.open,"high":bar.high,"low":bar.low,"close":bar.close,"volume":bar.volume},source_url="https://example.test/fixture",observed_at=datetime.now(UTC),quality_status="VALID",checksum=f"{suffix}-bar-{index:04d}"))
  db.add(DataRecord(provider_id=provider.id,instrument_id=instruments[labx].id,data_type="CORPORATE_ACTION",external_id=f"{labx}:dividend",event_time=datetime(2026,1,21,tzinfo=UTC),interval="event",payload={"action":"DIVIDEND","amount":"1.0"},source_url="https://example.test/fixture",observed_at=datetime.now(UTC),quality_status="VALID",checksum=f"{suffix}-action-dividend"));db.commit();version_id=version.id
 app.dependency_overrides[current_principal]=lambda:principal;app.dependency_overrides[csrf_protected]=lambda:principal
 try:
  with TestClient(app) as client:
   payload={**config(),"strategy_version_id":version_id,"symbols":[labx],"benchmark_symbol":labb,"start_date":"2026-01-01T00:00:00Z","end_date":"2026-03-21T00:00:00Z"}
   created=client.post("/api/lab/backtests",json=payload,headers={"X-CSRF-Token":"csrf"});assert created.status_code==201,created.text
   result=created.json();assert result["status"]=="COMPLETE" and result["data_provenance"]["bar_count"]==160 and result["trading"]=="DISABLED"
   duplicate=client.post("/api/lab/backtests",json=payload,headers={"X-CSRF-Token":"csrf"});assert duplicate.status_code==201 and duplicate.json()["id"]==result["id"]
   trades=client.get(f"/api/lab/backtests/{result['id']}/trades");assert trades.status_code==200 and trades.json()[0]["symbol"]==labx
 finally:app.dependency_overrides.clear()
