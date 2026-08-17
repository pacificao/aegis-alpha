# Development Status

- Current phase: Phase 2 — Aegis Console
- Current version: `0.2.0-console`
- Verified Phase 1–2 roadmap state: Phase 1 69/69 COMPLETE; Phase 2 8/8 COMPLETE; 0 BLOCKED; 0 WAITING_FOR_CREDENTIALS
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

Next: Phase 3 — Aegis Data. Trading remains disabled.
