# Phase 6 — Aegis Risk

Aegis Risk is a deterministic authorization boundary. It evaluates a frozen proposal and portfolio snapshot against an immutable, checksummed policy. It has no broker client, AI dependency, order endpoint, scheduler, or execution adapter.

Every assessment evaluates the global kill switch, circuit breaker, quantity, notional, reference-price deviation, projected position, portfolio, sector and correlated exposure, daily loss, drawdown, annualized volatility, buying-power use, open-order count, market-data freshness, and proposal freshness. Any failed or unavailable control rejects the proposal.

Proposal identifiers and policy-plus-request checksums provide duplicate prevention and reproducibility. Identical requests return the persisted assessment; reuse of an identifier with changed content is rejected.

`AUTHORIZED` means only that supplied frozen facts passed the policy. All responses remain `executable=false` and `trading=DISABLED`. Control mutations require authentication and CSRF and create audit activity. No broker credential or OAuth material enters this subsystem.
