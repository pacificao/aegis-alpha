"""Deterministic fractional-dividend payment qualification."""
from decimal import Decimal, InvalidOperation

MINIMUM_PAYABLE_DIVIDEND = Decimal("0.005")
ZERO_PAYMENT_REASON = "FILTER_EXPECTED_DIVIDEND_ROUNDS_TO_ZERO"

def expected_dividend(quantity: object, dividend_per_share: object) -> Decimal | None:
    try:
        value = Decimal(str(quantity)) * Decimal(str(dividend_per_share))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return value if value.is_finite() and value >= 0 else None

def expected_dividend_from_event_yield(notional: object, event_yield_pct: object) -> Decimal | None:
    try:
        value = Decimal(str(notional)) * Decimal(str(event_yield_pct)) / Decimal("100")
    except (InvalidOperation, TypeError, ValueError):
        return None
    return value if value.is_finite() and value >= 0 else None

def payable_fractional_dividend(*, quantity: object = None, dividend_per_share: object = None,
                                notional: object = None, event_yield_pct: object = None) -> tuple[bool, Decimal | None]:
    value = expected_dividend(quantity, dividend_per_share)
    if value is None:
        value = expected_dividend_from_event_yield(notional, event_yield_pct)
    return bool(value is not None and value >= MINIMUM_PAYABLE_DIVIDEND), value
