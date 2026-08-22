# Phase 6 — Aegis Risk

Aegis Risk is a deterministic authorization boundary. It evaluates a frozen proposal and portfolio snapshot against an immutable, checksummed policy. It has no broker client, AI dependency, order endpoint, scheduler, or execution adapter.

Every assessment evaluates the global kill switch, circuit breaker, quantity, notional, reference-price deviation, projected position, portfolio, sector and correlated exposure, daily loss, drawdown, annualized volatility, buying-power use, open-order count, market-data freshness, and proposal freshness. Any failed or unavailable control rejects the proposal.

For the explicitly selected Dividend Farm controlled trial only, portfolios below $100 use a deterministic $1 maximum position-value cap so Robinhood fractional-order minimums can be tested. At $100 and above, the strategy reverts to its 1% maximum. The overlay cannot relax buying power, portfolio/sector/correlation exposure, loss, drawdown, volatility, freshness, duplicate, breaker, kill-switch, approval, or execution controls.

Fractional equity quantities are supported. Risk requires at least $1 notional, verified NMS fractional eligibility, and a verified regular market session; otherwise it rejects the proposal. Planning and simulation use fractional quantities rather than requiring a whole share. Broker review remains authoritative and may reject securities that are temporarily or permanently ineligible.

Proposal identifiers and policy-plus-request checksums provide duplicate prevention and reproducibility. Identical requests return the persisted assessment; reuse of an identifier with changed content is rejected.

`AUTHORIZED` means only that supplied frozen facts passed the policy. All responses remain `executable=false` and `trading=DISABLED`. Control mutations require authentication and CSRF and create audit activity. No broker credential or OAuth material enters this subsystem.

Production acceptance completed on 2026-08-20 at version `0.5.0-risk` and migration `0009_phase6_aegis_risk`. CI and live checks verified deterministic authorization, fail-closed stale/duplicate/kill-switch behavior, persistence, authenticated boundaries, non-executability, and the absence of order or execution routes. PostgreSQL records Phase 6 as 14/14 COMPLETE.
