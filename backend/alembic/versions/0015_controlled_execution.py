"""controlled execution review and reconciliation ledger"""
from alembic import op
import sqlalchemy as sa
revision="0015_controlled_execution";down_revision="0014_controlled_trial";branch_labels=None;depends_on=None
def upgrade():
    op.create_table("controlled_execution_records",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("intent_id",sa.Integer(),sa.ForeignKey("controlled_trade_intents.id",ondelete="RESTRICT"),nullable=False,unique=True),sa.Column("environment",sa.String(24),nullable=False,server_default="CONTROLLED_LIVE"),sa.Column("status",sa.String(24),nullable=False),sa.Column("intended_snapshot",sa.JSON(),nullable=False),sa.Column("review_snapshot",sa.JSON(),nullable=False),sa.Column("actual_order",sa.JSON(),nullable=False),sa.Column("fills",sa.JSON(),nullable=False),sa.Column("reconciliation",sa.JSON(),nullable=False),sa.Column("review_checksum",sa.String(64),nullable=True),sa.Column("actual_checksum",sa.String(64),nullable=True),sa.Column("created_by",sa.String(64),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    for c in ("intent_id","environment","status","review_checksum","actual_checksum","created_at"):op.create_index(f"ix_controlled_execution_records_{c}","controlled_execution_records",[c])
def downgrade():op.drop_table("controlled_execution_records")
