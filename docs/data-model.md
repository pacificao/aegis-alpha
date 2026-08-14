# Data Model

- `phases`: stable phase number, name, description, status metadata.
- `tasks`: phase relationship, stable ordinal, title, status (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`), notes, timestamps.
- `development_activity`: actor, action, entity reference, safe structured detail, timestamp.
- Alembic owns schema evolution. Roadmap definitions are idempotently seeded; mutable status and notes persist in PostgreSQL.
- Sessions are ephemeral security data in Redis rather than application tables.

