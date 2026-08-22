"""Restart-safe ingestion and bounded candidate worker."""
from __future__ import annotations
import argparse
import logging
import time
from ..candidate_scanner import scan_batch
from ..config import get_settings
from ..database import SessionLocal
from .queue import run_batch
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s ingestion-worker %(message)s")

def _run_ingestion(settings)->None:
    db=SessionLocal()
    try:logging.info("batch=%s",run_batch(db,settings))
    except Exception:logging.exception("batch_failed")
    finally:db.close()

def _run_candidates(settings)->None:
    db=SessionLocal()
    try:logging.info("candidate_scan=%s",scan_batch(db,settings))
    except Exception:logging.exception("candidate_scan_failed")
    finally:db.close()

def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--once",action="store_true");args=parser.parse_args();settings=get_settings()
    if not settings.ingestion_worker_enabled and not args.once:
        logging.info("disabled")
        while True:time.sleep(settings.ingestion_worker_interval_seconds)
    next_candidate_scan=0.0
    while True:
        _run_ingestion(settings)
        if settings.candidate_scanner_enabled and time.monotonic()>=next_candidate_scan:
            _run_candidates(settings);next_candidate_scan=time.monotonic()+settings.candidate_scanner_interval_seconds
        if args.once:return
        time.sleep(settings.ingestion_worker_interval_seconds)
if __name__=="__main__":main()
