# ADR 0006: Reproducible research artifacts

Status: Accepted

## Decision

A Lab run is identified by the immutable strategy checksum, complete validated configuration, and sorted source-record checksums. Results, equity curve, trades, walk-forward split, seeded Monte Carlo distribution, sensitivity grid, and provenance are persisted as one research artifact.

## Rationale

A backtest without exact strategy, assumptions, and data identity cannot be reproduced or audited. Explicit friction and corporate-action handling prevents silent optimistic defaults. Research must remain structurally unable to create an order.

## Consequences

New source records or parameter changes create a different artifact. Identical inputs return the existing run. Lab results are displayed as research and never substituted for portfolio performance. Phase 6 risk and later simulation/execution boundaries remain independent.
