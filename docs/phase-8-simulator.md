# Phase 8 — Aegis Simulator

Aegis Simulator is an independent paper environment. A paper order requires one unused `AUTHORIZED` Phase 6 RiskAssessment and a matching, normalized Phase 3 `QUOTE` observed within 300 seconds. The simulator rechecks symbol, side, quantity, price movement, cash or position availability, and rejects stale/invalid inputs.

Market fills are deterministic: the normalized quote plus five basis points of adverse slippage and a $1 commission. Paper cash, average-cost positions, fills, realized/unrealized P&L, marked equity, and return are persisted in PostgreSQL. Each fill is audited.

The paper service imports no broker, gateway, Robinhood, AI, or execution adapter. Responses explicitly report `environment=PAPER`, `broker_called=false`, `live_execution_available=false`, and `trading=DISABLED`. A paper fill is evidence, never a live order.

Production acceptance completed on 2026-08-19 at version `0.7.0-simulator` and migration `0011_phase8_simulator`. A fresh official SPY quote and deterministic RiskEngine authorization produced a persisted paper-only fill with explicit friction. CI, isolation, authentication, duplicate rejection, portfolio marking, and absence of non-paper order routes passed. PostgreSQL records Phase 8 as 6/6 COMPLETE; trading remains disabled.
