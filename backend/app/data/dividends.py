from datetime import date
from math import ceil
from statistics import median


def _percentile_nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values: return None
    ordered=sorted(values);index=max(0,min(len(ordered)-1,ceil(percentile*len(ordered))-1))
    return ordered[index]


def company_name(description: str | None, explicit: str | None = None) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    text=(description or "").strip()
    prefix=text.split(" is ",1)[0].strip()
    return prefix if prefix and prefix != text else None


def recovery_estimate(action_dates: list[date], bars: dict[date,float], today: date, minimum_observations: int = 12) -> dict:
    ordered=sorted(bars);historical_events=len(set(day for day in action_dates if day<today))
    recoveries=[];drawdowns=[];observations=0
    for ex_date in sorted(set(day for day in action_dates if day < today)):
        prior=[day for day in ordered if day < ex_date]
        if not prior: continue
        observations+=1;entry=bars[prior[-1]]
        after=[day for day in ordered if day >= ex_date]
        recovered=next((index+1 for index,day in enumerate(after) if bars[day]>=entry),None)
        window=after[:recovered] if recovered is not None else after
        if window and entry>0:drawdowns.append(max(0.0,(entry-min(bars[day] for day in window))/entry*100))
        if recovered is not None:recoveries.append(recovered)
    probability=round(len(recoveries)/observations*100,1) if observations else None
    if observations < minimum_observations:
        status="INSUFFICIENT_HISTORY";estimate=None
    elif not recoveries:
        status="NO_HISTORICAL_RECOVERY";estimate=None
    else:
        status="ESTIMATED";estimate=round(float(median(recoveries)),1)
    latest=bars[ordered[-1]] if ordered else None
    return {"historical_dividend_events":historical_events,"price_history_days":len(ordered),"estimated_recovery_days":estimate,"recovery_p90_days":_percentile_nearest_rank(recoveries,0.90),"recovery_observations":observations,"recovery_probability_pct":probability,"maximum_historical_drawdown_pct":round(max(drawdowns),2) if drawdowns else None,"recovery_status":status,"reference_price":latest}


def dividend_safety_assessment(evidence: dict, minimum_observations: int = 12) -> dict:
    """Conservative research score; it never authorizes a trade."""
    observations=int(evidence.get("recovery_observations") or 0)
    probability=evidence.get("recovery_probability_pct")
    median_days=evidence.get("estimated_recovery_days")
    p90_days=evidence.get("recovery_p90_days")
    drawdown=evidence.get("maximum_historical_drawdown_pct")
    score=20*min(observations/minimum_observations,1.0)
    score+=30*(max(0,min(float(probability or 0),100))/100)
    score+=20*max(0,1-min(float(median_days if median_days is not None else 90),90)/90)
    score+=15*max(0,1-min(float(p90_days if p90_days is not None else 120),120)/120)
    score+=15*max(0,1-min(float(drawdown if drawdown is not None else 40),40)/40)
    safety=max(1,min(100,round(score)))
    confidence="HIGH" if observations>=24 else "MEDIUM" if observations>=minimum_observations else "LOW"
    if observations<minimum_observations:
        recommendation="INSUFFICIENT_DATA";reason=f"No buy planned; {observations}/{minimum_observations} recovery observations available."
    elif safety>=75:
        recommendation="RESEARCH_CANDIDATE";reason="No buy planned; candidate merits strategy and deterministic risk review."
    elif safety>=50:
        recommendation="WATCH";reason="No buy planned; historical risk/recovery evidence is not strong enough."
    else:
        recommendation="DO_NOT_BUY";reason="No buy planned; historical recovery risk fails the research threshold."
    return {"safety_score":safety,"safety_score_confidence":confidence,"recommendation":recommendation,"recommendation_reason":reason,"score_authorizes_trade":False}
