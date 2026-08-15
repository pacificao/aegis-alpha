# Data Model

- `phases`: stable phase number, name, description, status metadata.
- `tasks`: phase relationship, stable ordinal, title, status (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `WAITING_FOR_CREDENTIALS`), notes, timestamps.
- `development_activity`: actor, action, entity reference, safe structured detail, timestamp.
- `broker_connection_config`: provider-unique, non-secret operator metadata: display name, the allowlisted official endpoint, read-only mode, and update timestamp. Credentials, OAuth tokens, account numbers, and private keys are prohibited.
- Alembic owns schema evolution. Roadmap definitions are idempotently seeded; mutable status and notes persist in PostgreSQL.
- Sessions are ephemeral security data in Redis rather than application tables.

