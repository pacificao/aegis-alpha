# ADR 0004: Official provider-neutral research data boundary

## Decision

Aegis stores normalized, source-attributed records behind provider-neutral adapters. Official Alpha Vantage, FRED, SEC EDGAR, and NYSE interfaces/policies are the initial sources. No reverse-engineered market endpoint is permitted.

Provider credentials remain runtime secrets. Browser forms may request non-secret ingestion identifiers but never accept API keys. Source payloads cannot cause strategy decisions or orders; later deterministic strategy and risk layers consume validated records through separate interfaces.

PostgreSQL is authoritative, Redis is an expiring cache, ingestion is idempotent, and quality failures remain visible rather than silently repaired. UTC is authoritative for event/audit times; exchange/operator timezones are presentation and scheduling concerns.

## Consequences

Credentialed datasets can remain unavailable while credential-free SEC, FRED, and calendar capabilities operate. Phase completion reporting must distinguish tested adapters from verified live connectivity. Provider replacement does not require strategy, risk, or execution redesign.
