# ADR 0010 — Immutable read-only broker snapshots

Status: Accepted

## Decision

Keep Phase 9 as a read-only gateway phase. Extend the provider-neutral adapter only with account snapshot reads. The isolated Robinhood gateway dynamically uses advertised schemas but may call only an exact read allowlist; its HTTP API offers one bounded aggregate snapshot and no generic tool selector. Keyed-HMAC pseudonymize private identifiers before they leave the gateway.

Persist normalized snapshots immutably with source time and canonical checksum. Persist each sync attempt separately, retry only idempotent reads, sanitize failures, reconcile account/order uniqueness and fill quantities, and expose only authenticated projections. A verified snapshot is evidence, never an order or authorization.

## Consequences

Balances, holdings, P&L inputs, and historical orders/fills can support operator decisions and communications without giving the development domain OAuth material or mutation capability. Partial reads are visible as attention state. Phase 10 must introduce a separately reviewed, human-approved execution protocol; it cannot reinterpret this read API as execution.
