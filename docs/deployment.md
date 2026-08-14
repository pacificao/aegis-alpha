# DigitalOcean Deployment Plan

Use an Ubuntu LTS Droplet on a private VPC with a reserved IP. DigitalOcean Cloud Firewall and host UFW allow the verified SSH port from trusted administration ranges and HTTP/HTTPS publicly. Nginx is the only public container. PostgreSQL and Redis should move to managed/private services when production requirements justify it; they never receive public endpoints.

DNS uses an `aegis` subdomain with a low-TTL A record during migration, then TLS via ACME. IP-only development remains HTTP because publicly trusted certificates generally require DNS; never use a misleading self-signed production setup.

Backups include encrypted database dumps plus provider snapshots, stored in a separate account/bucket with retention and restoration drills. Redis session data is disposable. Deployment is CI-built immutable images -> staging migration/smoke tests -> human approval -> production migration/rolling restart -> health verification -> rollback to prior image. Git tags follow `vMAJOR.MINOR.PATCH`; Phase 1 release is `v0.1.0-core`.

