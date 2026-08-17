from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BrokerConnectionConfig, Phase, StrategyScenario, Task, TaskStatus
from .roadmap_data import PHASES

PHASE1_COMPLETE = {
    3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 21, 22, 23, 24, 25,
    26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 39, 40, 41, 42, 44, 45, 46,
    48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
    66, 67, 68, 69,
}
PHASE1_BLOCKED = {4, 37, 38, 43, 47}


def seed_roadmap(db: Session) -> None:
    broker = db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider == "robinhood"))
    if broker is None:
        db.add(BrokerConnectionConfig(provider="robinhood", connection_name="Robinhood Agentic", endpoint="https://agent.robinhood.com/mcp/trading", mode="READ_ONLY"))
    dividend_farm = db.scalar(select(StrategyScenario).where(StrategyScenario.name == "Dividend Farm"))
    if dividend_farm is None:
        db.add(StrategyScenario(name="Dividend Farm", strategy_type="DIVIDEND_FARM", description="Research whether dividend capture plus capital recycling produces attractive risk-adjusted returns.", lifecycle="RESEARCH", parameters={"max_position_pct": 1.0, "max_allocation_pct": 25.0, "min_annual_yield_pct": 1.0, "max_annual_yield_pct": 12.0, "min_dividend_event_pct": 0.15, "payment_frequencies": ["MONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL"], "min_dividend_history_years": 5, "min_historical_events": 12, "max_median_recovery_days": 30, "max_p90_recovery_days": 90, "min_recovery_probability_pct": 80.0, "max_historical_drawdown_pct": 15.0, "max_holding_days": 90, "min_market_cap_millions": 1000, "min_average_daily_volume": 500000, "max_sector_exposure_pct": 20.0, "earnings_exclusion_days": 5, "include_reits": False, "include_etfs": False, "include_special_dividends": False, "entry_days_before_ex_date": 1, "exit_method": "PURCHASE_PRICE", "profit_target_pct": 0.0, "reinvest_dividends": True}))
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
                db.add(Task(phase_id=phase.id, ordinal=ordinal, title=title, status=initial_status, notes=notes))
    db.commit()
