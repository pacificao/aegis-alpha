# Phase 9 — Aegis Gateway

## Scope and safety boundary

Phase 9 synchronizes broker state through the official Robinhood Trading MCP and persists immutable, checksummed, read-only snapshots. It does **not** enable controlled live trading. The broker adapter and Aegis backend expose status and account-snapshot reads only; they have no place, review, cancel, or generic MCP call method. `AEGIS_TRADING_ENABLED=false` remains mandatory.

Robinhood's official documentation identifies read access to accounts, balances, positions, transactions, order history, watchlists, and scans, and documents `get_accounts`, `get_portfolio`, realized P&L, equity/option positions, and order-history tools. It also warns that an agent with mutation access can trade without confirmation. Aegis therefore exposes only its exact reviewed read allowlist and blocks every mutation or unknown tool. Sources: [Agentic Trading overview](https://robinhood.com/us/en/support/articles/agentic-trading-overview/) and [Trading with your agent](https://robinhood.com/us/en/support/articles/trading-with-your-agent/), verified 2026-08-19.

## Data flow

Operator-authenticated browser → CSRF-protected Aegis sync request → authenticated TLS request to isolated gateway → official OAuth MCP session → exact account-read tools → identifier redaction/hashing in the gateway → strict Aegis normalization → reconciliation → immutable PostgreSQL snapshot and audit run.

The gateway obtains real account numbers only transiently to supply advertised read-tool schemas. It never logs or returns them. Account/order/position identifiers are replaced with stable keyed-HMAC references before leaving the execution domain. Tokens, authorization codes, passwords, and raw credentials are rejected or redacted.

## Persistence and reconciliation

Migration `0012_phase9_gateway` adds immutable `broker_snapshots` plus `broker_sync_runs`. Snapshots contain balances, holdings, historical orders/fills, source time, checksum, safe account references, and reconciliation evidence. Runs record bounded idempotent read retries, safe error classification, timing, result, and audit linkage. Reconciliation detects duplicate account/order references, fills exceeding order quantity, partial dataset failures, and count mismatches. Failed or unsafe responses persist no snapshot.

The Portfolio page shows freshness, checksum, balances/holdings, historical orders/fills, and reconciliation. Dashboard values derive only from a verified snapshot. Returns, drawdown, sector exposure, or scenario attribution remain unavailable until sufficient linked history exists; Aegis does not estimate them.

## Deployment and acceptance

Completed 2026-08-19. The human operator deployed reviewed `main` to the isolated broker Droplet. Five accounts passed core read-only synchronization; immutable persistence, keyed-HMAC pseudonymization, order/fill reconciliation, authenticated UI, unauthenticated rejection, protected CI, service recreation, and absence of mutation surfaces were verified. Optional parameter-dependent tax-lot and realized-P&L reads remain explicit warnings rather than unsafe guesses. Trading remains disabled.
