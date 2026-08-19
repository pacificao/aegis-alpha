# ADR 0009: Independent risk-gated paper simulator

## Decision

Require a single-use deterministic RiskEngine authorization and a fresh normalized quote for every paper fill. Persist paper accounts, orders, fills, and positions separately from research and brokerage state. Apply explicit deterministic friction.

## Consequences

Paper behavior is reproducible and auditable, stale data fails closed, and risk checks remain independently testable. The simulator cannot call a broker and paper results cannot be represented as live performance. Real broker portfolio synchronization and execution remain later phases.
