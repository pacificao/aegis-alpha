# ADR 0005: Immutable deterministic strategy specifications

Status: Accepted

## Decision

Store validated strategy specifications as immutable, checksummed versions and store each research evaluation with its input facts and reason codes. The engine emits decisions but has no dependency on broker, risk authorization, or execution code.

## Rationale

Reproducibility requires the exact universe, indicators, rules, sizing, schedule, filters, and parameters used for a decision. Immutable versions prevent silent strategy drift. A deliberately small deterministic operator set keeps decisions independently testable and explainable.

## Consequences

Scenario edits do not alter historical versions. A new version is required. Proposed weights are not orders and are always marked non-executable and risk-unauthorized. Phase 5 may consume these versions for backtests; Phase 6 must independently authorize any future intent.
