"""Restart-safe ingestion queue worker."""
from __future__ import annotations
import argparse
import logging
import time
from ..config import get_settings
from ..database import SessionLocal
from .queue import run_batch
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s ingestion-worker %(message)s")
def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--once",action="store_true");args=parser.parse_args();settings=get_settings()
    if not settings.ingestion_worker_enabled and not args.once:
        logging.info("disabled")
        while True:time.sleep(settings.ingestion_worker_interval_seconds)
    while True:
        db=SessionLocal()
        try:logging.info("batch=%s",run_batch(db,settings))
        except Exception:logging.exception("batch_failed")
        finally:db.close()
        if args.once:return
        time.sleep(settings.ingestion_worker_interval_seconds)
if __name__=="__main__":main()
