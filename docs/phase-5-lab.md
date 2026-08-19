# Phase 5 — Aegis Lab

Aegis Lab is a reproducible research environment. It consumes an immutable Phase 4 strategy version and checksummed Phase 3 records, simulates a portfolio day by day, and persists the exact configuration, provenance, results, trades, and robustness evidence. It cannot call a broker, authorize risk, paper trade, or execute.

## Portfolio simulation

Cash and positions are marked each data day. Unrecovered dividend-capture positions keep capital occupied. Position and strategy allocation limits constrain new entries. The ledger models:

- explicit commission, spread, and slippage assumptions;
- cash dividends credited on ex-date;
- split-adjusted share quantity and cost basis;
- T-1/T-2/T-3/T-5 entry variants;
- purchase-price, dividend-adjusted, profit-target, fixed-day, historical-recovery, volatility, and hybrid/time-stop exits;
- final forced liquidation disclosed as `END_OF_TEST`;
- benchmark return from the same checksummed data window.

Benchmark-only symbols are prohibited from becoming strategy positions.

## Analytics and robustness

Each run stores total return, CAGR, dividends, realized P/L, maximum drawdown, annualized volatility, Sharpe, Sortino, trade count, recovery/failure rates, holding-period average/median/P90, exposure, cash drag, turnover, return per capital-day, benchmark return, and excess return. Trade inspection includes dates, prices, shares, costs, dividends, P/L, return, duration, exit reason, and adverse movement.

A deterministic train/test chronological split supplies walk-forward evidence. Seeded bootstrap Monte Carlo supplies 5th/50th/95th ending-equity outcomes. Parameter sensitivity evaluates 36 entry/exit combinations. Identical strategy, configuration, and source checksums resolve to the same persisted run.

## Bias and interpretation

Results are hypotheses, not forecasts. The current engine requires normalized OHLCV and corporate actions and discloses source record checksums. Studies must consider survivorship bias, point-in-time universe membership, corporate-action announcement availability, taxes, borrow constraints, delistings, and data licensing. A zero-trade result is valid and must not be hidden.

All responses contain `risk_authorized=false`, `executable=false`, and `trading=DISABLED`.
