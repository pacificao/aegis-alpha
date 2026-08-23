from app.execution.service import reconcile

def test_intended_actual_fill_reconciliation_matches_exact_order():
 intended={"symbol":"SPY","side":"BUY","quantity":0.01,"order_type":"LIMIT","limit_price":500.0}
 actual={"symbol":"SPY","side":"BUY","quantity":0.01,"order_type":"LIMIT","limit_price":500.0}
 result=reconcile(intended,actual,[{"quantity":0.01,"price":499.99}])
 assert result["status"]=="MATCHED" and result["fill_quantity_valid"] is True and result["requires_human_attention"] is False

def test_reconciliation_detects_drift_and_overfill():
 intended={"symbol":"SPY","side":"BUY","quantity":0.01,"order_type":"LIMIT","limit_price":500.0}
 actual={"symbol":"QQQ","side":"BUY","quantity":0.01,"order_type":"LIMIT","limit_price":500.0}
 result=reconcile(intended,actual,[{"quantity":0.02}])
 assert result["status"]=="MISMATCH" and result["field_checks"]["symbol"] is False and result["fill_quantity_valid"] is False and result["requires_human_attention"] is True

def test_partial_fill_is_valid_but_remains_incomplete():
 intended={"symbol":"SPY","side":"BUY","quantity":.01,"order_type":"LIMIT","limit_price":500}
 actual=dict(intended)
 result=reconcile(intended,actual,[{"quantity":.004,"price":499.5}])
 assert result["status"]=="MATCHED" and result["fill_status"]=="PARTIALLY_FILLED"
 assert result["fill_quantity_valid"] is True and result["requires_human_attention"] is False

def test_overfill_is_attention():
 intended={"symbol":"SPY","side":"BUY","quantity":.01,"order_type":"LIMIT","limit_price":500}
 result=reconcile(intended,dict(intended),[{"quantity":.011}])
 assert result["status"]=="MISMATCH" and result["fill_status"]=="OVERFILLED" and result["requires_human_attention"] is True
