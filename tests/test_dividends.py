from datetime import date

from app.data.dividends import company_name,recovery_estimate


def test_company_name_uses_explicit_or_description():
    assert company_name("Realty Income Corp. is a real estate company.")=="Realty Income Corp."
    assert company_name("ignored","Realty Income Corporation")=="Realty Income Corporation"


def test_recovery_estimate_requires_twelve_events_and_uses_trading_sessions():
    bars={date(2026,1,1):10,date(2026,1,2):9,date(2026,1,5):10}
    result=recovery_estimate([date(2026,1,2)],bars,date(2026,2,1))
    assert result["estimated_recovery_days"] is None and result["recovery_observations"]==1
    result=recovery_estimate([date(2026,1,2)],bars,date(2026,2,1),minimum_observations=1)
    assert result["estimated_recovery_days"]==2 and result["recovery_probability_pct"]==100
