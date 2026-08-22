"""persistent continuous candidate scan state"""
from alembic import op
import sqlalchemy as sa
revision="0020_candidate_scanner";down_revision="0019_planned_trades";branch_labels=None;depends_on=None

def upgrade():
    op.create_table("candidate_scan_states",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("version_id",sa.Integer(),sa.ForeignKey("strategy_versions.id",ondelete="CASCADE"),nullable=False),sa.Column("instrument_id",sa.Integer(),sa.ForeignKey("instruments.id",ondelete="CASCADE"),nullable=False),sa.Column("last_decision_id",sa.Integer(),sa.ForeignKey("strategy_decisions.id",ondelete="SET NULL"),nullable=True),sa.Column("evidence_checksum",sa.String(64),nullable=False,server_default=""),sa.Column("outcome",sa.String(12),nullable=False,server_default="NOT_READY"),sa.Column("detail",sa.String(255),nullable=False,server_default=""),sa.Column("last_scanned_at",sa.DateTime(timezone=True),nullable=False),sa.Column("next_scan_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint("version_id","instrument_id",name="uq_candidate_scan_version_instrument"))
    for column in ("version_id","instrument_id","outcome","last_scanned_at","next_scan_at"):op.create_index(f"ix_candidate_scan_states_{column}","candidate_scan_states",[column])

def downgrade():op.drop_table("candidate_scan_states")
