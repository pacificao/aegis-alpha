"""Refresh non-executable benchmark history immediately before operator briefings."""
from __future__ import annotations
import json
from ..config import get_settings
from ..database import SessionLocal
from .service import ingest

BENCHMARKS=("SPY","QQQ","IWM")

def refresh()->dict:
    settings=get_settings();results={}
    with SessionLocal() as db:
        for symbol in BENCHMARKS:
            run=ingest(db,settings,"alpaca","historical",symbol)
            results[symbol]={"status":run.status,"accepted":run.accepted,"rejected":run.rejected}
    return {"benchmarks":results,"mode":"READ_ONLY","trading":"DISABLED"}

if __name__=="__main__":print(json.dumps(refresh(),sort_keys=True))
