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
