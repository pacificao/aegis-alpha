# Development Status

- Current phase: Phase 1 — Aegis Core / Foundation
- Current version: `0.1.0-core-dev`
- Phase 1 completion: 59/69 complete (86%); 5 in progress; 5 blocked
- Completed: repository structure and agent contract; architecture/security/data/environment/deployment/network/Robinhood documentation; FastAPI health/status/roadmap/system/broker APIs; SQLAlchemy models and Alembic migration; PostgreSQL/Redis Compose services; persistent roadmap seeding; structured logging/configuration; dark Next.js dashboard/roadmap/security/system UI; Nginx security boundary; backend/API tests; frontend test definition; CI workflow; firewall planning script; trading hard-disable
- In progress: reproducible container build, frontend runtime verification, authenticated browser-to-database validation, Git workflow promotion
- Blocked: UFW inspection/change still requires Nathan
- Test results: Python source compilation and backend/API suite previously passed; roadmap invariant check passed (12 phases, 69 Phase 1 tasks, 175 total). Docker Compose now runs PostgreSQL, Redis, FastAPI, Next.js, and unprivileged Nginx. Browser smoke coverage now checks hydration, login rendering, static assets, protected API behavior, console errors, and protected-route redirects.
- Last major change: restored browser rendering through Nginx while preserving the fail-closed host authentication boundary
- Next recommended task: harden the production Next.js CSP with per-response nonces and complete the remaining Phase 1 operational checks

## 2026-08-14 — Browser rendering recovery

- Corrected the frontend container runtime binding to `0.0.0.0:3000` so Nginx can reach the standalone Next.js server.
- Corrected unprivileged/read-only Nginx runtime paths by placing its PID and temporary paths under `/tmp` and listening on container port 8080.
- Diagnosed the black page as a CSP/Next.js 15 incompatibility: `script-src 'self'` blocked inline `self.__next_f` bootstrap data, preventing hydration and the client-side 401 redirect.
- Temporarily changed only `script-src` to `'self' 'unsafe-inline'`. No `unsafe-eval` or external script origin was added; all other restrictive directives and security headers remain. Production nonce hardening is tracked in `docs/decisions/csp.md`.
- Added a shared client authentication gate because API-driven pages redirected on 401 but the static Security route did not. Every protected frontend route now verifies `/api/auth/me` and fails closed to `/login`; no credential handling or authentication bypass was introduced.
- Added a Playwright smoke suite covering visible login UI, JavaScript execution/redirect, JS/CSS asset success, protected API 401, protected route gating, failed requests, and console errors.
- Final verification: production frontend image built successfully; Playwright/Chromium smoke suite 4/4 passed; frontend Vitest suite 1/1 passed; backend pytest suite 5/5 passed; unauthenticated `/api/status` remained HTTP 401; all five Compose services were up and PostgreSQL, Redis, backend, and frontend were healthy.
- Implemented the previously missing host PAM bridge after live login returned HTTP 503 with `FileNotFoundError` for `/run/aegis-auth/pam.sock`. The bridge uses the host PAM stack, accepts only `nathan`, verifies Unix peer credentials, rate-limits requests, stores/logs no password, and is packaged as a hardened root-owned systemd service. Installation was performed explicitly by Nathan with sudo.
- Nathan installed the reviewed bridge on 2026-08-14. The root-owned systemd service was active, the backend could access the mode-0660 Unix socket, a known-invalid password returned HTTP 401 rather than 503, and Nathan manually confirmed that valid Ubuntu PAM authentication rendered the dashboard.
