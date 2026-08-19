# Robinhood capability plan

Aegis uses only Robinhood's official Trading MCP at `https://agent.robinhood.com/mcp/trading`. The isolated gateway owns OAuth tokens. Aegis receives normalized results over an authenticated internal endpoint; credentials never enter the browser, backend database, or development logs. Trading remains disabled.

## Implemented and live-validated read-only market data

The gateway discovers Robinhood's currently advertised schemas and intersects them with a fail-closed market-data allowlist. On 2026-08-18 the connected production gateway advertised and successfully served equity historicals, fundamentals, financial statements, price books, technical indicators, earnings results/calendar, indexes/quotes, equity quotes, and option history/chains/instruments/quotes. Representative equity, earnings, index, and option-chain responses were persisted in the Phase 3 data model with provenance. Account-specific tradability was advertised but intentionally not exercised during public-data validation.

Robinhood did not advertise crypto market-data tools in this session. Aegis therefore treats crypto coverage as unavailable even though known read names are policy-safe; it will never invoke an unadvertised tool. Requests are CSRF-protected, audited, size-bounded, credential-rejecting, and provenance-tagged. Live schema discovery exposes only safe public tool metadata, never private account tools, results, tokens, or mutation capabilities.

The historical endpoint accepts explicit RFC3339 ranges, split-adjusted daily bars, and intervals extending through long-duration bars. This materially improves research ingestion, but observed availability for each symbol/range must still be measured; advertised interval support is not proof of complete point-in-time or delisted-security coverage.

## Planned use

- Near term: schedule quotes, fundamentals, earnings, and available historical bars; compare overlapping fields with Alpha Vantage and record disagreements as data-quality evidence.
- Research phases: option-chain/history analytics, technical indicators, market scans, popular lists, and earnings-event exclusions.
- Portfolio phases: accounts, portfolio, positions, tax lots, realized P&L, trade history, and order history. These contain private account data and remain outside the public-market ingestion endpoint.
- Execution phases: review, place, cancel, watchlist mutation, scan mutation, and every unknown tool remain blocked. Future order capability may exist only behind deterministic Strategy, RiskEngine, and isolated Execution boundaries after explicit authorization.

## Provider roles

Robinhood is preferred for broker truth, current portfolio state, real-time quotes, earnings, options, technical snapshots, and available price history. Alpha Vantage remains the independent equity cross-check and the currently validated source for dividend-event history and news; premium Alpha Vantage is useful only when Aegis needs deeper adjusted backfill or bulk history that Robinhood coverage tests cannot satisfy. SEC EDGAR remains authoritative for filings/company facts; FRED remains authoritative for macroeconomic series. Robinhood's documentation does not guarantee multi-decade bulk-universe depth, point-in-time constituent history, delisted-security coverage, or backtest redistribution rights, so it is not the sole research archive.

Official inventory: https://robinhood.com/us/en/support/articles/trading-with-your-agent/
