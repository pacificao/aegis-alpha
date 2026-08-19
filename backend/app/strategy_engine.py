"""Deterministic, research-only strategy evaluation; emits decisions, never orders."""
from __future__ import annotations
import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def canonical_checksum(value: dict) -> str:
    encoded=json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator=="eq": return actual==expected
    if operator=="ne": return actual!=expected
    if operator=="in": return actual in expected
    if operator=="not_in": return actual not in expected
    if operator=="gt": return float(actual)>float(expected)
    if operator=="gte": return float(actual)>=float(expected)
    if operator=="lt": return float(actual)<float(expected)
    if operator=="lte": return float(actual)<=float(expected)
    raise ValueError("Unsupported deterministic operator")


def _rule_matches(rule: dict, facts: dict) -> tuple[bool,str]:
    field=rule["field"]
    if field not in facts: return False,f"MISSING_{field.upper()}"
    try: matched=_compare(facts[field],rule["operator"],rule["value"])
    except (TypeError,ValueError,OverflowError): return False,f"INVALID_{field.upper()}"
    return matched,rule.get("reason",field).upper()


def evaluate(specification: dict,symbol: str,facts: dict,as_of: datetime|None=None) -> dict:
    symbol=symbol.strip().upper(); universe=specification["universe"]
    allowed=set(universe.get("symbols",[])); excluded=set(universe.get("exclude_symbols",[]))
    if symbol in excluded or (allowed and symbol not in allowed):
        return _result("EXCLUDE",["OUTSIDE_UNIVERSE"],symbol,facts,as_of)
    failures=[]
    for rule in specification["filters"]:
        matched,reason=_rule_matches(rule,facts)
        if not matched: failures.append(f"FILTER_{reason}")
    if failures: return _result("EXCLUDE",failures,symbol,facts,as_of)
    exits=[_rule_matches(rule,facts) for rule in specification["exit_rules"]]
    matched_exits=[reason for matched,reason in exits if matched]
    if matched_exits: return _result("EXIT",matched_exits,symbol,facts,as_of)
    entries=[_rule_matches(rule,facts) for rule in specification["entry_rules"]]
    if entries and all(matched for matched,_ in entries):
        result=_result("ENTRY",[reason for _,reason in entries],symbol,facts,as_of)
        result["proposed_weight_pct"]=specification["position_sizing"]["max_position_pct"]
        return result
    return _result("HOLD",[reason for matched,reason in entries if not matched] or ["NO_RULE_MATCH"],symbol,facts,as_of)


def _result(decision: str,reasons: list[str],symbol: str,facts: dict,as_of: datetime|None) -> dict:
    return {"decision":decision,"symbol":symbol,"as_of":(as_of or datetime.now(UTC)).astimezone(UTC),"reason_codes":reasons,"inputs":facts,"proposed_weight_pct":None,"risk_authorized":False,"executable":False,"trading":"DISABLED"}
