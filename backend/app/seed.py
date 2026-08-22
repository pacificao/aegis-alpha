from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BrokerConnectionConfig, DataProvider, Instrument, Phase, StrategyScenario, Task, TaskStatus
from .roadmap_data import PHASES
from .risk.service import ensure_defaults

PHASE1_COMPLETE = {
    3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 21, 22, 23, 24, 25,
    26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 39, 40, 41, 42, 44, 45, 46,
    48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
    66, 67, 68, 69,
}
PHASE1_BLOCKED = {4, 37, 38, 43, 47}
PHASE3_COMPLETE = {1, 4, 6, 8, 9, 10, 11, 12}
PHASE3_WAITING = {2, 3, 5, 7}


def seed_roadmap(db: Session) -> None:
    broker = db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider == "robinhood"))
    if broker is None:
        db.add(BrokerConnectionConfig(provider="robinhood", connection_name="Robinhood Agentic", endpoint="https://agent.robinhood.com/mcp/trading", mode="READ_ONLY"))
    dividend_farm = db.scalar(select(StrategyScenario).where(StrategyScenario.name == "Dividend Farm"))
    if dividend_farm is None:
        db.add(StrategyScenario(name="Dividend Farm", strategy_type="DIVIDEND_FARM", description="Research whether dividend capture plus capital recycling produces attractive risk-adjusted returns.", lifecycle="RESEARCH", parameters={"max_position_pct": 1.0, "max_allocation_pct": 25.0, "min_annual_yield_pct": 1.0, "max_annual_yield_pct": 12.0, "min_dividend_event_pct": 0.15, "event_yield_sensitivity_pct": [0.10, 0.15, 0.25], "payment_frequencies": ["MONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL"], "min_dividend_history_years": 5, "min_historical_events": 12, "max_median_recovery_days": 30, "max_p90_recovery_days": 90, "min_recovery_probability_pct": 80.0, "max_historical_drawdown_pct": 15.0, "max_holding_days": 90, "min_market_cap_millions": 1000, "min_average_daily_dollar_volume": 5000000, "max_sector_exposure_pct": 20.0, "earnings_exclusion_days": 5, "include_reits": False, "include_etfs": False, "include_special_dividends": False, "entry_days_before_ex_date": 1, "exit_method": "PURCHASE_PRICE", "profit_target_pct": 0.0, "reinvest_dividends": True}))
    templates=(
        ("Trend Momentum","TREND_MOMENTUM","Research persistent risk-adjusted price trends with liquidity and volatility confirmation.",{"lookback_days":126,"fast_average_days":50,"slow_average_days":200,"max_position_pct":1.0,"max_allocation_pct":20.0,"max_drawdown_pct":8.0}),
        ("Mean Reversion","MEAN_REVERSION","Research bounded reversions toward an evidence-based reference price.",{"lookback_days":20,"entry_zscore":2.0,"exit_zscore":0.25,"max_position_pct":0.5,"max_allocation_pct":10.0,"max_drawdown_pct":6.0}),
        ("Quality Value","QUALITY_VALUE","Research liquid companies with durable quality and valuation evidence.",{"minimum_quality_score":70,"minimum_value_score":70,"rebalance_days":30,"max_position_pct":1.0,"max_allocation_pct":20.0,"max_drawdown_pct":10.0}),
        ("Volatility Breakout","VOLATILITY_BREAKOUT","Research confirmed breakouts with volatility-sized exits and strict loss limits.",{"breakout_days":20,"atr_stop_multiple":2.0,"minimum_volume_multiple":1.5,"max_position_pct":0.5,"max_allocation_pct":10.0,"max_drawdown_pct":6.0}),
        ("Pairs Reversion","PAIRS_REVERSION","Paper-only research of stable relative-value relationships; no short-sale execution capability.",{"lookback_days":120,"entry_zscore":2.0,"exit_zscore":0.25,"max_position_pct":0.5,"max_allocation_pct":5.0,"max_drawdown_pct":4.0,"paper_only":True}),
    )
    for name,strategy_type,description,parameters in templates:
        if db.scalar(select(StrategyScenario).where(StrategyScenario.name==name)) is None:
            db.add(StrategyScenario(name=name,strategy_type=strategy_type,description=description,lifecycle="RESEARCH",parameters=parameters))
    providers=(("alpaca","MARKET","https://data.alpaca.markets","WAITING_FOR_CREDENTIALS"),("robinhood","BROKER_MARKET","https://agent.robinhood.com/mcp/trading","BROKER_MANAGED"),("alpha_vantage","MARKET","https://www.alphavantage.co/query","WAITING_FOR_CREDENTIALS"),("fred","ECONOMIC","https://fred.stlouisfed.org/graph/fredgraph.csv","NOT_REQUIRED"),("sec_edgar","FUNDAMENTAL","https://data.sec.gov","NOT_REQUIRED"),("aegis_calendar","CALENDAR","https://www.nyse.com/markets/hours-calendars","NOT_REQUIRED"))
    for provider_name,provider_type,base_url,credential_status in providers:
        if db.scalar(select(DataProvider).where(DataProvider.name==provider_name)) is None:
            db.add(DataProvider(name=provider_name,provider_type=provider_type,base_url=base_url,credential_status=credential_status,enabled=provider_name in {"alpaca","robinhood","fred","sec_edgar","aegis_calendar"}))
    for symbol,name,cik in (("SPY","SPDR S&P 500 ETF Trust",None),("QQQ","Invesco QQQ Trust",None),("AAPL","Apple Inc.","0000320193")):
        if db.scalar(select(Instrument).where(Instrument.symbol==symbol)) is None:
            db.add(Instrument(symbol=symbol,name=name,cik=cik,metadata_json={}))
    db.flush()
    for number, name, description, tasks in PHASES:
        phase = db.scalar(select(Phase).where(Phase.number == number))
        if phase is None:
            phase = Phase(number=number, name=name, description=description)
            db.add(phase)
            db.flush()
        for ordinal, title in enumerate(tasks, 1):
            existing = db.scalar(select(Task).where(Task.phase_id == phase.id, Task.ordinal == ordinal))
            if existing is None:
                initial_status = TaskStatus.NOT_STARTED
                notes = ""
                if number == 1 and ordinal in PHASE1_COMPLETE:
                    initial_status = TaskStatus.COMPLETE
                elif number == 1 and ordinal in PHASE1_BLOCKED:
                    initial_status = TaskStatus.BLOCKED
                    notes = "Host prerequisite or privileged verification required; see development status."
                elif number == 1:
                    initial_status = TaskStatus.IN_PROGRESS
                elif number == 3 and ordinal in PHASE3_COMPLETE:
                    initial_status = TaskStatus.COMPLETE
                    notes = "Implemented and verified in Phase 3 acceptance."
                elif number == 3 and ordinal in PHASE3_WAITING:
                    initial_status = TaskStatus.WAITING_FOR_CREDENTIALS
                    notes = "Official Alpha Vantage adapter is implemented and fixture-tested; production API key and live ingestion validation are required."
                db.add(Task(phase_id=phase.id, ordinal=ordinal, title=title, status=initial_status, notes=notes))
    db.commit()
    ensure_defaults(db)
