"""Deterministic intended/actual/fill reconciliation for controlled execution."""
from __future__ import annotations
from ..strategy_engine import canonical_checksum

def reconcile(intended:dict,actual:dict,fills:list[dict])->dict:
    expected={"symbol":str(intended.get("symbol","")).upper(),"side":str(intended.get("side","")).upper(),"quantity":float(intended.get("quantity",0)),"order_type":str(intended.get("order_type","")).upper(),"limit_price":float(intended.get("limit_price",0))}
    observed={"symbol":str(actual.get("symbol","")).upper(),"side":str(actual.get("side","")).upper(),"quantity":float(actual.get("quantity",0)),"order_type":str(actual.get("order_type",actual.get("type",""))).upper(),"limit_price":float(actual.get("limit_price",actual.get("price",0)))}
    checks={key:observed[key]==value for key,value in expected.items()};fill_quantity=sum(float(item.get("quantity",0)) for item in fills);fill_valid=0<=fill_quantity<=expected["quantity"]
    fill_status="OVERFILLED" if not fill_valid else "UNFILLED" if fill_quantity==0 else "FILLED" if abs(fill_quantity-expected["quantity"])<1e-9 else "PARTIALLY_FILLED"
    matched=all(checks.values()) and fill_valid
    return {"status":"MATCHED" if matched else "MISMATCH","field_checks":checks,"fill_quantity":fill_quantity,"fill_status":fill_status,"fill_quantity_valid":fill_valid,"intended_checksum":canonical_checksum(expected),"actual_checksum":canonical_checksum(observed),"requires_human_attention":not matched}
