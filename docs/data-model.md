# Data Model

- `phases`: stable phase number, name, description, status metadata.
- `tasks`: phase relationship, stable ordinal, title, status (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `WAITING_FOR_CREDENTIALS`), notes, timestamps.
- `development_activity`: actor, action, entity reference, safe structured detail, timestamp.
- `broker_connection_config`: provider-unique, non-secret operator metadata: display name, the allowlisted official endpoint, read-only mode, one keyed-HMAC `selected_account_ref`, and update timestamp. Credentials, OAuth tokens, account numbers, and private keys are prohibited.
- `strategy_scenarios`: unique name, research strategy type, description, Phase 2 lifecycle (`RESEARCH` or `PAUSED`), bounded JSON parameters, and timestamps. Live/paper states are rejected at both API and database layers.
- `operator_preferences`: operator-unique display density, bounded page size, mandatory sensitive-action confirmation, and update timestamp.
- Alembic owns schema evolution. Roadmap definitions are idempotently seeded; mutable status and notes persist in PostgreSQL.
- Sessions are ephemeral security data in Redis rather than application tables.


## Phase 3 trusted data

- `data_providers`: source identity, type, credential readiness, enablement, last success, and redacted error classification.
- `instruments`: provider-neutral symbol, asset type, exchange, currency, CIK, activation, and metadata.
- `data_records`: normalized OHLCV, quote, fundamental, corporate-action, economic, and news records with event/observation/ingestion times, provenance, interval, checksum, and quality status.
- `ingestion_runs`: dataset-level audit of status, accepted/rejected counts, timing, and bounded detail.
- `data_quality_issues`: immutable severity/code/detail findings linked to normalized records.

Uniqueness on provider, data type, and canonical checksum makes retries idempotent. Provider payloads remain JSON so source evolution does not force execution-layer coupling; normalized identifiers and timestamps remain queryable columns.

## Phase 5 research artifacts

`lab_runs` binds an immutable strategy version to the complete backtest configuration and Phase 3 record checksums. It stores metrics, equity curve, walk-forward, Monte Carlo, sensitivity, provenance, status, actor, and timestamp. `(strategy_version_id, configuration_checksum)` is unique. `lab_trades` stores inspectable simulated trade ledger rows and cascades only when its owning Lab run is removed. Lab records contain no broker credential, order, approval, or execution state.


## Phase 6 risk artifacts

- `risk_policies`: immutable version, configuration, checksum and active marker.
- `risk_control_state`: singleton global kill-switch/circuit-breaker state with operator reason.
- `risk_assessments`: proposal snapshot, deterministic checks, reason codes, outcome, notional and authorization flag. Records are non-executable.

## Phase 7 intelligence

- `intelligence_artifacts`: typed thesis, recommendation, confidence, cited evidence snapshot, structured counter-analysis, checksum, governance state, and permanent false risk-authorization flag.
- `intelligence_reviews`: checksum-bound independent reviewer verdict, confidence, rationale, identity, and timestamp.

## Phase 8 simulator

- `paper_accounts`: isolated initial cash, cash, and realized P&L.
- `paper_orders`: single-use RiskAssessment and quote provenance, intent, status, and audit identity.
- `paper_fills`: deterministic price, quantity, commission, slippage, and time.
- `paper_positions`: account/symbol quantity and average cost.

## Phase 9 gateway snapshots

- `broker_snapshots`: immutable provider, status, hashed account references, normalized balance/holding/order/fill projections, reconciliation evidence, source time, checksum, and actor. No credential or full account number is permitted.
- `broker_sync_runs`: append-only status, bounded read-attempt count, safe error code/detail, snapshot reference, and timing.

Retries are idempotent by canonical snapshot checksum. Historical broker orders/fills are observations only and cannot be submitted, edited, cancelled, or converted to executable objects. Phase 10 scopes every synchronization request to exactly one operator-selected pseudonymous account; the gateway filters before any account-specific tool call and the backend independently rejects multiple or mismatched account references.

## Multi-strategy data policy and pilot sizing (2026-08-19)

Aegis uses a tiered, provider-neutral evidence model. Core evidence is adjusted daily OHLCV, current quotes, volume/liquidity, company fundamentals and reported financials, dividends/splits, earnings dates/results, and macro series. Strategy-specific evidence adds technical indicators and Level 2 depth for short-horizon strategies; option chains, instruments, quotes, Greeks/volatility where licensed, and option history for options research; and borrow availability, borrow fees, short interest and locate constraints before any short strategy can progress beyond research. The current official Robinhood MCP supports equity history, fundamentals, financials, technicals, Level 2, earnings, option chains/instruments/quotes/history, and long equity/option order review. It does not establish a short-selling execution capability for Aegis.

Event intelligence is a separate evidence class: licensed news metadata/sentiment, SEC filings, issuer releases, earnings transcripts where licensed, and economic releases. Social signals may be added only as untrusted leading indicators with source identity, publication and observation timestamps, provenance, manipulation/bot risk, confidence, corroboration, and expiry. Neither news nor social sentiment can independently authorize risk or execution. Store licensed article bodies only when terms permit; otherwise retain metadata, URL, bounded excerpt, derived features and checksums.

The 16-symbol pilot covered indexes/ETFs, large growth, momentum, value, dividend/income, energy, financials, small-cap exposure and options-heavy underlyings. Alpha Vantage accepted 1,255 new records with zero quality rejections. The database is 13.1 MiB and `data_records` including indexes is 2.6 MiB. Across represented pilot symbols, stored tuple data averaged about 86 KiB per symbol at partial coverage; OHLCV averaged 285 bytes/row and news 1.6 KiB/item. A compact 100-bar plus 50-news package is approximately 0.1-0.3 MiB of tuple data, typically 0.2-0.6 MiB including relational overhead. Full daily history is expected to remain low-single-digit MiB per symbol. Repeated option-chain, quote, Level 2 and intraday snapshots will dominate capacity and require bounded universes, deduplication, aggregation and retention tiers.

The configured Alpha Vantage key is limited to 25 requests/day despite earlier expectations of 100, and provider responses request at least one second between calls. Collection must therefore use a quota-aware scheduler and Robinhood MCP batching for approved official market reads. The provider disclosed the key inside a throttle message; 14 persisted messages were redacted and ingestion now sanitizes API keys, URL credentials, tokens, passwords, secrets and authorization values before persistence. The key must be rotated by the operator.

## Scheduled universe ingestion

`ingestion_jobs` is the durable provider-neutral work ledger. A unique canonical key prevents duplicate provider/dataset/symbol/cadence jobs. Priority, availability, attempts, bounded retries, completion state and sanitized detail survive restarts. Active listing candidates are not treated as Robinhood-available merely because another provider lists them; a successful official Robinhood market-data read records validation. The daily master catalog comes from Nasdaq Trader official Nasdaq-listed and other-exchange-listed directories and covers non-test equities, ETFs, CEFs, ADRs, preferreds, and warrants without coupling discovery to a strategy. Raw daily history is retained, while indicators are computed from immutable bars. Intraday and option-history streams require explicit universe and retention tiers.
