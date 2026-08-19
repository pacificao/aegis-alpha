# Aegis Alpha

> **Publicly visible, proprietary software — not open source.** Viewing this repository grants no right to use, copy, modify, deploy, distribute, commercialize, or create derivative works. See [LICENSE](LICENSE).

A private, auditable AI-assisted quantitative-investment platform. Phase 7 adds cited, checksummed intelligence artifacts, independent Strategy Council reviews, deterministic fail-closed consensus, and an authenticated workbench. AI remains proposal-only; deterministic RiskEngine authorization is separate and trading is hard-disabled.

## Prerequisites (Ubuntu 24.04)

Docker Engine with the Compose plugin is required. If `docker --version` is unavailable, the operator must install it using Docker's official Ubuntu instructions; see `docs/ubuntu-setup.md`. Node and Python are only required on the host for non-container development.

## Configure and start

```bash
cp .env.example .env
sed -i "s/CHANGE_ME_GENERATE_A_RANDOM_VALUE/$(openssl rand -hex 32)/" .env
sudo install -d -o 10001 -g 10001 -m 0700 /var/lib/aegis-broker-gateway
sudo install -d -o root -g 10001 -m 0750 /etc/aegis
openssl rand -base64 32 | tr "+/" "-_" | sudo tee /etc/aegis/broker-gateway.key >/dev/null
sudo chown root:10001 /etc/aegis/broker-gateway.key
sudo chmod 0440 /etc/aegis/broker-gateway.key
docker compose build
docker compose up -d
docker compose ps
```

The replacement command creates a local random value; inspect `.env` and use distinct database/session secrets before staging. `.env` is ignored by Git.

Authentication intentionally fails closed until the root-owned host PAM bridge described in `docs/decisions/authentication.md` is installed. The application never reads, copies, logs, or stores the Linux password.

## Operations

```bash
# Stop
docker compose down

# Logs
docker compose logs -f --tail=200

# Backend tests (module form preserves the application import path)
docker compose run --rm backend python -m pytest -q

# Frontend checks, tests, and production build
docker build --target build -t aegis-alpha-frontend-test ./frontend
docker run --rm --entrypoint npm aegis-alpha-frontend-test run lint
docker run --rm --entrypoint npm aegis-alpha-frontend-test test -- --run

# Full validation
./scripts/verify.sh

# Server public IP and browser URL
hostname -I
printf 'http://%s/\n' "$(hostname -I | awk '{print $1}')"
```

## Safe firewall configuration

Do not run these blindly. First confirm the detected SSH port and compare the plan in `scripts/ufw-plan.sh` with your DigitalOcean firewall. This repository never enables UFW automatically.

```bash
./scripts/ufw-plan.sh
# The operator runs the printed sudo commands only after verifying SSH access on a second session.
```

Externally, Compose publishes only Nginx on ports 80/443. PostgreSQL, Redis, FastAPI, and Next.js have no host port mappings.

## Troubleshooting

- `docker: command not found`: complete `docs/ubuntu-setup.md`, log out/in after Docker group changes, then retry.
- `Authentication service unavailable`: install/start the PAM bridge per `docs/decisions/authentication.md`; this is the safe expected failure before host integration.
- unhealthy database/Redis: run `docker compose ps` and `docker compose logs postgres redis backend`.
- migration failure: verify `DATABASE_URL` and `POSTGRES_PASSWORD` use the same generated password, then run `docker compose run --rm backend alembic upgrade head`.
- port 80 already used: inspect with `sudo ss -ltnp '( sport = :80 )'`; do not terminate an unknown service.
- stale build: run `docker compose build --no-cache` and restart.

Architecture, roadmap, security boundaries, deployment planning, and current verified state are in `docs/`.

## Public development endpoint

The canonical endpoint is `https://aegis-alpha.pacificao.com`. HTTP and direct-IP UI requests redirect there; direct-IP `/health` remains available for diagnostics. TLS is renewed automatically with Certbot. Never submit the Linux password through a plaintext HTTP URL.
The authenticated System page saves non-secret MCP metadata and initiates Robinhood’s official browser/OAuth flow through the isolated Aegis broker gateway. Never enter a Robinhood password or token into Aegis, and never authorize brokerage access on the AI-administered development host.

Phase 5 adds **Aegis Lab** under Performance: authenticated, checksummed, research-only portfolio backtesting with explicit frictions, corporate actions, benchmarks, robustness analysis, and inspectable trades. Lab results are not portfolio results and cannot trade.

Phase 7 adds **Aegis Intelligence** under Suggested Adjustments. Provider-neutral AI clients and operators submit strictly bounded, cited artifacts; independent checksum-bound reviews produce fail-closed governance. Intelligence can only propose and never authorizes risk or executes.

Phase 8 adds **Aegis Simulator** under Performance: fresh-data, risk-gated paper fills, isolated paper positions, and paper performance. The simulator has no broker dependency and cannot place live orders.