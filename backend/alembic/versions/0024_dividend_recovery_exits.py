"""Persist Aegis-managed Dividend Farm positions and recovery exits."""
from alembic import op
import sqlalchemy as sa
revision="0024_dividend_exits"
down_revision="0023_scheduled_quality"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("dividend_farm_positions",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("entry_execution_id",sa.Integer(),sa.ForeignKey("controlled_execution_records.id",ondelete="RESTRICT"),nullable=False),sa.Column("entry_plan_id",sa.Integer(),sa.ForeignKey("planned_trades.id",ondelete="RESTRICT"),nullable=True),sa.Column("strategy_decision_id",sa.Integer(),sa.ForeignKey("strategy_decisions.id",ondelete="RESTRICT"),nullable=False),sa.Column("symbol",sa.String(32),nullable=False),sa.Column("quantity",sa.Float(),nullable=False),sa.Column("entry_price",sa.Float(),nullable=False),sa.Column("entry_filled_at",sa.DateTime(timezone=True),nullable=False),sa.Column("ex_dividend_date",sa.Date(),nullable=False),sa.Column("exit_target_price",sa.Float(),nullable=False),sa.Column("status",sa.String(24),nullable=False),sa.Column("exit_strategy_decision_id",sa.Integer(),sa.ForeignKey("strategy_decisions.id",ondelete="RESTRICT"),nullable=True),sa.Column("exit_plan_id",sa.Integer(),sa.ForeignKey("planned_trades.id",ondelete="RESTRICT"),nullable=True),sa.Column("last_observed_price",sa.Float(),nullable=True),sa.Column("last_observed_at",sa.DateTime(timezone=True),nullable=True),sa.Column("created_by",sa.String(64),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("entry_execution_id"))
    for col in ("entry_execution_id","entry_plan_id","strategy_decision_id","symbol","ex_dividend_date","status","exit_strategy_decision_id","exit_plan_id"):op.create_index(f"ix_dividend_farm_positions_{col}","dividend_farm_positions",[col])

def downgrade():op.drop_table("dividend_farm_positions")
