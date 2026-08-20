from datetime import date
from statistics import median


def company_name(description: str | None, explicit: str | None = None) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    text=(description or "").strip()
    prefix=text.split(" is ",1)[0].strip()
    return prefix if prefix and prefix != text else None


def recovery_estimate(action_dates: list[date], bars: dict[date,float], today: date, minimum_observations: int = 12) -> dict:
    ordered=sorted(bars)
    recoveries=[];observations=0
    for ex_date in sorted(set(day for day in action_dates if day < today)):
        prior=[day for day in ordered if day < ex_date]
        if not prior: continue
        observations+=1;entry=bars[prior[-1]]
        after=[day for day in ordered if day >= ex_date]
        recovered=next((index+1 for index,day in enumerate(after) if bars[day]>=entry),None)
        if recovered is not None:recoveries.append(recovered)
    probability=round(len(recoveries)/observations*100,1) if observations else None
    if observations < minimum_observations:
        status="INSUFFICIENT_HISTORY";estimate=None
    elif not recoveries:
        status="NO_HISTORICAL_RECOVERY";estimate=None
    else:
        status="ESTIMATED";estimate=round(float(median(recoveries)),1)
    latest=bars[ordered[-1]] if ordered else None
    return {"estimated_recovery_days":estimate,"recovery_observations":observations,"recovery_probability_pct":probability,"recovery_status":status,"reference_price":latest}
