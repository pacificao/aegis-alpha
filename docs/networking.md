# Networking Plan

Public: SSH on the detected host port, TCP 80 for initial access/ACME, TCP 443 for TLS. Internal Compose network only: Nginx to frontend/backend; backend to PostgreSQL/Redis. No host mappings exist for ports 3000, 8000, 5432, or 6379.

Before UFW changes, detect SSH from `sshd -T` or listening sockets, allow it first, inspect numbered rules, preserve a second SSH session, then enable. See `scripts/ufw-plan.sh`. DigitalOcean Cloud Firewall rules must agree with host rules.

