# Security Model

- Only Linux user `nathan` is authorized. Credentials are validated by a narrow root-owned host PAM bridge; the web application never receives password hashes or `/etc/shadow` access.
- Sessions use an opaque random ID, server-side Redis state, idle/absolute expiration, HttpOnly cookies, SameSite=Strict, and Secure cookies outside local development.
- Login is rate-limited by source and username. State-changing API calls require a session-bound CSRF token.
- Nginx applies CSP, frame denial, MIME sniffing protection, referrer restrictions, and request limits.
- Database, Redis, backend, and frontend are internal-only. Only Nginx publishes HTTP/HTTPS.
- Secrets come from deployment secret storage/environment and never Git. Production secrets are unavailable in research or agent environments.
- Audit activity records authenticated mutations without secrets.
- Trading is disabled by configuration and absence of execution endpoints.

Staging uses separate credentials, database, Redis, hostname, and restricted synthetic/paper data. Production uses DigitalOcean secret injection, encrypted backups, least-privilege service identities, TLS, and a separate execution security domain. Brokerage credentials will live only in that domain.

