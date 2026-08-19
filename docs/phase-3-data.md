# Phase 3 — Aegis Data

Phase 3 establishes trusted research data without adding execution capability. Trading remains disabled.

## Architecture

`DataProvider` adapters fetch only officially supported endpoints. Provider responses normalize into immutable `DataRecord` rows linked to providers and instruments. SHA-256 canonical checksums make ingestion idempotent. Every row carries event time, observation time, ingestion time, source URL, interval, quality status, and original normalized payload.

Supported adapters:

- Alpha Vantage official API: adjusted daily OHLCV, quotes, company overview fundamentals, dividends/corporate actions, and news sentiment. A provider key is required.
- Federal Reserve FRED: economic observations through the official credential-free CSV endpoint, with optional authenticated JSON API support.
- SEC EDGAR Data APIs: credential-free company facts using the required identifying User-Agent.
- NYSE calendar: deterministic regular-session generation using the official hours/holiday policy, US/Eastern exchange time, UTC storage, weekend/holiday closure, and a bounded query range.

## Quality and caching

Validation rejects empty payloads, naive/future timestamps, invalid OHLC ranges, negative volume, and non-finite values. Quotes older than 15 minutes are flagged stale. Issues are stored separately with severity and code. Redis caches authenticated readiness responses with bounded TTL and is invalidated after ingestion; PostgreSQL remains authoritative.

## APIs

- `GET /api/data/status` — provider credentials, latest runs, counts, freshness, quality, and trading invariant.
- `GET /api/data/records` — bounded normalized-record query by type and symbol.
- `GET /api/data/calendar` — bounded exchange-session range.
- `POST /api/data/ingest` — CSRF-protected, allowlisted provider/dataset ingestion with audit history.

Provider secrets are environment-only, never returned by APIs or accepted by the browser. The Data Sources console accepts only non-secret identifiers such as ticker, FRED series, or SEC CIK.

## Credential boundary

`ALPHA_VANTAGE_API_KEY` is required to run production market history, real-time quote, dividend, and news ingestion. Obtain it through Alpha Vantage's official API-key flow, store it only in the protected `.env`, and recreate the backend. `FRED_API_KEY` is optional because Aegis uses FRED's official CSV endpoint when absent.

Alpha Vantage authorization is configured only in the protected runtime environment. Live official production calls passed for standard daily OHLCV, quote, dividends, and news. The standard daily endpoint intentionally avoids the premium adjusted-history endpoint; dividend events remain a separately normalized feed.

## Official references

- https://www.alphavantage.co/documentation/
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://fred.stlouisfed.org/docs/api/fred/
- https://www.nyse.com/markets/hours-calendars
