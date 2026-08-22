"""Deterministic lifecycle maintenance for non-executable capital plans."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DevelopmentActivity, PlannedTrade

EXPIRABLE_PLAN_STATUSES=frozenset({"PLANNED","REVALIDATION_BLOCKED","READY_FOR_FINAL_APPROVAL"})

def expire_missed_plans(db:Session,today:date)->list[int]:
    """Release reservations after their eligible entry session has passed."""
    rows=db.scalars(select(PlannedTrade).where(PlannedTrade.status.in_(EXPIRABLE_PLAN_STATUSES),PlannedTrade.planned_entry_date<today).order_by(PlannedTrade.id)).all()
    expired=[]
    for row in rows:
        row.status="EXPIRED";row.revalidation_detail="ENTRY_SESSION_PASSED";row.notification_status="PENDING";row.notification_event="PLAN_EXPIRED"
        db.add(DevelopmentActivity(actor="system:plan-lifecycle",action="planned_trade_expired",entity_type="planned_trade",entity_id=row.id,detail=f"symbol={row.symbol}; entry={row.planned_entry_date}; released_notional={row.reserved_notional:.2f}; broker_called=false; trading=DISABLED"));expired.append(row.id)
    if expired:db.commit()
    return expired
