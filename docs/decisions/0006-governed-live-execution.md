# ADR 0006: Governed controlled-live execution

Aegis permits equity limit-order placement only through the isolated Robinhood gateway after the full chain `AI proposes -> Strategy decides -> RiskEngine authorizes -> operator approves -> Execution submits`. Backend and gateway deployment flags default false and are necessary but insufficient. The operator must create a short-lived authorization of at most 60 minutes and at most $5 per order; the production trial UI fixes the initial acceptance ceiling at $1 for 15 minutes.

Execution locks one immutable intent before the broker call. Repeated requests return the existing terminal record and never resubmit. Known broker rejection is terminal. Network timeout, unverifiable broker evidence, field mismatch, overfill, or unknown cancellation outcome engages the circuit breaker and requires broker-snapshot or human recovery. Fresh snapshots reconcile unfilled, partially filled and filled quantities. Cancellation remains available while risk controls are engaged so an open limit order can be reduced, but it still requires exact account, order, intent and approval references.

Broker OAuth and account identifiers remain unavailable to Aegis and development agents. No AI output can activate the deployment flags, create operator authorization, approve an intent, authorize deterministic risk, or bypass reconciliation.
