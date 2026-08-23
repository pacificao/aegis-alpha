"""calibrate dividend liquidity and yield rules as immutable version"""
from alembic import op
import hashlib,json
from sqlalchemy import text
revision="0021_dividend_liquidity_yield";down_revision="0020_candidate_scanner";branch_labels=None;depends_on=None
def _checksum(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def upgrade():
 bind=op.get_bind();row=bind.execute(text("SELECT id,parameters FROM strategy_scenarios WHERE name=\x27Dividend Farm\x27")).mappings().first()
 if not row:return
 parameters=dict(row["parameters"] or {});parameters.pop("min_average_daily_volume",None);parameters["min_average_daily_dollar_volume"]=5000000;parameters["event_yield_sensitivity_pct"]=[0.10,0.15,0.25]
 bind.execute(text("UPDATE strategy_scenarios SET parameters=CAST(:parameters AS JSONB) WHERE id=:id"),{"parameters":json.dumps(parameters),"id":row["id"]})
 latest=bind.execute(text("SELECT version,specification FROM strategy_versions WHERE scenario_id=:id ORDER BY version DESC LIMIT 1"),{"id":row["id"]}).mappings().first()
 if not latest:return
 spec=json.loads(json.dumps(latest["specification"]));spec["parameters"]=parameters;spec["filters"]=[{"field":"earnings_excluded","operator":"eq","value":False,"reason":"EARNINGS_WINDOW_CLEAR"},{"field":"average_daily_dollar_volume","operator":"gte","value":5000000,"reason":"DOLLAR_LIQUIDITY_ELIGIBLE"}]
 rules=[rule for rule in spec.get("entry_rules",[]) if rule.get("field")!="annual_yield_pct"];rules.insert(1,{"field":"annual_yield_pct","operator":"gte","value":1.0,"reason":"ANNUAL_YIELD_ELIGIBLE"});spec["entry_rules"]=rules;digest=_checksum(spec)
 exists=bind.execute(text("SELECT id FROM strategy_versions WHERE scenario_id=:id AND checksum=:checksum"),{"id":row["id"],"checksum":digest}).first()
 if not exists:bind.execute(text("INSERT INTO strategy_versions (scenario_id,version,specification,checksum,created_by) VALUES (:id,:version,CAST(:spec AS JSONB),:checksum,\x27system:migration\x27)"),{"id":row["id"],"version":latest["version"]+1,"spec":json.dumps(spec),"checksum":digest})
def downgrade():pass
