# Development Status

- Current phase: Phase 1 — Aegis Core / Foundation
- Current version: `0.1.0-core-dev`
- Verified Phase 1 roadmap state: 67/69 COMPLETE (97% rounded); 1 BLOCKED; 1 WAITING_FOR_CREDENTIALS
- BLOCKED: task 48, GitHub branch protection. The private repository and CI exist, but GitHub returned HTTP 403 because protected branches for this private repository require a plan upgrade. The repository must not be made public to bypass this.
- WAITING_FOR_CREDENTIALS: task 61, official Robinhood Trading MCP OAuth/onboarding and read-only connectivity verification.
- Trading: DISABLED by configuration validation and absence of any order endpoint/method.

## Verified 2026-08-14 through 2026-08-15

- Private GitHub repository `pacificao/aegis-alpha`, authenticated `gh`, local `main`, `develop`, and `feature/phase-1-core` workflow. Feature-to-develop PR #1 passed all three GitHub Actions jobs and was merged.
- Host Docker Buildx plugin installed and verified: `docker-buildx 0.30.1-0ubuntu1~24.04.1`; `docker buildx version` reports 0.30.1.
- Compose stack: PostgreSQL, Redis, FastAPI, Next.js, and Nginx healthy. Alembic is at `0004_broker_connection_config` (head).
- Public listeners: SSH 22 and Nginx HTTP 80/HTTPS 443. UFW is active, default-deny inbound, allowing 22/80/443. `aegis-alpha.pacificao.com` uses a valid Let's Encrypt certificate; HTTP and direct-IP UI traffic redirect to HTTPS, with direct-IP `/health` retained. Ports 3000, 5432, 6379, and 8000 have no host listeners.
- Host PAM bridge active; only `nathan` is accepted. Invalid authentication fails with 401, valid Ubuntu PAM login was manually verified by Nathan earlier on 2026-08-14. Passwords are not stored or application-logged.
- Sessions are Redis-backed with HttpOnly, SameSite=Strict cookies, 30-minute idle expiry, 8-hour absolute expiry, logout, CSRF tokens on mutations, application and Nginx login throttles.
- Backend pytest genuinely ran via `python -m pytest`: 6 passed, 1 read-only cache warning. The new coverage verifies safe Robinhood configuration retrieval, CSRF-protected persistence, rejection of secret-like extra fields, and rejection of arbitrary endpoints.
- Frontend was upgraded to Next.js 16.3.1 and React 19.2.4. `npm audit --audit-level=high` reports 0 vulnerabilities. ESLint: 0 errors, 1 navigation-style warning. Vitest: 1 file/1 test passed. The production frontend image built successfully. Playwright against `https://aegis-alpha.pacificao.com`: the authenticated Robinhood form plus login/hydration/assets/unauthorized boundaries for `/roadmap`, `/security`, and `/system` all passed (5/5).
- UFW, Nginx headers/rate limits/request size, internal Compose networking, secret tracking scan, PostgreSQL/Redis connectivity, unauthorized 401, and trading-disabled health response were inspected.
- `scripts/backup.sh` and `scripts/restore.md` provide dump, checksum, restore-test, repository, secret, rebuild, rollback, and recovery procedures. Backups are Git-ignored.
- Official Robinhood documentation identifies `https://agent.robinhood.com/mcp/trading` and desktop OAuth/onboarding for an Agentic account. The authenticated System page now persists only a user-entered display name and that exact endpoint, records `READ_ONLY`, rejects extra/secret fields and arbitrary URLs, and survived full container recreation. Aegis still correctly reports `NOT_CONFIGURED`; the adapter exposes status only and contains no order capability.

## Known limitations / next exact work

1. Complete Robinhood Trading MCP desktop OAuth/onboarding, then verify read-only account synchronization without exposing credentials or enabling orders.
2. Promote reviewed develop to main through a release PR; GitHub Actions passed on PR #1. Branch protection remains blocked until a GitHub plan supporting protected private branches is available.
3. Only after acceptance passes: tag `v0.1.0-core`, push it, finish privileged cleanup, and verify `sudo -n true` fails.
