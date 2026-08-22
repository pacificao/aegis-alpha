"""fully wire Dividend Farm qualification as immutable version"""
from alembic import op
import hashlib,json
from sqlalchemy import text
revision="0022_dividend_full_qualification";down_revision="0021_dividend_liquidity_yield";branch_labels=None;depends_on=None
def _checksum(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def upgrade():
 bind=op.get_bind();row=bind.execute(text("SELECT id,parameters FROM strategy_scenarios WHERE name=\x27Dividend Farm\x27")).mappings().first()
 if not row:return
 latest=bind.execute(text("SELECT version,specification FROM strategy_versions WHERE scenario_id=:id ORDER BY version DESC LIMIT 1"),{"id":row["id"]}).mappings().first()
 if not latest:return
 p=dict(row["parameters"] or {});spec=json.loads(json.dumps(latest["specification"]));spec["parameters"]=p;spec["universe"]["asset_types"]=["EQUITY"]+(["ETF"] if p.get("include_etfs") else [])+(["REIT"] if p.get("include_reits") else [])
 spec["entry_rules"]=[{"field":"event_yield_pct","operator":"gte","value":p.get("min_dividend_event_pct",0.15),"reason":"EVENT_YIELD_MINIMUM"},{"field":"annual_yield_pct","operator":"gte","value":p.get("min_annual_yield_pct",1.0),"reason":"ANNUAL_YIELD_MINIMUM"},{"field":"annual_yield_pct","operator":"lte","value":p.get("max_annual_yield_pct",12.0),"reason":"ANNUAL_YIELD_MAXIMUM"},{"field":"recovery_probability_pct","operator":"gte","value":p.get("min_recovery_probability_pct",80.0),"reason":"RECOVERY_PROBABILITY_MINIMUM"}]
 spec["filters"]=[{"field":"earnings_excluded","operator":"eq","value":False,"reason":"EARNINGS_WINDOW_CLEAR"},{"field":"average_daily_dollar_volume","operator":"gte","value":p.get("min_average_daily_dollar_volume",5000000),"reason":"DOLLAR_LIQUIDITY_MINIMUM"},{"field":"recovery_observations","operator":"gte","value":p.get("min_historical_events",12),"reason":"RECOVERY_OBSERVATIONS_MINIMUM"},{"field":"estimated_recovery_days","operator":"lte","value":p.get("max_median_recovery_days",30),"reason":"MEDIAN_RECOVERY_MAXIMUM"},{"field":"recovery_p90_days","operator":"lte","value":p.get("max_p90_recovery_days",90),"reason":"P90_RECOVERY_MAXIMUM"},{"field":"maximum_historical_drawdown_pct","operator":"lte","value":p.get("max_historical_drawdown_pct",15),"reason":"HISTORICAL_DRAWDOWN_MAXIMUM"},{"field":"dividend_history_years","operator":"gte","value":p.get("min_dividend_history_years",5),"reason":"DIVIDEND_HISTORY_MINIMUM"},{"field":"payment_frequency","operator":"in","value":[str(x).upper() for x in p.get("payment_frequencies",[])],"reason":"PAYMENT_FREQUENCY_ALLOWED"},{"field":"special_dividend","operator":"eq","value":bool(p.get("include_special_dividends",False)),"reason":"SPECIAL_DIVIDEND_POLICY"},{"field":"market_cap","operator":"gte","value":float(p.get("min_market_cap_millions",1000))*1000000,"reason":"MARKET_CAP_MINIMUM"}]
 if p.get("include_special_dividends"):spec["filters"]=[rule for rule in spec["filters"] if rule["field"]!="special_dividend"]
 digest=_checksum(spec);exists=bind.execute(text("SELECT id FROM strategy_versions WHERE scenario_id=:id AND checksum=:checksum"),{"id":row["id"],"checksum":digest}).first()
 if not exists:bind.execute(text("INSERT INTO strategy_versions (scenario_id,version,specification,checksum,created_by) VALUES (:id,:version,CAST(:spec AS JSONB),:checksum,\x27system:migration\x27)"),{"id":row["id"],"version":latest["version"]+1,"spec":json.dumps(spec),"checksum":digest})
def downgrade():pass
