from __future__ import annotations
from datetime import UTC,datetime
from typing import Any

def _check(code:str,passed:bool,actual:float|str|bool,limit:float|str|bool,detail:str)->dict:
    return {"code":code,"passed":passed,"actual":actual,"limit":limit,"detail":detail}

def evaluate(policy:dict[str,Any],proposal:dict[str,Any],controls:dict[str,bool],now:datetime|None=None)->dict:
    """Evaluate a frozen proposal/snapshot. No I/O, broker, AI, or execution dependency."""
    now=(now or datetime.now(UTC)).astimezone(UTC)
    side=proposal["side"]; quantity=float(proposal["quantity"]); price=float(proposal["price"]); reference=float(proposal["reference_price"])
    notional=quantity*price; fractional=abs(quantity-round(quantity))>1e-9; portfolio=float(proposal["portfolio_value"]); buying_power=float(proposal["buying_power"])
    increase=notional if side=="BUY" else 0.0
    projected_position=float(proposal["current_position_value"])+increase
    projected_exposure=float(proposal["total_exposure_value"])+increase
    projected_sector=float(proposal["sector_exposure_value"])+increase
    projected_correlation=float(proposal["correlated_exposure_value"])+increase
    age=(now-proposal["market_data_as_of"].astimezone(UTC)).total_seconds()
    proposal_age=(now-proposal["proposal_created_at"].astimezone(UTC)).total_seconds()
    deviation=abs(price-reference)/reference*10000
    percent_position_limit=portfolio*policy["max_position_pct"]/100
    micro_trial=bool(policy.get("micro_account_trial_eligible",False)) and portfolio<float(policy.get("micro_account_portfolio_threshold",100.0))
    position_limit=max(percent_position_limit,float(policy.get("micro_account_max_position_notional",1.0))) if micro_trial else percent_position_limit
    c=[
      _check("KILL_SWITCH_CLEAR",not controls["kill_switch_engaged"],controls["kill_switch_engaged"],False,"Global kill switch must be clear"),
      _check("CIRCUIT_BREAKER_CLEAR",not controls["circuit_breaker_engaged"],controls["circuit_breaker_engaged"],False,"Circuit breaker must be clear"),
      _check("ORDER_QUANTITY",0<quantity<=policy["max_order_quantity"],quantity,policy["max_order_quantity"],"Quantity must be positive and bounded"),
      _check("MINIMUM_NOTIONAL",notional>=float(policy.get("min_order_notional",1.0)),notional,policy.get("min_order_notional",1.0),"Robinhood equity orders require at least $1 notional"),
      _check("FRACTIONAL_ELIGIBILITY",not fractional or bool(proposal.get("fractional_eligible")),proposal.get("fractional_eligible"),True,"Fractional quantity requires Robinhood-validated NMS candidate eligibility; broker review is final"),
      _check("FRACTIONAL_SESSION",not fractional or bool(proposal.get("regular_session")),proposal.get("regular_session"),True,"Fractional order requires a verified regular market session"),
      _check("ORDER_NOTIONAL",0<notional<=policy["max_order_notional"],notional,policy["max_order_notional"],"Order notional limit"),
      _check("PRICE_SANITY",0<price and deviation<=policy["max_price_deviation_bps"],round(deviation,6),policy["max_price_deviation_bps"],"Price deviation from reference"),
      _check("POSITION_LIMIT",side=="SELL" or projected_position<=position_limit,projected_position,position_limit,"Projected position limit (controlled micro-account exception)" if micro_trial else "Projected position limit"),
      _check("PORTFOLIO_EXPOSURE",side=="SELL" or projected_exposure<=portfolio*policy["max_portfolio_exposure_pct"]/100,projected_exposure,portfolio*policy["max_portfolio_exposure_pct"]/100,"Projected gross exposure limit"),
      _check("SECTOR_EXPOSURE",side=="SELL" or projected_sector<=portfolio*policy["max_sector_exposure_pct"]/100,projected_sector,portfolio*policy["max_sector_exposure_pct"]/100,"Projected sector exposure limit"),
      _check("CORRELATION_EXPOSURE",side=="SELL" or projected_correlation<=portfolio*policy["max_correlated_exposure_pct"]/100,projected_correlation,portfolio*policy["max_correlated_exposure_pct"]/100,"Projected correlated exposure limit"),
      _check("DAILY_LOSS",side=="SELL" or float(proposal["daily_pnl_pct"])>=-policy["max_daily_loss_pct"],proposal["daily_pnl_pct"],-policy["max_daily_loss_pct"],"Daily loss boundary"),
      _check("DRAWDOWN",side=="SELL" or float(proposal["drawdown_pct"])<=policy["max_drawdown_pct"],proposal["drawdown_pct"],policy["max_drawdown_pct"],"Portfolio drawdown boundary"),
      _check("VOLATILITY",side=="SELL" or float(proposal["annualized_volatility_pct"])<=policy["max_annualized_volatility_pct"],proposal["annualized_volatility_pct"],policy["max_annualized_volatility_pct"],"Annualized volatility boundary"),
      _check("BUYING_POWER",side=="SELL" or notional<=buying_power*policy["max_buying_power_use_pct"]/100,notional,buying_power*policy["max_buying_power_use_pct"]/100,"Buying-power use boundary"),
      _check("SELL_POSITION_AVAILABLE",side=="BUY" or notional<=float(proposal["current_position_value"]),notional,proposal["current_position_value"],"Sell cannot exceed the supplied current position"),
      _check("OPEN_ORDERS",int(proposal["open_order_count"])<policy["max_open_orders"],proposal["open_order_count"],policy["max_open_orders"],"Open-order count boundary"),
      _check("MARKET_DATA_FRESH",0<=age<=policy["max_market_data_age_seconds"],round(age,3),policy["max_market_data_age_seconds"],"Market data freshness"),
      _check("PROPOSAL_FRESH",0<=proposal_age<=policy["max_proposal_age_seconds"],round(proposal_age,3),policy["max_proposal_age_seconds"],"Proposal freshness"),
    ]
    failed=[x["code"] for x in c if not x["passed"]]
    return {"outcome":"AUTHORIZED" if not failed else "REJECTED","reason_codes":failed or ["ALL_CONTROLS_PASSED"],"checks":c,"notional":round(notional,6),"risk_authorized":not failed,"executable":False,"trading":"DISABLED"}
