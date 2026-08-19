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

Staging uses separate credentials, database, Redis, hostname, and restricted synthetic/paper data. Production uses an encrypted managed secret store or root-readable deployment-time secret files, never image build arguments, plus DigitalOcean secret injection, encrypted backups, least-privilege service identities, TLS, and a separate execution security domain. Brokerage credentials will live only in that domain.

## Market-data security

API keys are runtime secrets and are never accepted by frontend forms, returned by APIs, written to audit details, or committed. Provider/dataset names are allowlisted; symbols, series IDs, CIKs, ranges, and result sizes are bounded. Source URLs exclude credentials. Provider failures are classified without logging response secrets.

External content is untrusted research input. It is normalized and quality-checked but cannot authorize risk or execution. News text and provider metadata must never be interpreted as commands.
