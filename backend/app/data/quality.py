import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from typing import Any

def checksum(data_type: str, external_id: str, event_time: datetime, payload: dict[str,Any]) -> str:
    canonical=json.dumps({"data_type":data_type,"external_id":external_id,"event_time":event_time.astimezone(UTC).isoformat(),"payload":payload},sort_keys=True,separators=(",",":"),default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()

def validate(data_type: str, event_time: datetime, payload: dict[str,Any], now: datetime | None = None) -> list[tuple[str,str,str]]:
    now=now or datetime.now(UTC); issues=[]
    if event_time.tzinfo is None: issues.append(("ERROR","NAIVE_TIMESTAMP","Event time must include timezone"))
    elif event_time > now + timedelta(minutes=5): issues.append(("ERROR","FUTURE_TIMESTAMP","Event time is unexpectedly in the future"))
    def finite(value: Any) -> bool: return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
    if data_type=="OHLCV":
        required=("open","high","low","close","volume")
        if any(not finite(payload.get(key)) for key in required): issues.append(("ERROR","INVALID_OHLCV","OHLCV fields must be finite numbers"))
        elif payload["high"] < max(payload["open"],payload["low"],payload["close"]) or payload["low"] > min(payload["open"],payload["high"],payload["close"]): issues.append(("ERROR","OHLC_RANGE","OHLC price range is inconsistent"))
        if finite(payload.get("volume")) and payload["volume"] < 0: issues.append(("ERROR","NEGATIVE_VOLUME","Volume cannot be negative"))
    if data_type=="QUOTE" and event_time.tzinfo is not None and event_time < now-timedelta(minutes=15): issues.append(("WARNING","STALE_QUOTE","Quote is older than 15 minutes"))
    if not payload: issues.append(("ERROR","EMPTY_PAYLOAD","Provider payload is empty"))
    return issues
