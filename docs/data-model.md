# Data Model

- `phases`: stable phase number, name, description, status metadata.
- `tasks`: phase relationship, stable ordinal, title, status (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `WAITING_FOR_CREDENTIALS`), notes, timestamps.
- `development_activity`: actor, action, entity reference, safe structured detail, timestamp.
- `broker_connection_config`: provider-unique, non-secret operator metadata: display name, the allowlisted official endpoint, read-only mode, and update timestamp. Credentials, OAuth tokens, account numbers, and private keys are prohibited.
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
