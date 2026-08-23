"""Allow Dividend Farm to allocate up to all available capital."""
from alembic import op
from sqlalchemy import text
import hashlib,json
revision="0025_dividend_allocation"
down_revision="0024_dividend_exits"
branch_labels=None
depends_on=None

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def upgrade():
    bind=op.get_bind();scenario=bind.execute(text("SELECT id,parameters FROM strategy_scenarios WHERE name='Dividend Farm'")).mappings().first()
    if scenario:
        params=dict(scenario["parameters"] or {});params["max_allocation_pct"]=100.0
        bind.execute(text("UPDATE strategy_scenarios SET parameters=CAST(:params AS JSONB),updated_at=now() WHERE id=:id"),{"params":json.dumps(params),"id":scenario["id"]})
        latest=bind.execute(text("SELECT version,specification FROM strategy_versions WHERE scenario_id=:id ORDER BY version DESC LIMIT 1"),{"id":scenario["id"]}).mappings().first()
        if latest:
            spec=json.loads(json.dumps(latest["specification"]));spec.setdefault("parameters",{})["max_allocation_pct"]=100.0;spec.setdefault("position_sizing",{})["max_strategy_allocation_pct"]=100.0;spec["position_sizing"]["cash_buffer_pct"]=0.0
            checksum=digest(spec)
            if not bind.execute(text("SELECT 1 FROM strategy_versions WHERE scenario_id=:id AND checksum=:checksum"),{"id":scenario["id"],"checksum":checksum}).first():
                bind.execute(text("INSERT INTO strategy_versions (scenario_id,version,specification,checksum,created_by) VALUES (:id,:version,CAST(:spec AS JSONB),:checksum,'system:migration')"),{"id":scenario["id"],"version":latest["version"]+1,"spec":json.dumps(spec),"checksum":checksum})
    policy=bind.execute(text("SELECT version,configuration FROM risk_policies WHERE active=true ORDER BY version DESC LIMIT 1")).mappings().first()
    if policy:
        config=dict(policy["configuration"] or {});config["max_portfolio_exposure_pct"]=100.0;config["max_buying_power_use_pct"]=100.0;checksum=digest(config)
        bind.execute(text("UPDATE risk_policies SET active=false WHERE active=true"))
        existing=bind.execute(text("SELECT id FROM risk_policies WHERE checksum=:checksum"),{"checksum":checksum}).first()
        if existing:bind.execute(text("UPDATE risk_policies SET active=true WHERE id=:id"),{"id":existing[0]})
        else:bind.execute(text("INSERT INTO risk_policies (version,name,configuration,checksum,active,created_by) VALUES (:version,'Full-capital diversified policy',CAST(:config AS JSONB),:checksum,true,'system:migration')"),{"version":policy["version"]+1,"config":json.dumps(config),"checksum":checksum})

def downgrade():pass
