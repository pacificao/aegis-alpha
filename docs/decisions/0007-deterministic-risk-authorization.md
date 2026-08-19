# ADR 0007 — Deterministic risk authorization

Status: Accepted

Persist immutable checksummed risk policies and complete request snapshots, check results, reason codes, and outcomes. Risk evaluation is a pure function with no AI, broker, or execution dependency. Duplicate identifiers, stale evidence, breached limits, circuit breakers, and the kill switch fail closed.

Risk decisions are reproducible and auditable. Authorization never implies execution: Phase 6 has no order method and always returns `executable=false`, while global trading configuration remains disabled.
