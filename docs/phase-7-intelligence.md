# Phase 7 — Aegis Intelligence

Aegis Intelligence is a provider-neutral, non-executable proposal and review boundary. It accepts strictly bounded intelligence artifacts for strategy creation and critique, regime/news/fundamental/parameter research, post-trade review, anomaly detection, pre-market briefings, post-market digests, and attention alerts.

Every artifact requires HTTPS citations, evidence timestamps, explicit freshness limits, a confidence value, a countercase in structured analysis, and an immutable SHA-256 checksum. Stale or invalid evidence fails to `NEEDS_REVIEW`. The database preserves the complete evidence snapshot and audit activity.

The Strategy Council records independent reviews against the exact artifact checksum. Two independent approvals may make only `RESEARCH`, `HOLD`, or `ADJUST` artifacts eligible for deterministic RiskEngine review. Disagreement, missing reviews, stale/mismatched evidence, abstention, and all `BUY`, `SELL`, `PAUSE`, or `ESCALATE` recommendations require human review. Two rejections reject. This layer never sets `risk_authorized`, never produces an executable object, and has no broker or order dependency.

The existing scheduled operator-email system remains the delivery layer for pre-market, post-market, and attention communications. Phase 7 artifacts provide cited, freshness-scored intelligence inputs; delivery failures cannot change governance state.
