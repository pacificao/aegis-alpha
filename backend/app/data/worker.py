"""Restart-safe ingestion and bounded candidate worker."""
from __future__ import annotations
import argparse
import logging
import time
from datetime import datetime
from ..candidate_scanner import scan_batch
from ..dividend_exit_monitor import authorize_recovery_exits, capture_filled_entries, monitor_recovery_exits
from ..broker_sync.service import synchronize
from ..config import get_settings
from ..database import SessionLocal
from ..gateway import BrokerGatewayClient
from ..models import BrokerConnectionConfig
from ..planning import create_qualified_plans, expire_missed_plans, reject_unpayable_plans
from sqlalchemy import select
from .calendar import EASTERN
from .queue import run_batch
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s ingestion-worker %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

def _run_ingestion(settings)->None:
    db=SessionLocal()
    try:logging.info("batch=%s",run_batch(db,settings))
    except Exception:logging.exception("batch_failed")
    finally:db.close()

def _run_candidates(settings)->None:
    db=SessionLocal()
    try:
        logging.info("candidate_scan=%s",scan_batch(db,settings))
        if created:=create_qualified_plans(db,datetime.now(EASTERN).date()):logging.info("qualified_plans=%s risk_authorized=false trading=DISABLED",created)
    except Exception:logging.exception("candidate_scan_failed")
    finally:db.close()

def _run_broker_sync(settings)->None:
    """Refresh the selected account without requiring a browser session."""
    db=SessionLocal()
    try:
        config=db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider=="robinhood"))
        if not config or not config.selected_account_ref:
            logging.info("broker_sync=skipped reason=account_not_selected");return
        client=BrokerGatewayClient(settings)
        if client.status().get("status")!="CONNECTED":
            logging.info("broker_sync=skipped reason=gateway_not_connected");return
        run=synchronize(db,client,"system:broker-sync",config.selected_account_ref)
        logging.info("broker_sync=%s snapshot_id=%s attempts=%s",run.status,run.snapshot_id,run.attempts)
    except Exception:logging.exception("broker_sync_failed")
    finally:db.close()

def _run_exit_monitor()->None:
    db=SessionLocal()
    try:
        opened=capture_filled_entries(db);exits=monitor_recovery_exits(db);authorized=authorize_recovery_exits(db)
        if opened or exits:logging.info("dividend_exit_lifecycle opened=%s exit_plans=%s authorized_exits=%s broker_called=false trading=DISABLED",opened,exits,authorized)
    except Exception:logging.exception("dividend_exit_monitor_failed")
    finally:db.close()

def _expire_plans()->None:
    db=SessionLocal()
    try:
        rejected=reject_unpayable_plans(db);expired=expire_missed_plans(db,datetime.now(EASTERN).date())
        if rejected or expired:logging.info("rejected_unpayable_plans=%s expired_plans=%s released_reservations=true",rejected,expired)
    except Exception:logging.exception("plan_expiry_failed")
    finally:db.close()

def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--once",action="store_true");args=parser.parse_args();settings=get_settings()
    if not settings.ingestion_worker_enabled and not args.once:
        logging.info("disabled")
        while True:time.sleep(settings.ingestion_worker_interval_seconds)
    next_candidate_scan=0.0
    next_broker_sync=0.0
    while True:
        _expire_plans()
        _run_ingestion(settings)
        _run_exit_monitor()
        if settings.broker_sync_enabled and time.monotonic()>=next_broker_sync:
            _run_broker_sync(settings);next_broker_sync=time.monotonic()+settings.broker_sync_interval_seconds
        if settings.candidate_scanner_enabled and time.monotonic()>=next_candidate_scan:
            _run_candidates(settings);next_candidate_scan=time.monotonic()+settings.candidate_scanner_interval_seconds
        if args.once:return
        time.sleep(settings.ingestion_worker_interval_seconds)
if __name__=="__main__":main()
