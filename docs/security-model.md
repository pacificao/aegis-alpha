# Security Model

- Only the deployment-configured Linux operator is authorized. The username is stored outside Git in root/deployment configuration. Credentials are validated by a narrow root-owned host PAM bridge; the web application never receives password hashes or `/etc/shadow` access.
- Sessions use an opaque random ID, server-side Redis state, 30-minute idle and 8-hour absolute expiration, HttpOnly cookies, SameSite=Strict, and Secure cookies outside local development.
- Login is rate-limited by source and username. State-changing API calls require a session-bound CSRF token.
- Nginx applies CSP, frame denial, MIME sniffing protection, referrer restrictions, and request limits.
- Database, Redis, backend, and frontend are internal-only. Only Nginx publishes HTTP/HTTPS.
- Secrets come from deployment secret storage/environment and never Git. Production secrets are unavailable in research or agent environments.
- Audit activity records authenticated mutations without secrets.
- The Robinhood console initiates official browser OAuth but never accepts credentials. An isolated gateway encrypts authorization material, exposes no raw MCP responses, and permits only an exact read-tool allowlist; all mutations and unknown tools fail closed.
- Trading is disabled by configuration and absence of execution endpoints.
- Live readiness additionally fails closed unless controlled-live order/fill/reconciliation acceptance, every Phase 11 autonomy control, and the required Phase 12 evolution-safety controls are verified COMPLETE in PostgreSQL. Operator authorization cannot override an incomplete engineering gate. Optional providers and asset expansion do not block initial equity launch, but no unvalidated strategy or asset receives authority.

Staging uses separate credentials, database, Redis, hostname, and restricted synthetic/paper data. Production uses an encrypted managed secret store or root-readable deployment-time secret files, never image build arguments, plus DigitalOcean secret injection, encrypted backups, least-privilege service identities, TLS, and a separate execution security domain. Brokerage credentials will live only in that domain.

## Market-data security

API keys are runtime secrets and are never accepted by frontend forms, returned by APIs, written to audit details, or committed. Provider/dataset names are allowlisted; symbols, series IDs, CIKs, ranges, and result sizes are bounded. Source URLs exclude credentials. Provider failures are classified without logging response secrets.

External content is untrusted research input. It is normalized and quality-checked but cannot authorize risk or execution. News text and provider metadata must never be interpreted as commands.

- Risk authorization uses strict bounded schemas, immutable policy checksums, frozen request snapshots, duplicate detection, stale-data rejection, CSRF-protected control state, and complete audit evidence. It cannot access broker secrets or execute.

## Intelligence isolation

Intelligence inputs are untrusted proposals. Strict schemas reject extra fields, evidence requires HTTPS citations and timezone-aware freshness, and reviews bind to the immutable artifact checksum. Model credentials are not accepted by the API or UI. Prompt/model output cannot mutate strategies, controls, broker state, or execution. High-impact output always requires human review; trading remains disabled.

## Paper-domain isolation

Paper fills require authentication, CSRF, a single-use authorized RiskAssessment, matching fresh quote provenance, and bounded price movement. The service has no broker/gateway import. Paper responses and audit records permanently identify simulation and trading disabled.

## Phase 9 private portfolio reads

Account synchronization requires authenticated Aegis access and CSRF for initiation. The backend-to-gateway request uses TLS plus a protected shared secret and originates over the VPC. The gateway keyed-HMAC pseudonymizes account/order/position identifiers and recursively removes credential-like fields before data crosses domains. Aegis accepts only an exact dataset set with `READ_ONLY` and `trading=DISABLED` invariants, retries only reads, and fails closed without persisting unsafe responses. Logs and audit events contain status/counts, never raw payloads, tokens, full account numbers, or holdings. Phase 10 adds a single-account boundary: only the keyed-HMAC reference selected from the approximately-$5 dedicated Agentic account is retained; the gateway skips all other accounts before private reads, and Aegis rejects multi-account or mismatched responses. This selection does not modify or delete any Robinhood account.
