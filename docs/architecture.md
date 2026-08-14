# Architecture

Browser traffic enters only through Nginx. Nginx proxies UI requests to Next.js and `/api`, `/health`, login, and logout requests to FastAPI. FastAPI owns sessions, roadmap state, audit activity, SQLAlchemy access to PostgreSQL, and Redis connectivity. PostgreSQL and Redis exist only on the internal Compose network.

Future order flow is strictly `AI proposal -> deterministic strategy decision -> deterministic RiskEngine authorization -> broker-neutral execution adapter`. No component may skip a stage. Research and execution deploy into separate accounts/networks with separate identities and secret stores.

Phase 1 contains no order endpoint, broker credential, or execution implementation. `RobinhoodBrokerAdapter` is a nonfunctional interface placeholder and reports disconnected/planned. `AEGIS_TRADING_ENABLED` must be false; backend startup rejects true.

See `data-model.md`, `security-model.md`, and ADRs in `decisions/`.

