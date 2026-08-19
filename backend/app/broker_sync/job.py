"""Scheduled, bounded, read-only broker snapshot job."""
from sqlalchemy import select
from ..config import get_settings
from ..database import SessionLocal
from ..gateway import BrokerGatewayClient
from ..models import BrokerConnectionConfig
from .service import synchronize

def main()->int:
    settings=get_settings()
    with SessionLocal() as db:
        config=db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider=="robinhood"))
        if config is None or not config.selected_account_ref:
            print("broker_sync status=SKIPPED reason=ACCOUNT_NOT_SELECTED trading=DISABLED")
            return 2
        run=synchronize(db,BrokerGatewayClient(settings),"scheduled-broker-sync",config.selected_account_ref)
        print(f"broker_sync status={run.status} attempts={run.attempts} trading=DISABLED")
        return 0 if run.status in {"COMPLETE","ATTENTION"} else 1
if __name__=="__main__":raise SystemExit(main())
