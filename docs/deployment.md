# DigitalOcean Deployment Plan

Use an Ubuntu LTS Droplet on a private VPC with a reserved IP. DigitalOcean Cloud Firewall and host UFW allow the verified SSH port from trusted administration ranges and HTTP/HTTPS publicly. Nginx is the only public container. PostgreSQL and Redis should move to managed/private services when production requirements justify it; they never receive public endpoints.

DNS uses an `aegis` subdomain with a low-TTL A record during migration, then TLS via ACME. IP-only development remains HTTP because publicly trusted certificates generally require DNS; never use a misleading self-signed production setup.

Backups include encrypted database dumps plus provider snapshots, stored in a separate account/bucket with retention and restoration drills. Redis session data is disposable. Deployment is CI-built immutable images -> staging migration/smoke tests -> human approval -> production migration/rolling restart -> health verification -> rollback to prior image. Git tags follow `vMAJOR.MINOR.PATCH`; Phase 1 release is `v0.1.0-core`.


## Phase 1 production topology details

Recommended initial staging size is a 2 vCPU/4 GiB Ubuntu LTS Droplet; production begins at 4 vCPU/8 GiB after measured load tests, with separate staging and production projects/VPCs. Cloud Firewall inbound policy is TCP 443 from anywhere, TCP 80 only for redirect/ACME, and the verified SSH port only from Nathan's trusted administration CIDRs; deny all other inbound traffic. Databases use private VPC endpoints/security groups only. DNS uses separate staging and production names, CAA records, short migration TTLs, then managed TLS renewal monitoring.

Monitoring covers external HTTPS, container health/restarts, disk/inode pressure, database connections/backup age, migration revision, authentication failures/rate limiting, and certificate expiry without recording secrets. Deploy immutable digest-pinned images, take a pre-migration backup, run forward migrations once, smoke staging, require human promotion, and record the Git tag/image digest/migration revision. Rollback restores the prior image; database rollback occurs only after a rehearsed migration-specific decision. Provider snapshots supplement but never replace encrypted logical dumps and restore drills.

## Broker execution domain

Deploy `broker-gateway` in a separate project/VPC or host account that the development AI identity, development SSH identity, and development Docker daemon cannot administer. Permit its internal API only from the Aegis backend over a private authenticated channel; publish only the exact OAuth callback through TLS. Store the Fernet key in the platform secret store and ciphertext in a `0700` gateway-owned directory. Never mount either into backend, frontend, Nginx, research workers, CI, or backup jobs. Recovery creates a new key only for a new authorization and requires Nathan to repeat browser OAuth; broker tokens are deliberately excluded from backups.
