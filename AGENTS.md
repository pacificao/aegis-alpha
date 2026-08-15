# Aegis Alpha Agent Contract

## Permanent rules

1. AI proposes.
2. Strategies decide.
3. Risk authorizes.
4. Execution executes.
5. AI never bypasses the deterministic RiskEngine.
6. Every dollar moved must be explainable and auditable.
7. Research and live execution are separate security domains.
8. Production credentials and brokerage secrets are never available to AI development agents.
8a. Never complete broker OAuth on a host or container runtime administered by an AI development agent.
9. Robinhood is the first planned broker; broker interfaces must remain provider-neutral.
10. GitHub is the permanent source of truth.
11. Ubuntu is the runtime foundation.
12. DigitalOcean is the planned production environment; this server is development.
13. Trading remains disabled until a later, explicitly authorized phase.

## Development rules

- Update `docs/development-status.md` after meaningful work.
- Never commit `.env`, credentials, tokens, session secrets, Linux passwords, brokerage secrets, or database volumes.
- Never weaken host security or modify firewall/SSH settings without the operator's explicit execution of reviewed commands.
- Keep deterministic strategy, risk, and execution boundaries independently testable.
- Add migrations for schema changes and tests for behavior changes.
- Work on `feature/*`, merge through `develop`, and promote reviewed releases to protected `main`.
- Do not claim a check passed unless it was run.
