# Robinhood official integration boundary

Verified against Robinhood's official Agentic Trading documentation on 2026-08-14. The supported endpoint is `https://agent.robinhood.com/mcp/trading`. Connection uses a desktop browser OAuth/onboarding flow and a dedicated Agentic account. The MCP can expose account numbers, balances, positions, transactions, orders, watchlists, and scans, and it is also capable of placing orders; therefore Aegis must never attach it directly to an AI research process or expose write tools in Phase 1.

Phase 1 implements only a provider-neutral `BrokerAdapter.status()` boundary and `RobinhoodBrokerAdapter` with `NOT_CONFIGURED`, `CONNECTED`, `DISCONNECTED`, and `ERROR` as the allowed operational vocabulary. Current status is `NOT_CONFIGURED`. The application has no order method, route, credential field, or hidden execution capability. Read-only account synchronization remains WAITING_FOR_CREDENTIALS and must be mediated by a future allowlisted MCP gateway that rejects every mutation tool and redacts account identifiers from logs.

Official operator flow: in Codex Settings → MCP servers, choose Streamable HTTP and add `https://agent.robinhood.com/mcp/trading`; select the server and complete Robinhood's desktop authentication/onboarding. Do not paste a password or token into chat. Successful completion means the MCP reports authenticated and read-only account queries can be verified through the allowlisted gateway while Aegis still reports trading DISABLED.

## Console UX decision

The Aegis frontend must not contain a Robinhood username/password, token, API-key, or arbitrary MCP-URL form. Official Agentic Trading authentication is completed in the MCP client's browser/OAuth flow. The console may safely show connection state, the fixed official endpoint, setup instructions, and a user-triggered “Check connection” action once a server-side allowlisted read-only gateway exists. It must never accept or proxy brokerage credentials, and it must never expose MCP order tools during Phase 1.
