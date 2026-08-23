# Production and Robinhood handoff

This repository is production-deployable, but the current server remains the development environment under `AGENTS.md`. Do not relabel an AI-administered host as the brokerage execution security domain.

## Required production boundary

Deploy `broker-gateway` on a separate host/project and private network that the development AI identity, development SSH identity, CI, research workers, and main application Docker daemon cannot administer. Expose only its exact HTTPS OAuth callback. Permit its internal status/connect/disconnect API only from the Aegis backend through a private authenticated channel.

Create the encryption key directly inside that protected domain. It must be owned by the gateway administrator, readable by the gateway group, not readable by other users, and never copied into Git, chat, logs, CI, the backend, or backups. The ciphertext directory must be owned by the gateway runtime and mode `0700`.

The gateway deliberately contains no generic MCP proxy. Every tool invocation passes an exact read-only allowlist. Orders, cancellations, reviews, watchlist mutations, scan mutations, and unknown tools are rejected. `AEGIS_TRADING_ENABLED=true` is rejected during application configuration.

## Operator authorization

After the separate gateway is deployed and administrative access has been removed from development agents:

1. Set `BROKER_AUTHORIZATION_ENABLED=true` only in the protected gateway environment and restart that gateway.
2. Sign in to Aegis at `https://aegis-alpha.pacificao.com` from a desktop browser.
3. Open **System**, verify the endpoint is exactly `https://agent.robinhood.com/mcp/trading`, and select **Connect Robinhood in browser**.
4. Complete Robinhood's own browser flow. Do not enter a Robinhood password, token, API key, or private key into an Aegis form or chat.
5. Return to Aegis and verify `CONNECTED`, `READ_ONLY`, `Trading DISABLED`, and a populated read-sync timestamp.
6. Verify gateway logs contain tool counts and status only, never account data or authorization material.

If Robinhood advertises renamed or new read tools, Aegis blocks them until the allowlist and tests receive human review. If any validation fails, disconnect in Aegis and revoke the connection from Robinhood.

Robinhood's official Agentic Trading MCP can expose trading tools. The OAuth connection by itself is therefore not the safety boundary; the isolated Aegis gateway, absence of order APIs, and later deterministic RiskEngine/Execution separation are mandatory controls.

## Current dedicated target

The prepared operator bootstrap targets Ubuntu 24.04 at private VPC address `10.124.0.4`, hostname `brokerage.aegis-alpha.pacificao.com`, and permits the Aegis server private address `10.124.0.3`. Nathan runs `scripts/bootstrap-broker-droplet.sh` as root from the DigitalOcean browser console. Review it before execution; it does not install an AI/development SSH credential.

## Protected-main automatic updates

After a reviewed release is promoted to protected `main`, the operator may install the root-owned broker-only updater from the DigitalOcean console with `bash /opt/aegis-broker/source/scripts/install-broker-auto-update.sh`. It checks `main` every five minutes, accepts fast-forward updates only, refuses dirty repositories, rebuilds only `broker-gateway`, verifies public health, records the deployed revision under `/var/lib/aegis-broker/deployment`, and rolls back a failed deployment. Production OAuth and gateway data directories are never replaced.
