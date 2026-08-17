# Dividend Farm research specification

Status: hypothesis; research configuration only. It cannot trade, schedule jobs, invoke Robinhood tools, or bypass Strategy/Risk/Execution boundaries.

## Hypothesis and event return

Buy before an ex-dividend date, capture the dividend, hold until an exit rule is met, then recycle released capital. Event yield is `cash dividend per share / entry price`; annual published yield must be divided by actual payment frequency and never treated as one-event return. The candidate objective is dividend captured per capital-day adjusted for recovery probability, drawdown, liquidity, reliability, and tail recovery time.

## Historical event analysis

For each adjusted ex-dividend event, calculate average/median and 25th/75th/90th/95th recovery days; recovery probability within 5/10/15/30/60/90 trading days; maximum recovery period; failure rate; maximum adverse excursion; dividend consistency; event yield; and return per capital-day. Exclude insufficient, unreliable, stale, survivorship-biased, or look-ahead-contaminated histories.

## Portfolio simulation

Simulate every trading day. Unrecovered positions keep capital occupied. Model corporate actions, delistings, taxes as an explicit scenario assumption, commissions, spread, slippage, liquidity, cash drag, allocation/sector caps, and simultaneous candidates. Report CAGR, dividends, realized P/L, maximum drawdown, Sharpe, Sortino, utilization, cash drag, holding-time distribution, recovery/failure rates, trade count, turnover, and return per capital-day against buy-and-hold and dividend benchmarks.

## Configurable Phase 2 parameters

The seeded UI configuration includes maximum position/allocation; annual/event yield bounds; payment frequencies; history/events minimums; median/P90 recovery limits; minimum recovery probability; drawdown/holding limits; market cap/volume; sector cap; earnings exclusion; REIT/ETF/special-dividend inclusion; entry day; exit method/profit target; and reinvestment. New custom research scenarios may also be created. Values are inert until later engines consume versioned specifications.

## Required research variants

Test entry at T-1/T-2/T-3/T-5 and exits at purchase price, purchase minus dividend, configurable profit, fixed 5/10/15/30 days, historical recovery, volatility, and hybrid recovery/time-stop. Use out-of-sample/walk-forward analysis, parameter sensitivity, regime segmentation, multiple-testing controls, and benchmark comparison.

## Promotion gates

Research requires Phase 3 data and Phases 4–5 strategy/backtest engines. Real-time no-money testing requires the isolated Phase 8 simulator. Controlled live requires Phase 6 risk controls, Phase 9 execution safeguards, Phase 10 per-order human approval, and explicit operator authorization. Continuous unattended trading is not eligible before Phase 11 bounded autonomy and remains disabled now.
