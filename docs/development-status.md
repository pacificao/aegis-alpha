# Development Status

- Current phase: Phase 9 — Aegis Gateway COMPLETE; Phase 10 controlled-trial readiness is IN PROGRESS
- Current version: `0.8.0-gateway`
- Verified roadmap state: Phase 1 69/69 COMPLETE; Phase 2 8/8 COMPLETE; Phase 3 12/12 COMPLETE; Phase 4 10/10 COMPLETE; Phase 5 14/14 COMPLETE; Phase 6 14/14 COMPLETE; Phase 7 14/14 COMPLETE; Phase 8 6/6 COMPLETE; Phase 9 14/14 COMPLETE
- Trading: DISABLED by configuration validation and absence of any order endpoint/method.

## Verified 2026-08-14 through 2026-08-15

- Repository visibility is public but licensing is proprietary/all-rights-reserved. Public-hardening removes embedded operator/host identifiers, keeps deployment state outside Git, adds CODEOWNERS, security reporting, Dependabot, and full-history Gitleaks CI. GitHub secret scanning, push protection, vulnerability alerts, security updates, and private vulnerability reporting are enabled where the account plan supports them.
- Independent dependency audits after the public transition report zero known vulnerabilities: backend and broker gateway `pip-audit`, plus frontend `npm audit`. FastAPI/Starlette, python-multipart, pytest, and cryptography were moved to fixed versions and their tests pass.
- Production/read-only broker hardening now validates OAuth redirects against HTTPS Robinhood-owned hosts, rejects nonstandard ports, makes the single MCP invocation path policy-enforced, rejects symlink token targets and world-readable encryption keys, forces the ciphertext directory to `0700`, and durably fsyncs encrypted token replacement. The deployment `.env` permission was corrected from `0664` to `0600`. See `docs/production-broker-handoff.md` for the operator-only deployment and OAuth procedure.
- A reviewed Ubuntu 24.04 bootstrap package is prepared for the dedicated broker target at `10.124.0.4` / `brokerage.aegis-alpha.pacificao.com`. It separates the public OAuth callback origin from the Aegis UI return origin, preserves the verified active SSH port before enabling UFW, generates secrets only on the broker host, enables authorization there, and admits the Aegis VPC source `10.124.0.3` to the authenticated internal API.
- The dedicated gateway was subsequently installed and verified healthy over public TLS with `trading=DISABLED`; its container port `8100` is localhost-only and UFW is default-deny. Aegis backend routing uses the TLS hostname mapped to VPC address `10.124.0.4`, so authenticated internal traffic stays on the private link while certificate hostname validation remains intact.
- Robinhood's OAuth protected-resource metadata binds authorization to the full MCP URL, not only its origin. The gateway now supplies the full official MCP endpoint to SDK resource validation; a regression assertion prevents the origin-only configuration that Robinhood rejects before browser authorization.
- Robinhood's authorization-server metadata advertises the single OAuth scope `internal`. Because the MCP SDK omits scope unless client metadata supplies it, the gateway now requests that exact advertised scope; no broader or invented scope is permitted.
- Disconnect now atomically cancels and awaits an active OAuth task, cancels pending callback/authorization futures, clears encrypted registration/token data, and resets all in-memory flow references. Connect opens Robinhood in a separate browser tab while Aegis remains open; popup blocking is reported without starting a hidden authorization attempt.
- Public, proprietary GitHub repository `pacificao/aegis-alpha`, authenticated `gh`, protected `main`/`develop`, and `feature/*` workflow. Both protected branches require PRs plus backend, Compose, frontend, gateway, and secret-scan checks; admin enforcement is enabled and force-push/deletion are disabled.
- Host Docker Buildx plugin installed and verified: `docker-buildx 0.30.1-0ubuntu1~24.04.1`; `docker buildx version` reports 0.30.1.
- Compose stack: PostgreSQL, Redis, isolated broker gateway, FastAPI, Next.js, and Nginx healthy. Alembic is at `0005_phase2_console` (head).
- Public listeners: SSH 22 and Nginx HTTP 80/HTTPS 443. UFW is active, default-deny inbound, allowing 22/80/443. `aegis-alpha.pacificao.com` uses a valid Let's Encrypt certificate; HTTP and direct-IP UI traffic redirect to HTTPS, with direct-IP `/health` retained. Ports 3000, 5432, 6379, 8000, and 8100 have no host listeners.
- Host PAM bridge active; only the deployment-configured operator is accepted. Invalid authentication fails with 401, valid Ubuntu PAM login was manually verified earlier on 2026-08-14. Passwords are not stored or application-logged.
- Sessions are Redis-backed with HttpOnly, SameSite=Strict cookies, 30-minute idle expiry, 8-hour absolute expiry, logout, CSRF tokens on mutations, application and Nginx login throttles.
- Backend pytest genuinely ran via `python -m pytest`: 7 passed, 1 read-only cache warning. The new coverage verifies safe Robinhood configuration retrieval, CSRF-protected persistence, rejection of secret-like extra fields, and rejection of arbitrary endpoints.
- Broker gateway pytest: 11 passed with 1 read-only cache warning; policy tests cover allowed reads and blocked order, cancellation, review, mutation, and unknown tools; storage tests prove token plaintext is absent from ciphertext.
- Frontend was upgraded to Next.js 16.3.1 and React 19.2.4. `npm audit --audit-level=high` reports 0 vulnerabilities. ESLint: 0 errors, 1 navigation-style warning. Vitest: 1 file/1 test passed. The production frontend image built successfully. Playwright against `https://aegis-alpha.pacificao.com`: the authenticated Robinhood form plus login/hydration/assets/unauthorized boundaries for `/roadmap`, `/security`, and `/system` all passed (5/5).
- UFW, Nginx headers/rate limits/request size, internal Compose networking, secret tracking scan, PostgreSQL/Redis connectivity, unauthorized 401, and trading-disabled health response were inspected.
- `scripts/backup.sh` and `scripts/restore.md` provide dump, checksum, restore-test, repository, secret, rebuild, rollback, and recovery procedures. Backups are Git-ignored.
- The Aegis-owned broker gateway now implements official MCP OAuth/PKCE initiation, encrypted atomic token storage, service authentication, browser callback handling, read-only account validation, exact read-tool allowlisting, and unconditional rejection of order/cancellation/review/mutation/unknown tools. The System page owns connect/status/disconnect. Development has `BROKER_AUTHORIZATION_ENABLED=false`; both connect and callback return 403 and the browser button is disabled. No authorization was initiated because Docker administration is root-equivalent; current status remains `NOT_CONFIGURED`.

## Known limitations / next exact work

- Robinhood's hosted authorization page rejected the public HTTPS callback before redirecting to Aegis. A protected loopback relay is now implemented: the official OAuth flow redirects to `http://127.0.0.1:8765/callback`, the operator copies that complete URL into Aegis, and the browser submits it directly to the isolated gateway with a one-time nonce. The authorization code is never sent through the Aegis backend, persisted in PostgreSQL, or written to access logs. The gateway validates the exact scheme, address, port, path, state, origin, and nonce before exchanging the code and performing read-only validation.
- Relay verification: broker gateway pytest 29/29 passed; backend pytest 7/7 passed; frontend production build passed; Vitest 1/1 passed; ESLint passed with 0 errors and the existing 1 navigation-style warning.
- On 2026-08-17 Nathan completed Robinhood's desktop-only OAuth/onboarding flow through Aegis. The isolated gateway successfully exchanged the authorization code, established the official Trading MCP session, verified the required read-only tools, and completed read-only account synchronization. Aegis displayed `CONNECTED` and `READ_ONLY`; the roadmap milestone was persisted as COMPLETE with an audit activity. Trading remained `DISABLED` throughout.

Phase 1 privileged cleanup and the `v0.1.0-core` tag are complete.

## Verified 2026-08-17 — Phase 2

- Authentication UX exposes the protected cookie policy plus 30-minute idle and 8-hour absolute session limits; all new APIs require authentication and all mutations require CSRF.
- Dashboard and navigation accurately show Phase 2, Robinhood state, overall progress, and trading disabled. Responsive navigation supports narrow/mobile screens.
- Portfolio displays only verified broker connection/mode and explicitly refuses to fabricate holdings before Phase 9 synchronization views.
- Strategy Library persists bounded research scenarios. Dividend Farm is seeded with 24 adjustable parameters; custom research scenarios can be created and paused. API and database constraints reject paper/live states.
- Settings persist display density/page size while sensitive-action confirmation is permanently required. Activity displays up to 100 audited authenticated mutations.
- Migration `0005_phase2_console` applied after a PostgreSQL backup; Phase 1's 69 completed tasks persisted.
- Backend pytest: 9/9 passed. Frontend build and TypeScript: passed. Vitest: 1/1. ESLint: 0 errors, 1 existing navigation warning. Browser authentication/hydration/assets/console checks: 8/8 passed. All six tested console pages returned 200; four unauthenticated Phase 2 APIs returned 401.
- Dividend Farm is documented as an empirical hypothesis. Market data, backtesting, real-time paper simulation, deterministic risk, execution, controlled live, and autonomy remain later gated phases.


## Post-Phase 2 navigation refinement

- The operator console now uses grouped navigation: Portfolio, Scenarios, Performance, Suggested Adjustments, and System. Administrative pages are contained under System, reducing persistent menu clutter on desktop and mobile.
- Performance and Suggested Adjustments have dedicated, authentication-protected views. They disclose data readiness and required decision notes without fabricating analytics or recommendations.
- Suggested adjustments remain reviewable proposals only; they cannot automatically change a scenario or bypass strategy, deterministic risk, or execution controls. Trading remains disabled.
- Dashboard operational telemetry was moved out of the decision surface and remains available under System. Dashboard is now a visualization-ready decision cockpit for portfolio value, return, available capital, drawdown, performance versus benchmark, risk/exposure, scenario contribution, opportunity intelligence, and an operator decision queue.
- Time horizon, account, scenario, and benchmark filters are established. Unavailable data-dependent filters are visibly disabled and all metrics use explicit empty states until Phase 3 supplies validated data; nothing is estimated or fabricated.


## Startup continuity and operator communications

- Docker and the PAM authentication bridge are enabled and active at boot. Every Aegis Compose service has `restart: unless-stopped`; the isolated broker bootstrap enables Docker, Nginx, and certificate renewal and gives its gateway the same restart policy. Both public HTTPS health checks passed with trading disabled. A destructive reboot was not required to verify the configuration.
- Canonical roadmap tasks and `docs/operator-briefings.md` now preserve pre-market decision briefings, post-market highlights, attention alerts, public-source/citation rules, portfolio inputs, exchange-calendar scheduling, durable delivery, redaction, deduplication, retry, audit, and notification preferences. Delivery is WAITING FOR CREDENTIALS: an authorized transactional mail provider, verified sender identity/domain, and runtime secret are not configured, so no email was sent.
- SMTP DNS, STARTTLS, certificate validation, authentication, and submission passed. Nathan approved test drafts for pre-market, post-market, and attention-alert email types.
- Reboot-persistent cron scheduling uses headquarters time `America/Los_Angeles`: pre-market at 05:30 weekdays (one hour before the 06:30 Pacific open), post-market at 13:30 weekdays (30 minutes after the 13:00 Pacific close), and deduplicated health-transition monitoring every five minutes. Database/audit timestamps remain UTC. Alert state is persisted outside Git; healthy polling sends no email, while failures and recoveries send notification-only messages. Exchange-holiday calendar gating remains a Phase 3 task.

## Verified 2026-08-18 — Phase 3 data foundation

- Migration `0006_phase3_data` adds normalized providers, instruments, records, ingestion runs, and quality issues with indexed provenance and idempotent checksums.
- Official adapters cover Alpha Vantage OHLCV/quotes/fundamentals/dividends/news, FRED economic observations, SEC EDGAR company facts, and NYSE session awareness. Reverse-engineered endpoints are prohibited.
- Live credential-free validation passed: FRED returned 942 UNRATE observations through its official CSV endpoint; SEC EDGAR returned Apple company facts for CIK 0000320193.
- Deterministic validation covers timestamp sanity, OHLC consistency, nonnegative volume, empty payloads, quote freshness, quality severity, and canonical checksums. Redis readiness caching is bounded and invalidated after ingestion.
- Authenticated Data Sources UI and APIs expose readiness, bounded records, calendar sessions, audited ingestion, quality counts, freshness, and source URLs. Provider keys never enter the browser.
- Backend pytest: 15/15 passed. Frontend production build/TypeScript passed. ESLint: 0 errors, 1 existing navigation warning. Vitest: 1/1 passed. Trading remains disabled.
- Alpha Vantage production validation passed with the protected runtime key: 100 SPY daily OHLCV records, one current quote, 111 dividend events, and 50 news records were accepted with zero rejects. The standard daily endpoint is used so the validated implementation does not require the premium adjusted-history endpoint.

## Robinhood data expansion

- Official Robinhood Trading MCP public-market reads are implemented behind a second, narrower gateway allowlist; account-private reads remain reserved for portfolio synchronization and every mutation/order capability remains blocked.
- Authenticated Data Sources ingestion supports Robinhood market tools with bounded JSON arguments, credential rejection, audit history, provenance, and normalized broker-data categories. The isolated gateway now exposes authenticated safe-schema discovery; only advertised tools intersecting the public-data allowlist are returned.
- Provider responsibilities and the complete safe-use roadmap are recorded in `docs/robinhood-capabilities.md`. Alpha Vantage remains required for reproducible deep adjusted backfill and independent research validation.
- Production validation discovered 14 safe schemas. Thirteen public tools were exercised successfully: equity quotes, fundamentals, historicals, technical indicators, financials, earnings results/calendar, price book, indexes/quotes, option chains/instruments/quotes/historicals. Account-number-dependent tradability was intentionally not called. Nine representative datasets were persisted with `COMPLETE`, one accepted record, and zero rejects each.
- Robinhood did not advertise crypto tools during validation, so crypto remains unavailable rather than assumed. Trading remained `DISABLED` in every gateway response; no review, order, cancellation, watchlist, scanner mutation, or other state-changing tool was exposed or called.

## Verified 2026-08-18 — Phase 4 strategy engine

- Added schema-validated deterministic specifications covering universe, indicators, entry/exit rules, position sizing, NYSE schedules, filters, parameters, and immutable checksummed versions.
- Research evaluation deterministically emits ENTRY, EXIT, HOLD, or EXCLUDE with reason codes and exact input facts. Decisions persist for audit and are unconditionally `risk_authorized=false`, `executable=false`, and `trading=DISABLED`.
- Strategy Engine UI supports adjustable scenario parameters, universe configuration, immutable version creation, and operator-supplied decision previews. It explicitly does not backtest, simulate, authorize risk, or execute.
- Migration `0007_phase4_strategy_engine` adds strategy versions and decision history. ADR 0005 records the immutable boundary.
- Backend pytest: 19/19 passed. Frontend ESLint: 0 errors, 1 existing navigation warning. Vitest: 1/1 passed. Production build and TypeScript passed.
- Production acceptance: Alembic `0007_phase4_strategy_engine (head)`; all six Compose services healthy; HTTPS `/health` returned version `0.3.0-strategy` with trading disabled; `/strategies` returned 200 with security headers. A persisted Dividend Farm v1 evaluation returned ENTRY at the 1% strategy proposal bound while `risk_authorized=false`, `executable=false`, and `trading=DISABLED`.
- PostgreSQL roadmap state was updated only after acceptance: Phase 4 is 10/10 COMPLETE with verified notes and a development activity record.

## Post-Phase 4 UI truth audit

- Removed stale Phase 1–3 placeholders across the global shell, Dashboard, Performance, Roadmap, Portfolio, and Security views.
- Dashboard and Performance now read live Phase 3 readiness counts while clearly reserving backtest metrics for Phase 5, paper results for Phase 8, and verified broker portfolio metrics for Phase 9.
- Roadmap delivery/next-phase summaries derive from PostgreSQL state instead of hard-coded phase numbers. The UI shows Phase 4 complete, Phase 5 next, and trading disabled without fabricating performance.
- Frontend ESLint passed with 0 errors and one existing navigation warning; Vitest 1/1 and the production build/TypeScript passed.

## Phase 5 — COMPLETE (verified 2026-08-19)

- Aegis Lab implements day-by-day portfolio backtesting with occupied capital, bounded allocation, transaction costs, spread/slippage, dividends, splits, same-window benchmarks, walk-forward, seeded Monte Carlo, 36-variant parameter sensitivity, drawdown, Sharpe, Sortino, exposure, capital utilization, and trade inspection.
- Immutable Phase 4 strategy versions and checksummed Phase 3 records define reproducible run identity. Benchmark-only symbols cannot become strategy positions. All artifacts remain non-executable, risk-unauthorized, and trading-disabled.
- Authenticated Lab APIs and the Performance → Aegis Lab UI expose readiness, configuration, results, provenance, robustness, and trades. Performance and Dashboard show the latest Lab evidence separately from unavailable real portfolio performance.
- Production acceptance passed on migration `0008_phase5_aegis_lab` and version `0.4.0-lab`: all six containers were healthy, HTTPS `/lab` returned 200, unauthenticated Lab API access returned 401, and persisted run #1 used 100 checksummed SPY bars plus one corporate action to produce one inspectable trade and 36 sensitivity variants. The artifact reports `risk_authorized=false`, `executable=false`, and `trading=DISABLED`.
- Verification results: backend pytest 24/24 passed; frontend Vitest 1/1 passed; production build passed; Compose validation passed; GitHub backend/frontend/gateway/Compose/secret checks passed through feature, develop, and main promotion. Production acceptance found and corrected a missing browser payload default before closure.

## Future governed consensus milestone

- Phase 7 now includes independent proposal verification. Aegis supplies a checksummed proposal and evidence snapshot; a credential-isolated verifier returns an independently auditable assessment. Agreement can only advance a preauthorized low-risk proposal to the deterministic RiskEngine. Disagreement, missing evidence, stale evidence, or verifier failure requires human review or fails closed; both rejection results in rejection. High-impact actions always require human approval, and no AI component may authorize risk or execute.


## Phase 6 — COMPLETE (verified 2026-08-20)

- Deterministic Aegis Risk evaluates immutable policy limits for position, portfolio, sector, correlation, loss, drawdown, volatility, buying power, order sanity, duplicates, freshness, circuit breaker, and kill switch.
- Authenticated APIs and the Risk UI expose policy, controls, proposal evaluation, and the immutable assessment ledger. Every authorization remains non-executable and trading-disabled.
- Protected-main CI passed backend, frontend, gateway, Compose, and secret checks. Production migration `0009_phase6_aegis_risk` applied and all six containers reported healthy.
- Live acceptance verified an authorized-but-non-executable proposal, checksum idempotency, changed-content duplicate rejection, stale-data rejection, kill-switch rejection and safe reset, HTTPS `/risk` 200, unauthenticated API 401, and the absence of order/execution routes. Trading remained `DISABLED`.
- PostgreSQL roadmap state records all 14 Phase 6 tasks COMPLETE with a development activity audit entry. Phase 7 is next.

## Phase 7 — COMPLETE (verified 2026-08-19)

- Provider-neutral, strictly schema-bound intelligence artifacts cover strategy creation/critique, market regime, news, fundamentals, parameter research, post-trade review, anomaly detection, pre-market briefings, post-market digests, and attention alerts.
- Citations, timestamps, freshness, confidence, countercases, immutable checksums, independent reviews, and deterministic consensus are persisted and audited.
- Only unanimous independent agreement can make low-impact research/hold/adjust artifacts eligible for separate RiskEngine review. High-impact recommendations and disagreement require a human. Intelligence never authorizes risk or executes; trading remains disabled.
- Protected-main CI passed all backend, frontend, gateway, Compose, and secret checks. Production migration `0010_phase7_intelligence` applied with all six containers healthy.
- Live acceptance verified cited artifact persistence, two-reviewer low-impact consensus, stale-evidence failure, high-impact human escalation, HTTPS UI 200, unauthenticated API 401, no order/execution routes, and `risk_authorized=false`, `executable=false`, `trading=DISABLED`.
- PostgreSQL records all 14 Phase 7 tasks COMPLETE. Phase 8 is next.

## Phase 8 — COMPLETE (verified 2026-08-19)

- Independent paper accounts, single-use risk-authorized orders, fresh normalized quote validation, deterministic fills, positions, realized/unrealized P&L, equity, return, audit history, authenticated APIs, and Simulator UI are implemented.
- Five-basis-point adverse slippage and $1 commission make friction explicit. Stale data, price deviation, insufficient cash/positions, duplicate authorization use, and missing RiskEngine authorization fail closed.
- The paper module has no broker/gateway/Robinhood dependency. All outputs identify PAPER, broker-called false, live execution unavailable, and trading disabled.
- Protected-main CI passed backend, frontend, gateway, Compose, and secret checks. Production migration `0011_phase8_simulator` applied with all six containers healthy.
- Live acceptance ingested a fresh official Alpha Vantage SPY quote, obtained deterministic RiskEngine authorization, persisted a paper fill and marked position with explicit friction, rejected duplicate use, confirmed no broker call or non-paper order route, and kept trading disabled.
- PostgreSQL records all 6 Phase 8 tasks COMPLETE. Phase 9 is next.

## Phase 9 — COMPLETE (verified 2026-08-19)

- Implemented a provider-neutral read-only snapshot adapter and a single bounded isolated-gateway account snapshot route. Exact Robinhood account, portfolio, P&L, position, tax-lot, and historical order reads are allowed; all mutation/unknown tools remain fail-closed.
- Private identifiers are one-way hashed before leaving the gateway. Aegis strictly validates read-only/trading-disabled invariants, normalizes balances/holdings/orders/fills, detects duplicate references and invalid fill quantities, retries only idempotent reads, persists immutable checksummed snapshots/runs, and writes sanitized audit activity.
- Portfolio, Dashboard, and Performance now project verified snapshot evidence and freshness without fabricating return, drawdown, exposure, or attribution. Synchronization requires authentication and CSRF. A persisted DISCONNECTED OAuth session may be revalidated only by this bounded read; no order/review/cancel route or adapter method exists.
- Migration `0012_phase9_gateway` is live. The operator deployed the isolated gateway; five accounts completed core portfolio, equity/option position, equity/option order, and trade-history reads. Ten optional tax-lot/realized-P&L reads failed safely because their schemas require additional parameters, so the immutable snapshot explicitly reports PARTIAL/ATTENTION while core order references and fill quantities reconcile. No original account number is stored; all five account-number fields are keyed-HMAC pseudonyms. Backend 41/41, gateway 34/34, frontend build, lint, Vitest, protected CI, health, UI, authentication, persistence, listener, log-redaction, and no-live-order-surface checks passed. PostgreSQL records Phase 9 14/14 COMPLETE. Trading remains disabled.


## Phase 10 preparation — single brokerage account scope (2026-08-19)

- Added Phase 10 tasks for strict single-account scope, parameterized tax-lot/realized-P&L reads, and port-21 remediation before any controlled-live authorization.
- Exactly one pseudonymous brokerage account matched the dedicated approximately-$5 Agentic MCP account. Aegis now requires that selected keyed-HMAC reference for every synchronization; the gateway filters other accounts before account-specific reads, and the backend rejects multiple or mismatched accounts. No Robinhood account is modified or deleted.
- Migration `0013_single_broker_account` records only the pseudonymous selection. The UI exposes only `SINGLE_ACCOUNT` or `NOT_SELECTED`, never the reference or account number. The prior multi-account Aegis snapshot was purged after the unique selection, and a clean selected-account resynchronization persisted exactly one matching account. Trading remains `DISABLED`.
- Isolated-gateway deployment acceptance passed: status remained `READ_ONLY`/`DISABLED`; the gateway returned one account; the backend persisted one matching account and rejected scope drift by invariant. The single-account Phase 10 roadmap task is COMPLETE. Snapshot status remains `ATTENTION` solely for the separate planned parameterized tax-lot/realized-P&L reads.


## Decision UI and storage maintenance (2026-08-19)

- Dashboard now prioritizes operator posture, verified capital, governed decision queue, deterministic risk state, evidence-gated direction, and attention counts. Decorative filters and mixed-in Lab research metrics were removed; system/connection detail remains on targeted pages.
- Portfolio now renders its existing verified summary: portfolio value, cash, buying power, and holdings. It continues to expose no account number or execution action. The global header now accurately identifies Phase 10 as active.
- Deleted 4.738 GB of reproducible unused Docker build cache and 2.793 GB of images unused by every container. Root filesystem usage fell from 97% (790 MB free) to 37% (15 GB free). Containers, all six active service images, volumes, PostgreSQL/Redis data, backups, credentials, and broker state were preserved.

- Deployment acceptance: all six containers healthy; HTTPS login returned 200; protected Portfolio returned 401 unauthenticated; backend health reported trading `DISABLED`. Only 22, 80, 443 and the pre-existing Phase 10-tracked port 21 listen publicly; internal application and data ports remain private.


## Phase 10 controlled-trial readiness (2026-08-19)

- Added an immutable controlled trade-intent and human-approval ledger. An intent requires an AUTHORIZED deterministic RiskEngine assessment linked to an immutable strategy decision, freezes symbol, side, quantity, LIMIT price, checksums, account scope and a five-minute expiry, and rejects reuse or drift. Approval requires the exact checksum and explicit phrase. Both creation and approval report broker-called false, executable false and trading DISABLED.
- Added the Production Trial UI with readiness gates, strategy selection, conservative risk-profile metrics, non-executable intent review and typed approval. Investment BI remains investment-only; operational state stays under System.
- Added research templates for Trend Momentum, Mean Reversion, Quality Value, Volatility Breakout and paper-only Pairs Reversion. Strategy-specific indicators, entry/exit rules and allocation limits are versioned; no template is presumed profitable.
- Added immutable portfolio-history retrieval and a scheduled read-only snapshot job for defensible future charts. Historical depth is evidence-gated and is never fabricated.
- Migration 0014 creates the approval ledger. Backend 46/46, frontend Vitest 1/1 and production frontend build/TypeScript passed before deployment. Live order submission remains unavailable. Port 21 remediation, isolated execution-adapter deployment, operator authorization, parameterized tax-lot/P&L validation, fill reconciliation and real-capital acceptance remain BLOCKED or IN PROGRESS; therefore Phase 10 is not complete and Aegis is not authorized to trade.


## Verified port-21 remediation (2026-08-19)

- Nathan explicitly stopped and disabled vsftpd. Verification found the service disabled and inactive and no TCP/21 listener on IPv4 or IPv6. Public listeners are now limited to SSH 22 and Nginx 80/443; PostgreSQL, Redis, backend, frontend and broker gateway remain private. Phase 10 readiness derives this gate from the verified PostgreSQL roadmap task rather than claiming it from an unverified container assumption.


## Phase 10 parameterized account-read hardening (2026-08-19)

- The isolated gateway now derives only semantically known, bounded required arguments from official MCP schemas: a trailing 366-day date window for realized P&L and one read per symbol already present in the selected accounts equity-position dataset for tax lots. Unknown required arguments fail closed. Responses remain size-bounded, sanitized, read-only and trading-disabled. Gateway tests: 36/36 passed. Isolated production deployment and a clean selected-account resynchronization are still required before marking the roadmap task COMPLETE.
