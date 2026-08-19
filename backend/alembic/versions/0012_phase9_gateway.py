"""phase9 read-only broker synchronization"""
from alembic import op
import sqlalchemy as sa
revision="0012_phase9_gateway";down_revision="0011_phase8_simulator";branch_labels=None;depends_on=None
def upgrade():
    op.create_table("broker_snapshots",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("provider",sa.String(40),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("account_count",sa.Integer(),nullable=False),sa.Column("account_refs",sa.JSON(),nullable=False),sa.Column("balances",sa.JSON(),nullable=False),sa.Column("holdings",sa.JSON(),nullable=False),sa.Column("orders",sa.JSON(),nullable=False),sa.Column("fills",sa.JSON(),nullable=False),sa.Column("reconciliation",sa.JSON(),nullable=False),sa.Column("checksum",sa.String(64),nullable=False,unique=True),sa.Column("source_observed_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_by",sa.String(64),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for c in ("provider","status","checksum","source_observed_at","created_at"):op.create_index(f"ix_broker_snapshots_{c}","broker_snapshots",[c])
    op.create_table("broker_sync_runs",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("provider",sa.String(40),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("attempts",sa.Integer(),nullable=False),sa.Column("snapshot_id",sa.Integer(),sa.ForeignKey("broker_snapshots.id",ondelete="RESTRICT"),nullable=True),sa.Column("error_code",sa.String(60),nullable=False),sa.Column("detail",sa.Text(),nullable=False),sa.Column("started_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True),nullable=True))
    for c in ("provider","status","snapshot_id","started_at"):op.create_index(f"ix_broker_sync_runs_{c}","broker_sync_runs",[c])
def downgrade():op.drop_table("broker_sync_runs");op.drop_table("broker_snapshots")
