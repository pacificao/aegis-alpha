"""Normalize, persist, and reconcile immutable read-only broker snapshots."""
from __future__ import annotations
import hashlib,json,time
from datetime import UTC,datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..gateway import BrokerGatewayClient
from ..models import BrokerSnapshot,BrokerSyncRun,DevelopmentActivity

_ALLOWED_DATASETS=frozenset({"get_portfolio","get_equity_positions","get_equity_tax_lots","get_equity_orders","get_option_positions","get_option_orders","get_crypto_positions","get_crypto_orders","get_realized_pnl","get_pnl_trade_history"})

def _canonical(value:object)->str:return json.dumps(value,sort_keys=True,separators=(",",":"),default=str)
def _number(value:object)->float|None:
    try:return float(str(value).replace("\x24","").replace(",",""))
    except (TypeError,ValueError):return None
def _rows(value:object)->list:
    if isinstance(value,list):return value
    if isinstance(value,dict):
        for key in ("results","items","data","positions","orders","executions","fills"):
            if key in value and isinstance(value[key],list):return value[key]
        return [value]
    return []
def _fills(value:object)->list:
    found=[]
    if isinstance(value,dict):
        for key,item in value.items():
            if key.lower() in {"executions","fills"} and isinstance(item,list):found.extend(item)
            else:found.extend(_fills(item))
    elif isinstance(value,list):
        for item in value:found.extend(_fills(item))
    return found

def normalize(payload:dict)->dict:
    if len(_canonical(payload))>8_000_000:raise ValueError("GATEWAY_RESPONSE_TOO_LARGE")
    if payload.get("trading")!="DISABLED" or payload.get("mode")!="READ_ONLY" or payload.get("status")!="COMPLETE":raise ValueError("UNSAFE_OR_INCOMPLETE_GATEWAY_RESPONSE")
    observed=datetime.fromisoformat(str(payload["observed_at"]).replace("Z","+00:00"))
    if observed.tzinfo is None:raise ValueError("NAIVE_OBSERVED_TIME")
    accounts=payload.get("accounts")
    if not isinstance(accounts,list) or not accounts or len(accounts)>20:raise ValueError("INVALID_ACCOUNT_SET")
    refs=[];balances=[];holdings=[];orders=[];fills=[];failures=[]
    for account in accounts:
        ref=account.get("account_ref","")
        if not isinstance(ref,str) or not ref.startswith("ref_") or len(ref)>64:raise ValueError("UNSAFE_ACCOUNT_REFERENCE")
        refs.append(ref);datasets=account.get("datasets",{})
        if not isinstance(datasets,dict) or set(datasets)-_ALLOWED_DATASETS:raise ValueError("UNAPPROVED_DATASET")
        for name,value in datasets.items():
            row={"account_ref":ref,"dataset":name,"records":_rows(value)}
            if name in {"get_portfolio","get_realized_pnl","get_pnl_trade_history"}:balances.append(row)
            elif "positions" in name or "tax_lots" in name:holdings.append(row)
            elif "orders" in name:
                orders.append(row)
                for fill in _fills(value):fills.append({"account_ref":ref,"dataset":name,"record":fill})
        for failure in account.get("failures",[]):
            failures.append({"account_ref":ref,"tool":str(failure.get("tool","unknown"))[:80],"code":str(failure.get("code","READ_FAILED"))[:60]})
    duplicate_refs=len(refs)!=len(set(refs))
    order_rows=[row for group in orders for row in group["records"] if isinstance(row,dict)]
    order_refs=[str(row.get("id") or row.get("order_id") or row.get("client_order_id")) for row in order_rows if row.get("id") or row.get("order_id") or row.get("client_order_id")]
    duplicate_orders=len(order_refs)!=len(set(order_refs));quantity_issues=[]
    for index,row in enumerate(order_rows):
        ordered=_number(row.get("quantity") or row.get("total_quantity"));executed=sum((_number(fill.get("quantity")) or 0) for fill in _fills(row) if isinstance(fill,dict))
        if ordered is not None and executed>ordered+1e-9:quantity_issues.append({"order_index":index,"code":"FILL_EXCEEDS_ORDER_QUANTITY"})
    attention=duplicate_refs or duplicate_orders or failures or quantity_issues
    reconciliation={"status":"ATTENTION" if attention else "MATCHED","account_refs_unique":not duplicate_refs,"order_refs_unique":not duplicate_orders,"fill_quantities_valid":not quantity_issues,"quantity_issues":quantity_issues,"dataset_failures":failures,"order_records":len(order_rows),"fill_records":len(fills)}
    normalized={"provider":"robinhood","status":"PARTIAL" if failures else "VERIFIED","account_count":len(refs),"account_refs":refs,"balances":balances,"holdings":holdings,"orders":orders,"fills":fills,"reconciliation":reconciliation,"source_observed_at":observed}
    normalized["checksum"]=hashlib.sha256(_canonical({**normalized,"source_observed_at":observed.isoformat()}).encode()).hexdigest()
    return normalized

def synchronize(db:Session,client:BrokerGatewayClient,actor:str,max_attempts:int=3)->BrokerSyncRun:
    run=BrokerSyncRun(provider="robinhood",status="RUNNING",attempts=0,error_code="",detail="Read-only synchronization started")
    db.add(run);db.flush()
    payload=None
    for attempt in range(1,max_attempts+1):
        run.attempts=attempt;payload=client.account_snapshot()
        if payload.get("status")!="ERROR":break
        if attempt<max_attempts:time.sleep(0.05*(2**(attempt-1)))
    try:
        normalized=normalize(payload or {})
        snapshot=db.scalar(select(BrokerSnapshot).where(BrokerSnapshot.checksum==normalized["checksum"]))
        if snapshot is None:
            snapshot=BrokerSnapshot(**normalized,created_by=actor);db.add(snapshot);db.flush()
        run.snapshot_id=snapshot.id;run.status="COMPLETE" if normalized["status"]=="VERIFIED" else "ATTENTION";run.detail="Immutable read-only snapshot persisted and reconciled"
        action="broker_snapshot_synchronized"
    except (ValueError,TypeError,KeyError):
        run.status="FAILED";run.error_code="BROKER_READ_FAILED";run.detail="Read-only broker synchronization failed safely";action="broker_snapshot_failed"
    run.completed_at=datetime.now(UTC)
    db.add(DevelopmentActivity(actor=actor,action=action,entity_type="broker_sync_run",entity_id=run.id,detail=f"status={run.status}; attempts={run.attempts}; trading=DISABLED; no broker mutation attempted"))
    db.commit();db.refresh(run);return run

def _find(value:object,keys:tuple[str,...])->float|None:
    if isinstance(value,dict):
        for key in keys:
            if key in value and (number:=_number(value[key])) is not None:return number
        for child in value.values():
            if (number:=_find(child,keys)) is not None:return number
    elif isinstance(value,list):
        for child in value:
            if (number:=_find(child,keys)) is not None:return number
    return None

def serialize_snapshot(snapshot:BrokerSnapshot|None,connection:str)->dict:
    if snapshot is None:return {"broker":"Robinhood","connection":connection,"mode":"READ_ONLY","holdings_available":False,"snapshot":None,"detail":"No verified read-only broker snapshot is available.","trading":"DISABLED"}
    observed=snapshot.source_observed_at if snapshot.source_observed_at.tzinfo else snapshot.source_observed_at.replace(tzinfo=UTC)
    age=max(0,int((datetime.now(UTC)-observed).total_seconds()))
    summary={"portfolio_value":_find(snapshot.balances,("total_equity","portfolio_value","equity","total_value")),"buying_power":_find(snapshot.balances,("buying_power","withdrawable_amount")),"cash":_find(snapshot.balances,("cash","cash_available")),"holding_count":sum(len(group.get("records",[])) for group in snapshot.holdings),"order_count":snapshot.reconciliation.get("order_records",0),"fill_count":snapshot.reconciliation.get("fill_records",0)}
    return {"broker":"Robinhood","connection":connection,"mode":"READ_ONLY","holdings_available":snapshot.status in {"VERIFIED","PARTIAL"},"snapshot":{"id":snapshot.id,"summary":summary,"status":snapshot.status,"account_count":snapshot.account_count,"balances":snapshot.balances,"holdings":snapshot.holdings,"orders":snapshot.orders,"fills":snapshot.fills,"reconciliation":snapshot.reconciliation,"checksum":snapshot.checksum,"observed_at":snapshot.source_observed_at,"age_seconds":age,"stale":age>900},"detail":"Verified immutable broker read; order history is non-executable.","trading":"DISABLED"}
