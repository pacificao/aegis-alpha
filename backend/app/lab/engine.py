"""Deterministic day-by-day portfolio backtesting with no execution capability."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import date
import hashlib,json,math,random,statistics
from typing import Any

@dataclass(frozen=True)
class Bar:
    day: date; symbol: str; open: float; high: float; low: float; close: float; volume: int
@dataclass(frozen=True)
class Action:
    day: date; symbol: str; kind: str; value: float
@dataclass
class Position:
    symbol:str; shares:float; entry_day:date; entry_price:float; cost_basis:float; dividend_per_share:float; ex_day:date
@dataclass
class Trade:
    symbol:str; entry_day:date; exit_day:date; shares:float; entry_price:float; exit_price:float; dividends:float; costs:float; pnl:float; return_pct:float; holding_days:int; exit_reason:str; max_drawdown_pct:float

def _percentile(values:list[float],q:float)->float:
    if not values:return 0.0
    ordered=sorted(values); index=(len(ordered)-1)*q; lo=math.floor(index); hi=math.ceil(index)
    return ordered[lo] if lo==hi else ordered[lo]*(hi-index)+ordered[hi]*(index-lo)
def _safe_mean(values):return statistics.fmean(values) if values else 0.0
def _stdev(values):return statistics.stdev(values) if len(values)>1 else 0.0
def _round(value):return round(float(value),6)
def checksum(payload:dict)->str:return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str,allow_nan=False).encode()).hexdigest()

def simulate(bars:list[Bar],actions:list[Action],config:dict[str,Any])->dict:
    if not bars:raise ValueError("No historical bars available")
    initial=float(config["initial_capital"]); cash=initial; positions:dict[str,Position]={}; trades:list[Trade]=[]; equity_curve=[]; total_dividends=0.0; turnover=0.0
    commission=float(config["commission_per_trade"]); slippage_bps=float(config["slippage_bps"]); spread_bps=float(config["spread_bps"]); max_position=float(config["max_position_pct"])/100; max_allocation=float(config["max_allocation_pct"])/100
    entry_days=int(config["entry_days_before_ex_date"]); max_holding=int(config["max_holding_days"]); exit_method=config["exit_method"]; profit_target=float(config.get("profit_target_pct",0))/100
    by_day:dict[date,dict[str,Bar]]={}; symbol_days:dict[str,list[date]]={}
    for bar in sorted(bars,key=lambda b:(b.day,b.symbol)):
        by_day.setdefault(bar.day,{})[bar.symbol]=bar; symbol_days.setdefault(bar.symbol,[]).append(bar.day)
    dividends={(a.symbol,a.day):a.value for a in actions if a.kind=="DIVIDEND" and a.value>0}; splits={(a.symbol,a.day):a.value for a in actions if a.kind=="SPLIT" and a.value>0}
    entries:dict[tuple[str,date],tuple[date,float]]={}
    for (symbol,ex_day),amount in dividends.items():
        days=symbol_days.get(symbol,[])
        eligible=[d for d in days if d<ex_day]
        if len(eligible)>=entry_days: entries[(symbol,eligible[-entry_days])]=(ex_day,amount)
    adverse:dict[str,float]={}
    for day in sorted(by_day):
        day_bars=by_day[day]
        for symbol,position in list(positions.items()):
            bar=day_bars.get(symbol)
            if not bar:continue
            if (symbol,day) in splits:
                ratio=splits[(symbol,day)]; position.shares*=ratio; position.entry_price/=ratio
            if (symbol,day) in dividends:
                received=position.shares*dividends[(symbol,day)]; cash+=received; total_dividends+=received; position.dividend_per_share=dividends[(symbol,day)]
            adverse[symbol]=min(adverse.get(symbol,0.0),(bar.low-position.entry_price)/position.entry_price*100)
            held=sum(1 for d in symbol_days[symbol] if position.entry_day<=d<=day)-1
            target=position.entry_price
            exit_trigger=bar.close>=target; exit_reason="RECOVERED"
            if exit_method=="PURCHASE_MINUS_DIVIDEND": exit_trigger=bar.close>=position.entry_price-position.dividend_per_share;exit_reason="DIVIDEND_ADJUSTED_TARGET"
            elif exit_method=="PROFIT_TARGET": exit_trigger=bar.close>=position.entry_price*(1+profit_target);exit_reason="PROFIT_TARGET"
            elif exit_method.startswith("FIXED_"): exit_trigger=held>=int(exit_method.split("_")[1]);exit_reason="FIXED_EXIT"
            elif exit_method=="HISTORICAL_RECOVERY": exit_trigger=held>=int(config["historical_recovery_days"]);exit_reason="HISTORICAL_RECOVERY_WINDOW"
            elif exit_method=="VOLATILITY":
                volatility_target=position.entry_price-position.dividend_per_share+(bar.high-bar.low)*float(config["volatility_multiplier"])
                exit_trigger=bar.close>=volatility_target;exit_reason="VOLATILITY_TARGET"
            elif exit_method=="HYBRID":
                price_recovered=bar.close>=position.entry_price
                exit_trigger=price_recovered or held>=int(config["hybrid_time_stop_days"]);exit_reason="RECOVERED" if price_recovered else "HYBRID_TIME_STOP"
            timed_out=held>=max_holding
            if day>=position.ex_day and (exit_trigger or timed_out):
                exit_price=bar.close*(1-(slippage_bps+spread_bps/2)/10000); proceeds=position.shares*exit_price-commission; cash+=proceeds; costs=commission*2+position.shares*position.entry_price*(slippage_bps+spread_bps/2)/10000+position.shares*bar.close*(slippage_bps+spread_bps/2)/10000; pnl=proceeds-position.cost_basis+position.shares*position.dividend_per_share
                trades.append(Trade(symbol,position.entry_day,day,position.shares,position.entry_price,exit_price,position.shares*position.dividend_per_share,costs,pnl,pnl/position.cost_basis*100 if position.cost_basis else 0,held,exit_reason if exit_trigger else "TIME_STOP",adverse.get(symbol,0)))
                turnover+=position.cost_basis+proceeds; del positions[symbol]
        marked=sum(pos.shares*day_bars[pos.symbol].close for pos in positions.values() if pos.symbol in day_bars); equity=cash+marked
        for symbol,bar in day_bars.items():
            if symbol not in config["symbols"]: continue
            entry=entries.get((symbol,day))
            if not entry or symbol in positions:continue
            if entry[1]/bar.close*100<float(config.get("min_dividend_event_pct",0)):continue
            allocated=sum(pos.shares*bar.close for pos in positions.values() if pos.symbol in day_bars)
            budget=min(equity*max_position,max(0,equity*max_allocation-allocated),cash-commission)
            entry_price=bar.close*(1+(slippage_bps+spread_bps/2)/10000); shares=round(budget/entry_price,6)
            if shares<=0 or shares*entry_price<1:continue
            cost=shares*entry_price+commission; cash-=cost; positions[symbol]=Position(symbol,shares,day,entry_price,cost,entry[1],entry[0]); adverse[symbol]=0; turnover+=cost
        marked=sum(pos.shares*day_bars[pos.symbol].close for pos in positions.values() if pos.symbol in day_bars); equity_curve.append({"date":day.isoformat(),"equity":_round(cash+marked),"cash":_round(cash),"exposure_pct":_round(marked/(cash+marked)*100 if cash+marked else 0)})
    if positions:
        last=equity_curve[-1]; final_day=date.fromisoformat(last["date"])
        for symbol,position in list(positions.items()):
            bar=by_day[final_day].get(symbol)
            if not bar:continue
            exit_price=bar.close*(1-(slippage_bps+spread_bps/2)/10000); proceeds=position.shares*exit_price-commission; cash+=proceeds; held=sum(1 for d in symbol_days[symbol] if position.entry_day<=d<=final_day)-1; costs=commission*2+position.shares*position.entry_price*(slippage_bps+spread_bps/2)/10000+position.shares*bar.close*(slippage_bps+spread_bps/2)/10000; pnl=proceeds-position.cost_basis+position.shares*position.dividend_per_share
            trades.append(Trade(symbol,position.entry_day,final_day,position.shares,position.entry_price,exit_price,position.shares*position.dividend_per_share,costs,pnl,pnl/position.cost_basis*100 if position.cost_basis else 0,held,"END_OF_TEST",adverse.get(symbol,0))); turnover+=proceeds
        equity_curve[-1]["equity"]=_round(cash); equity_curve[-1]["cash"]=_round(cash); equity_curve[-1]["exposure_pct"]=0
    metrics=_metrics(equity_curve,trades,initial,total_dividends,turnover,bars,config)
    return {"configuration":config,"metrics":metrics,"equity_curve":equity_curve,"trades":[{**asdict(t),"entry_day":t.entry_day.isoformat(),"exit_day":t.exit_day.isoformat()} for t in trades],"walk_forward":_walk_forward(equity_curve),"monte_carlo":_monte_carlo(trades,initial,int(config["monte_carlo_iterations"]),int(config["random_seed"])),"trading":"DISABLED","risk_authorized":False,"executable":False}

def _metrics(curve,trades,initial,dividends,turnover,bars,config):
    values=[p["equity"] for p in curve]; returns=[values[i]/values[i-1]-1 for i in range(1,len(values)) if values[i-1]]; peak=values[0]; drawdowns=[]
    for value in values:peak=max(peak,value);drawdowns.append(value/peak-1)
    years=max((date.fromisoformat(curve[-1]["date"])-date.fromisoformat(curve[0]["date"])).days/365.25,1/365.25); total=values[-1]/initial-1; annual=total/years if years<1 else (values[-1]/initial)**(1/years)-1
    volatility=_stdev(returns)*math.sqrt(252); sharpe=_safe_mean(returns)/_stdev(returns)*math.sqrt(252) if _stdev(returns) else 0; downside=[min(0,r) for r in returns]; sortino=_safe_mean(returns)/math.sqrt(_safe_mean([r*r for r in downside]))*math.sqrt(252) if any(downside) else 0
    holding=[t.holding_days for t in trades]; recovered=[t for t in trades if t.exit_reason=="RECOVERED"]; exposure=[p["exposure_pct"] for p in curve]
    benchmark=_benchmark(bars,config.get("benchmark_symbol"))
    return {"initial_capital":initial,"ending_equity":_round(values[-1]),"total_return_pct":_round(total*100),"cagr_pct":_round(annual*100),"total_dividends":_round(dividends),"realized_pnl":_round(sum(t.pnl for t in trades)),"maximum_drawdown_pct":_round(min(drawdowns)*100),"annualized_volatility_pct":_round(volatility*100),"sharpe_ratio":_round(sharpe),"sortino_ratio":_round(sortino),"trade_count":len(trades),"recovery_rate_pct":_round(len(recovered)/len(trades)*100 if trades else 0),"failed_recoveries":len(trades)-len(recovered),"average_holding_days":_round(_safe_mean(holding)),"median_holding_days":_round(statistics.median(holding) if holding else 0),"p90_holding_days":_round(_percentile(holding,.9)),"average_exposure_pct":_round(_safe_mean(exposure)),"cash_drag_pct":_round(100-_safe_mean(exposure)),"turnover_pct":_round(turnover/initial*100),"return_per_capital_day_pct":_round(sum(t.return_pct/max(t.holding_days,1) for t in trades)),"benchmark_return_pct":benchmark,"excess_return_pct":_round(total*100-benchmark)}

def _benchmark(bars,symbol):
    rows=sorted([b for b in bars if b.symbol==symbol],key=lambda b:b.day)
    return _round((rows[-1].close/rows[0].close-1)*100) if len(rows)>1 else 0.0

def _walk_forward(curve):
    if len(curve)<4:return {"train_return_pct":0,"test_return_pct":0,"split_date":curve[-1]["date"]}
    mid=len(curve)//2; train=(curve[mid-1]["equity"]/curve[0]["equity"]-1)*100; test=(curve[-1]["equity"]/curve[mid]["equity"]-1)*100
    return {"train_return_pct":_round(train),"test_return_pct":_round(test),"split_date":curve[mid]["date"]}

def _monte_carlo(trades,initial,iterations,seed):
    returns=[t.return_pct/100 for t in trades]
    if not returns:return {"iterations":iterations,"p05_ending_equity":initial,"median_ending_equity":initial,"p95_ending_equity":initial,"seed":seed}
    rng=random.Random(seed); outcomes=[]
    for _ in range(iterations):
        equity=initial
        for _ in returns:equity*=1+rng.choice(returns)
        outcomes.append(equity)
    return {"iterations":iterations,"p05_ending_equity":_round(_percentile(outcomes,.05)),"median_ending_equity":_round(_percentile(outcomes,.5)),"p95_ending_equity":_round(_percentile(outcomes,.95)),"seed":seed}

def sensitivity(bars,actions,config):
    variants=[]
    for event_yield in (0.10,0.15,0.25):
        for entry in (1,2,3,5):
            for exit_method in ("PURCHASE_PRICE","PURCHASE_MINUS_DIVIDEND","FIXED_5","FIXED_10","FIXED_15","FIXED_30","HISTORICAL_RECOVERY","VOLATILITY","HYBRID"):
                candidate={**config,"min_dividend_event_pct":event_yield,"entry_days_before_ex_date":entry,"exit_method":exit_method,"monte_carlo_iterations":min(50,int(config["monte_carlo_iterations"]))}
                result=simulate(bars,actions,candidate); variants.append({"min_dividend_event_pct":event_yield,"entry_days":entry,"exit_method":exit_method,"total_return_pct":result["metrics"]["total_return_pct"],"maximum_drawdown_pct":result["metrics"]["maximum_drawdown_pct"],"trade_count":result["metrics"]["trade_count"]})
    return variants
