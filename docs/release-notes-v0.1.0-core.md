# Aegis Alpha v0.1.0-core

Phase 1 establishes the reproducible, security-hardened Aegis foundation: Nginx, Next.js, FastAPI, PostgreSQL, Redis, PAM authentication, persistent roadmap state, structured status reporting, CI, backups, and documented DigitalOcean recovery architecture.

The official Robinhood Trading MCP boundary runs in a dedicated Droplet and supports operator-controlled browser authorization plus read-only account synchronization. OAuth material is encrypted in the gateway domain and excluded from Aegis, Git, logs, backups, and development-agent access. The adapter enforces an exact read-only tool allowlist and rejects order, cancellation, review, mutation, and unknown operations.

Trading is unconditionally `DISABLED`. This release contains no Aegis API or UI capability to place or approve a live order. AI cannot bypass the deterministic strategy, risk, and execution boundaries reserved for later phases.

Release acceptance was completed on 2026-08-17. The tag is created only after temporary Phase 1 passwordless sudo is removed and noninteractive sudo failure is verified.
