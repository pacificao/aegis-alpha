# Architecture

Browser traffic enters only through Nginx. Nginx proxies UI requests to Next.js and `/api`, `/health`, login, and logout requests to FastAPI. FastAPI owns sessions, roadmap state, audit activity, SQLAlchemy access to PostgreSQL, and Redis connectivity. PostgreSQL and Redis exist only on the internal Compose network.

Nginx uses Docker embedded DNS with dynamically resolved, shared-memory upstream zones for frontend, backend, and the local gateway. Recreated application containers therefore do not leave Nginx pinned to obsolete container addresses; persistent post-deployment 502 responses do not require an Nginx restart. Single-replica replacement can still produce a brief unavailable interval while the replacement becomes healthy. Long-running Python gateway containers run behind Docker init so terminated health-check children are reaped.

Future order flow is strictly `AI proposal -> deterministic strategy decision -> deterministic RiskEngine authorization -> broker-neutral execution adapter`. No component may skip a stage. Research and execution deploy into separate accounts/networks with separate identities and secret stores.
The Aegis browser talks only to FastAPI. FastAPI coordinates a narrow broker gateway API for status, OAuth start, and disconnect; it cannot select MCP tools. The gateway alone holds encrypted OAuth material and its exact read-tool allowlist. Real authorization is deployed in a separate execution security domain that the development AI cannot administer.

Phase 1 originally contained no execution implementation. The later controlled-live boundary now provides exact review, place and cancel routes only through the isolated broker gateway. Both deployment flags default false; a short-lived operator authorization, immutable intent and approval checksums, fresh deterministic RiskEngine authorization, clear global controls, single-account scope, idempotency and broker reconciliation are all mandatory.

Phase 2 adds authenticated console projections for portfolio-boundary status, research scenario configuration, operator preferences, and audit history. Scenario persistence is configuration only: it cannot fetch market data, run a backtest, paper trade, authorize risk, invoke the broker gateway, or execute an order. Paper execution belongs to Phase 8 and live authorization to Phases 10–11.

See `data-model.md`, `security-model.md`, and ADRs in `decisions/`.


## Phase 3 data flow

Official provider → allowlisted adapter → normalization → deterministic quality checks → PostgreSQL → bounded Redis cache → authenticated research APIs/UI.

The data layer cannot call RiskEngine or execution. Provider replacement is isolated behind adapters. UTC is authoritative; NYSE and Pacific headquarters time are explicit edge concerns. See `decisions/0004-data-provider-boundary.md`.

## Phase 5 research boundary

Aegis Lab depends inward on immutable Strategy Engine versions and trusted Data records. Its deterministic simulator produces persisted research artifacts and has no dependency on `BrokerGatewayClient`, RiskEngine, paper execution, or live execution. Lab evidence may inform later proposals but cannot authorize or execute them.


## Phase 6 risk boundary

Strategy proposals enter a pure deterministic RiskEngine with an immutable policy and frozen portfolio/market snapshot. It persists every check and reason code. Risk has no broker or execution dependency; authorization remains non-executable while trading is disabled. Kill switch, circuit breaker, duplicates, stale evidence, and missing facts fail closed.

## Aegis Intelligence (Phase 7)

Provider/model clients submit bounded cited artifacts to the authenticated Intelligence API. PostgreSQL stores immutable evidence/checksum artifacts and independent reviews. The Strategy Council deterministically derives `HUMAN_REVIEW`, `REJECTED`, or `ELIGIBLE_FOR_RISK_REVIEW`; it never authorizes risk. The existing deterministic RiskEngine remains the sole authorization boundary and execution remains absent.

## Aegis Simulator (Phase 8)

The paper domain consumes only persisted RiskEngine authorizations and normalized quotes. It owns separate paper account/order/fill/position tables and has no broker dependency. Paper state never mutates research, risk policy, broker state, or live portfolios.

## Aegis Gateway (Phase 9)

The Aegis backend can request one bounded read-only account snapshot from the isolated gateway. The gateway discovers official schemas, invokes only exact account/portfolio/position/order-history reads, hashes private identifiers, and returns no OAuth material. Aegis normalizes, reconciles, checksums, persists, and projects the immutable snapshot. Neither side exposes generic MCP invocation or order/review/cancel methods. Phase 9 broker history remains separate from Phase 8 paper state and Phase 6 risk authorization.


The multi-source evidence boundary projects approved normalized records into bounded checksummed symbol bundles for Intelligence consumers. News and future social signals are marked untrusted event inputs. The Codex verifier is an outbound, no-tool, non-executing reviewer; its credential is injected only into the backend runtime and its output can never set `risk_authorized` or call execution.

## Market-data scheduler boundary

The ingestion worker shares only the data and broker-read networks. It has no edge listener, PAM mount, OpenAI credential, execution endpoint or trading authority. It may call allowlisted official market-data tools and public-data providers, persist immutable evidence, and update queue state. Provider responses remain evidence only; Strategy, deterministic RiskEngine and Execution boundaries are unchanged.
