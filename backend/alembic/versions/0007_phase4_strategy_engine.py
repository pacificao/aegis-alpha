"""Add Phase 4 deterministic strategy engine records."""
from alembic import op
import sqlalchemy as sa
revision="0007_phase4_strategy_engine"
down_revision="0006_phase3_data"
branch_labels=None
depends_on=None

def upgrade() -> None:
    op.create_table("strategy_versions",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("scenario_id",sa.Integer(),sa.ForeignKey("strategy_scenarios.id",ondelete="CASCADE"),nullable=False),
        sa.Column("version",sa.Integer(),nullable=False),sa.Column("specification",sa.JSON(),nullable=False),
        sa.Column("checksum",sa.String(64),nullable=False),sa.Column("created_by",sa.String(64),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint("scenario_id","version",name="uq_strategy_version_number"),
        sa.UniqueConstraint("scenario_id","checksum",name="uq_strategy_version_checksum"))
    op.create_index("ix_strategy_versions_scenario_id","strategy_versions",["scenario_id"])
    op.create_index("ix_strategy_versions_checksum","strategy_versions",["checksum"])
    op.create_table("strategy_decisions",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("version_id",sa.Integer(),sa.ForeignKey("strategy_versions.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("symbol",sa.String(32),nullable=False),sa.Column("as_of",sa.DateTime(timezone=True),nullable=False),
        sa.Column("decision",sa.String(12),nullable=False),sa.Column("reason_codes",sa.JSON(),nullable=False),sa.Column("proposed_weight_pct",sa.Float(),nullable=True),
        sa.Column("inputs",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    for column in ("version_id","symbol","as_of","decision"):
        op.create_index(f"ix_strategy_decisions_{column}","strategy_decisions",[column])

def downgrade() -> None:
    op.drop_table("strategy_decisions"); op.drop_table("strategy_versions")
