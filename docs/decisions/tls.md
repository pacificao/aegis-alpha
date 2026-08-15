# ADR: Public TLS and direct-IP behavior

Status: implemented 2026-08-15.

The canonical console origin is `https://aegis-alpha.pacificao.com`. DNS points to the deployment address configured outside Git; a Let's Encrypt ECDSA certificate is renewed by the host Certbot timer and mounted read-only into the unprivileged Nginx container. Hostname HTTP and direct-IP UI requests redirect to the canonical HTTPS origin. Only the direct-IP `/health` diagnostic remains plaintext-accessible. This avoids transmitting the Linux PAM password or session cookie over HTTP while retaining IP-based reachability.

TLS permits versions 1.2 and 1.3, disables session tickets, sends HSTS on HTTPS, and retains the existing CSP and security headers. Certificate private keys remain outside the repository and are group-readable only by the numeric Nginx container group.
