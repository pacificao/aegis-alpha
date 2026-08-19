# Development Roadmap

The complete task-level roadmap is canonically defined in `backend/app/roadmap_data.py`, seeded idempotently into PostgreSQL, and displayed on the authenticated Development Roadmap page with persistent status and notes.

1. **Aegis Core / Foundation** — 69 tasks covering repository/workflow, Ubuntu tooling, architecture documentation, Docker, FastAPI, PostgreSQL, Redis, Next.js, health/status, structured logging/config, UI/dashboard, SQLAlchemy/Alembic, secrets/security/firewall, test/CI, environment/deployment planning, and future Robinhood placeholders. Definition of done is in `phase-1-completion.md`.
2. **Aegis Console** — authentication improvements, dashboard/navigation, portfolio, strategy, settings, activity, and responsive UI.
3. **Aegis Data** — provider abstraction, historical/realtime/fundamental/economic/news data, normalization, cache, quality, market calendar, and lawful public-source provenance.
4. **Aegis Strategy Engine** — specification, universe, indicators, rules, sizing, schedules, filters, parameters, and versions.
5. **Aegis Lab** — backtesting, market frictions/actions, benchmarks, robust validation, risk metrics, exposure, and trade inspection.
6. **Aegis Risk** — deterministic engine, exposure/loss/drawdown/volatility limits, sanity and buying-power checks, deduplication, stale-data controls, breakers, and kill switch.
7. **Aegis Intelligence** — AI-assisted creation/critique/research/review/detection, Strategy Council, cited briefings, and independent proposal verification. Aegis/verifier agreement may advance only preauthorized low-risk proposals to deterministic RiskEngine review; disagreement, missing evidence, or verifier failure escalates to the human operator or fails closed. High-impact actions always require human approval. AI never bypasses RiskEngine.
8. **Aegis Simulator** — live-data simulation, paper execution/fills/portfolio, isolation, and performance.
9. **Aegis Gateway** — broker abstraction, Robinhood Agentic/MCP, synchronization, orders/fills/reconciliation, failure handling, audit, and safeguards.
10. **Aegis Controlled Live** — real capital with per-order human approval and intent/fill/state/risk validation; one explicitly selected Agentic MCP account; parameterized tax-lot and realized-P&L reads; and remediation of the pre-existing port-21 listener before authorization.
11. **Aegis Autonomy** — strategy, capital, asset, size, loss, portfolio, and granular permission bounds.
12. **Aegis Evolution** — continuous research/refinement/allocation/regime selection, agent evaluation, new data/brokers/assets, optional local inference, and provider-neutral scheduled/audited operator notifications.

Task wording in the canonical data file exactly drives the web UI so documentation, persistence, and presentation cannot drift independently.

