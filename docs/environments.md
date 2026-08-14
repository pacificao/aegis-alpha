# Environments

- Local development: this Ubuntu host, Compose, generated local secrets, HTTP by IP, host PAM bridge, no broker connectivity.
- Staging: separate Droplet/VPC, TLS hostname, staging secrets, synthetic/paper data, no production brokerage credentials.
- Production: separate DigitalOcean project/VPC, TLS-only Nginx, managed secret injection, encrypted backups, monitoring, restricted operator access, and distinct research/execution domains.

