# Development Status

- Current phase: Phase 1 — Aegis Core / Foundation
- Current version: `0.1.0-core-dev`
- Verified Phase 1 roadmap state: 67/69 COMPLETE (97% rounded); 1 BLOCKED; 1 WAITING_FOR_CREDENTIALS
- BLOCKED: task 48, GitHub branch protection. The private repository and CI exist, but GitHub returned HTTP 403 because protected branches for this private repository require a plan upgrade. The repository must not be made public to bypass this.
- WAITING_FOR_CREDENTIALS: task 61, official Robinhood Trading MCP OAuth/onboarding and read-only connectivity verification.
- Trading: DISABLED by configuration validation and absence of any order endpoint/method.

## Verified 2026-08-14

- Private GitHub repository `pacificao/aegis-alpha`, authenticated `gh`, local `main`, `develop`, and `feature/phase-1-core` workflow. Promotion/push and CI verification remain part of the release sequence.
- Compose stack: PostgreSQL, Redis, FastAPI, Next.js, and Nginx healthy. Alembic is at `0003_expand_task_status`.
- Public listeners: SSH 22 and Nginx HTTP 80 only. UFW is active, default-deny inbound, allowing 22/80/443. Ports 3000, 5432, 6379, and 8000 have no host listeners.
- Host PAM bridge active; only `nathan` is accepted. Invalid authentication fails with 401, valid Ubuntu PAM login was manually verified by Nathan earlier on 2026-08-14. Passwords are not stored or application-logged.
- Sessions are Redis-backed with HttpOnly, SameSite=Strict cookies, 30-minute idle expiry, 8-hour absolute expiry, logout, CSRF tokens on mutations, application and Nginx login throttles.
- Backend pytest genuinely ran after fixing an entrypoint defect that previously caused `docker compose run backend pytest` to start Uvicorn instead of pytest: 5 passed, 1 read-only cache warning.
- Frontend ESLint: 0 errors, 1 configuration-style warning. Vitest: 1 file/1 test passed. Production frontend build passed. Browser smoke was started against the rebuilt app; the runner produced only partial progress before this execution environment ended the process, so the prior 4/4 result is not being reused as a new pass claim.
- UFW, Nginx headers/rate limits/request size, internal Compose networking, secret tracking scan, PostgreSQL/Redis connectivity, unauthorized 401, and trading-disabled health response were inspected.
- `scripts/backup.sh` and `scripts/restore.md` provide dump, checksum, restore-test, repository, secret, rebuild, rollback, and recovery procedures. Backups are Git-ignored.
- Official Robinhood documentation now identifies `https://agent.robinhood.com/mcp/trading` and desktop OAuth/onboarding for an Agentic account. Aegis reports `NOT_CONFIGURED`; the adapter exposes status only and contains no order capability.

## Known limitations / next exact work

1. Complete Robinhood Trading MCP desktop OAuth/onboarding, then verify read-only account synchronization without exposing credentials or enabling orders.
2. Push the reviewed feature/develop/main sequence and verify GitHub Actions. Branch protection remains blocked until a GitHub plan supporting protected private branches is available.
3. Rerun the complete Playwright suite in an execution window that allows all four tests to finish.
4. Only after acceptance passes: tag `v0.1.0-core`, push it, finish privileged cleanup, and verify `sudo -n true` fails.
