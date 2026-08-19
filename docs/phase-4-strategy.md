# Phase 4 — Aegis Strategy Engine

Phase 4 converts research scenarios into immutable, deterministic strategy specifications. It produces auditable research decisions only. It has no broker invocation, order model, execution endpoint, or risk authorization capability. Trading remains disabled.

## Specification contract

Every version explicitly defines:

- universe symbols, exclusions, and asset types;
- named source/derived indicators;
- deterministic entry and exit rules;
- fixed-percent or equal-weight sizing bounds;
- NYSE schedule, exchange timezone, frequency, and evaluation time;
- deterministic eligibility filters;
- bounded adjustable parameters.

Pydantic rejects unknown fields, unsafe symbols, unknown operators, unsupported indicator types, invalid schedules, oversized collections, and position sizes above 10%. Canonical SHA-256 checksums prevent duplicate versions. Versions are immutable; changing a scenario requires creating a new version.

## Decision contract

Evaluation requires a symbol, timezone-aware `as_of`, and explicit facts. Rules support only `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, and `not_in`. Evaluation order is universe, filters, exits, then entries. The result is one of `ENTRY`, `EXIT`, `HOLD`, or `EXCLUDE`, with reason codes and the exact supplied facts persisted for audit.

Every result contains `risk_authorized=false`, `executable=false`, and `trading=DISABLED`. An ENTRY weight is a strategy proposal bounded by the specification, never an authorization. Phase 6 RiskEngine and later isolated execution remain mandatory.

## API and UI

Authenticated APIs list/create immutable versions, evaluate a version, and retrieve its decision history. Mutations require CSRF. The Strategy Engine UI edits scenario parameters, snapshots a complete version, and previews a decision from operator-supplied facts. It clearly distinguishes this from Phase 5 backtesting and Phase 8 paper simulation.

## Phase boundary

Phase 4 does not calculate historical indicators from market records, optimize parameters, backtest, paper trade, access private portfolio data, or execute orders. Those responsibilities remain in later phases.
