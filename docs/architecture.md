# Architecture

Browser traffic enters only through Nginx. Nginx proxies UI requests to Next.js and `/api`, `/health`, login, and logout requests to FastAPI. FastAPI owns sessions, roadmap state, audit activity, SQLAlchemy access to PostgreSQL, and Redis connectivity. PostgreSQL and Redis exist only on the internal Compose network.

Future order flow is strictly `AI proposal -> deterministic strategy decision -> deterministic RiskEngine authorization -> broker-neutral execution adapter`. No component may skip a stage. Research and execution deploy into separate accounts/networks with separate identities and secret stores.
The Aegis browser talks only to FastAPI. FastAPI coordinates a narrow broker gateway API for status, OAuth start, and disconnect; it cannot select MCP tools. The gateway alone holds encrypted OAuth material and its exact read-tool allowlist. Real authorization is deployed in a separate execution security domain that the development AI cannot administer.

Phase 1 contains no order endpoint, broker credential, or execution implementation. `RobinhoodBrokerAdapter` is a status-only provider-neutral boundary. The System page can persist non-secret Robinhood connection metadata (display name and the exact official endpoint) but cannot accept credentials, arbitrary endpoints, or invoke MCP tools. `AEGIS_TRADING_ENABLED` must be false; backend startup rejects true.

Phase 2 adds authenticated console projections for portfolio-boundary status, research scenario configuration, operator preferences, and audit history. Scenario persistence is configuration only: it cannot fetch market data, run a backtest, paper trade, authorize risk, invoke the broker gateway, or execute an order. Paper execution belongs to Phase 8 and live authorization to Phases 10–11.

See `data-model.md`, `security-model.md`, and ADRs in `decisions/`.


## Phase 3 data flow

Official provider → allowlisted adapter → normalization → deterministic quality checks → PostgreSQL → bounded Redis cache → authenticated research APIs/UI.

The data layer cannot call RiskEngine or execution. Provider replacement is isolated behind adapters. UTC is authoritative; NYSE and Pacific headquarters time are explicit edge concerns. See `decisions/0004-data-provider-boundary.md`.

## Phase 5 research boundary

Aegis Lab depends inward on immutable Strategy Engine versions and trusted Data records. Its deterministic simulator produces persisted research artifacts and has no dependency on `BrokerGatewayClient`, RiskEngine, paper execution, or live execution. Lab evidence may inform later proposals but cannot authorize or execute them.
