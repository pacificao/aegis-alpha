# ADR 0002: Broker credentials require a separate execution security domain

Status: accepted, 2026-08-15.

Robinhood's official Trading MCP exposes both read and mutation tools. Aegis therefore uses a dedicated broker gateway with no generic tool-call API. Its exact allowlist contains documented read operations; all unknown tools plus `place_*`, `cancel_*`, `review_*`, watchlist mutations, and scan mutations fail closed. Phase 1 has no confirmation path that can enable these tools: trading is unconditionally disabled.

OAuth uses the official MCP authorization-code/PKCE client flow. Token and dynamic-client material are encrypted before atomic `0600` writes. The encryption key and ciphertext directory are mounted only into the gateway. APIs expose status and sanitized counts, never tokens, account numbers, or raw MCP responses.

A root-owned directory on the development Docker host is not a production security boundary because Docker administration is root-equivalent. Real brokerage authorization must occur only after this gateway is deployed in a separate execution environment that AI development agents cannot administer. The Aegis browser initiates that remote authorization; no password or token is entered into Aegis. Recovery reauthorizes through OAuth instead of backing up broker tokens.
