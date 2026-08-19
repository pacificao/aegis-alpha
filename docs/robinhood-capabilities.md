# Robinhood capability plan

Aegis uses only Robinhood's official Trading MCP at `https://agent.robinhood.com/mcp/trading`. The isolated gateway owns OAuth tokens. Aegis receives normalized results over an authenticated internal endpoint; credentials never enter the browser, backend database, or development logs. Trading remains disabled.

## Implemented read-only market data

The gateway fail-closed allowlist and Data Sources UI support historical equities, fundamentals, financial statements, price books, technical indicators, earnings results/calendar, indexes/quotes, equity quotes/tradability, option history/chains/instruments/quotes, currency pairs, and crypto quotes. Requests are CSRF-protected, audited, size-bounded, credential-rejecting, provenance-tagged, and stored in the Phase 3 data model.

## Planned use

- Near term: scheduled quotes, fundamentals, earnings, tradability, and available historical bars; compare overlapping fields with Alpha Vantage.
- Research phases: option-chain/history analytics, technical indicators, market scans, popular lists, and earnings-event exclusions.
- Portfolio phases: accounts, portfolio, positions, tax lots, realized P&L, trade history, and order history. These contain private account data and remain outside the public-market ingestion endpoint.
- Execution phases: review, place, cancel, watchlist mutation, scan mutation, and every unknown tool remain blocked. Future order capability may exist only behind deterministic Strategy, RiskEngine, and isolated Execution boundaries after explicit authorization.

## Provider roles

Robinhood is preferred for broker truth, current portfolio state, real-time quotes, earnings, options, and its available price history. Alpha Vantage remains the reproducible research/backfill source for deep adjusted equity history, independent cross-checking, dividend-event history, and news. SEC EDGAR remains authoritative for filings/company facts; FRED remains authoritative for macroeconomic series. Robinhood's documentation does not guarantee multi-decade bulk-universe depth, point-in-time constituent history, delisted-security coverage, or backtest redistribution rights, so it is not the sole research archive.

Official inventory: https://robinhood.com/us/en/support/articles/trading-with-your-agent/
