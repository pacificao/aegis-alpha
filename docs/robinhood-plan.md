# Robinhood official integration boundary

Verified against Robinhood's official Agentic Trading documentation on 2026-08-15. The supported endpoint is `https://agent.robinhood.com/mcp/trading`. Robinhood authentication uses its browser OAuth/onboarding flow; Aegis never asks for or stores a Robinhood password, pasted bearer token, API key, or private key.

## Implemented Phase 1 flow

1. The operator signs in to Aegis and opens **System**.
2. Aegis shows the fixed official endpoint and requires an explicit browser confirmation.
3. The backend sends a narrow connect request to the broker gateway. It cannot issue arbitrary MCP tool calls.
4. The gateway redirects the browser to Robinhood's official authorization page.
5. Robinhood returns to Aegis's exact OAuth callback URL.
6. The gateway encrypts OAuth client/token state at rest, lists the advertised tools, rejects unknown or mutation tools, and validates only `get_accounts`.
7. Aegis reports `CONNECTED`, `DISCONNECTED`, `ERROR`, or `NOT_CONFIGURED`; trading always reports `DISABLED`.

The gateway has no generic call-tool HTTP route. Its exact allowlist contains read-only account, portfolio, position, market-data, order-history, watchlist-read, scan-read, and option-discovery tools. All `place_*`, `cancel_*`, `review_*`, watchlist mutations, scan mutations, and unknown tools are denied. Phase 1 has no live-order path.

## Credential isolation requirement

OAuth must not be completed on this development host. An operator with Docker administration can read container-mounted files and is effectively root; because AI development agents administer this host, local filesystem permissions alone cannot satisfy the permanent credential boundary.

Deploy `broker-gateway` into a separate execution environment that AI development agents cannot administer. Give only that environment access to its encryption key and encrypted token directory. Expose only the exact OAuth callback through Nginx; do not publish port 8100. After that isolation is verified, the operator can click **Connect Robinhood** in Aegis and complete the official browser flow without sharing credentials in chat.

Current development status: `NOT_CONFIGURED`; read-only synchronization is `WAITING_FOR_CREDENTIALS / AUTHORIZATION`. This is intentional and must not be bypassed.

`BROKER_AUTHORIZATION_ENABLED` defaults to `false`. The gateway rejects both authorization start and OAuth callback while false, and Aegis disables the Connect button. Set it to `true` only in the isolated execution deployment after its access boundary has been verified.
