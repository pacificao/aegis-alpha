# Networking Plan

Public: SSH on the detected host port, TCP 80 for initial access/ACME, TCP 443 for TLS. Internal Compose network only: Nginx to frontend/backend; backend to PostgreSQL/Redis. No host mappings exist for ports 3000, 8000, 5432, or 6379.

Before UFW changes, detect SSH from `sshd -T` or listening sockets, allow it first, inspect numbered rules, preserve a second SSH session, then enable. See `scripts/ufw-plan.sh`. DigitalOcean Cloud Firewall rules must agree with host rules.


## Verified TLS endpoint

`aegis-alpha.pacificao.com` resolves to `144.126.211.97`. Nginx publishes TCP 80 and 443; hostname HTTP requests redirect to HTTPS, and direct-IP requests redirect to the same trusted HTTPS hostname so login credentials are never submitted over plaintext HTTP. `http://144.126.211.97/health` remains directly available for diagnostics. PostgreSQL, Redis, FastAPI, and Next.js remain unbound from the host.

Let's Encrypt certificate files remain outside Git under `/etc/letsencrypt`. `certbot.timer` is enabled, the webroot challenge is `/var/lib/aegis-certbot`, and the deploy hook reloads the containerized Nginx after renewal. The renewal simulation passed on 2026-08-15.
