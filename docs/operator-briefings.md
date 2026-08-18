# Operator Briefings and Alerts

Recipient: `nathan@pacificao.com`. Delivery must be configurable outside source control.

## Safety and information policy

Aegis uses lawful public information and authorized portfolio data only. It must never solicit, ingest, infer, or distribute material nonpublic information. Every actionable claim needs source attribution, observed time, freshness, confidence, and a clear distinction between fact and inference.

Email is notification-only. Links return the operator to authenticated Aegis. Email replies, pixels, and links cannot authorize orders, change risk limits, approve scenarios, or perform sensitive actions.

## Pre-market decision briefing

Schedule against the exchange calendar, before the primary market opens—not a fixed weekday-only clock. Include:

- executive summary and the few decisions that matter;
- overnight market, macroeconomic, earnings, dividend, corporate-action, and material news changes;
- verified portfolio value, cash, exposure, concentration, drawdown, scheduled events, and risk-budget use;
- scenario-specific opportunities, expected edge, evidence quality, constraints, and reasons to reject;
- items requiring Nathan's review, with authenticated deep links;
- Aegis data freshness and a compact system-readiness footer.

## Post-market highlights

Send after the official close and required data-settlement delay. Include daily gains/losses and attribution, dividends and material portfolio changes, decisions and rejected proposals, risk-limit proximity, notable events, and concise day/week/month context. Prefer highlights and exceptions over a heavy report.

## Attention alerts

Alert only on actionable state transitions: stale/failed data, broker disconnect, reconciliation mismatch, risk-limit approach or breach, scenario pause, failed scheduled job, security event, or explicit user interaction required. Define severity, deduplication key, cooldown, escalation, acknowledgement, recovery notification, and an immutable audit record. Never include secrets, tokens, full account numbers, or sensitive holdings beyond the operator's configured email policy.

## Delivery architecture

Use a provider-neutral notification adapter, durable outbox, idempotency key, retry with bounded backoff, delivery/audit status, HTML plus plain-text templates, unsubscribe/preferences for noncritical mail, and exchange-calendar-aware scheduling. Credentials remain in a root-protected runtime secret or managed secret store.

Before enabling delivery, configure a transactional email provider, verified sender domain, SPF, DKIM, DMARC, reply handling, and alert escalation policy. Tests must use a capture transport and prove redaction, deduplication, scheduling, retries, and that notification actions cannot mutate trading state.
