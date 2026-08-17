# ADR 0003: Phase 2 scenarios are inert research configuration

Accepted 2026-08-17.

The console may create and edit bounded, persisted strategy scenario parameters. In Phase 2 the only lifecycle values are `RESEARCH` and `PAUSED`. API validation and a database constraint reject paper/live states.

Scenario records have no market-data, scheduler, broker, risk, or execution capability. The Dividend Farm seed is a hypothesis and configuration template, not a claim of profitability or an executable strategy.

Progression remains Research (Phases 4–5) → Paper Trading (Phase 8) → Controlled Live with per-order approval (Phase 10) → bounded autonomy (Phase 11). Each later transition requires deterministic controls, tests, audit evidence, and explicit authorization.
