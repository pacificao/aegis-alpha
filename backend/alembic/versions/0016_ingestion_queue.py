"""persistent quota-aware ingestion queue"""
from alembic import op
import sqlalchemy as sa
revision="0016_ingestion_queue";down_revision="0015_controlled_execution";branch_labels=None;depends_on=None
def upgrade():
    op.create_table("ingestion_jobs",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("provider",sa.String(60),nullable=False),sa.Column("dataset",sa.String(60),nullable=False),sa.Column("symbol",sa.String(32),nullable=True),sa.Column("arguments",sa.JSON(),nullable=False,server_default="{}"),sa.Column("priority",sa.Integer(),nullable=False,server_default="100"),sa.Column("status",sa.String(20),nullable=False,server_default="QUEUED"),sa.Column("available_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("attempts",sa.Integer(),nullable=False,server_default="0"),sa.Column("max_attempts",sa.Integer(),nullable=False,server_default="8"),sa.Column("dedupe_key",sa.String(255),nullable=False,unique=True),sa.Column("detail",sa.Text(),nullable=False,server_default=""),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("started_at",sa.DateTime(timezone=True),nullable=True),sa.Column("completed_at",sa.DateTime(timezone=True),nullable=True))
    for c in ("provider","dataset","symbol","priority","status","available_at","dedupe_key"):op.create_index(f"ix_ingestion_jobs_{c}","ingestion_jobs",[c])
def downgrade():op.drop_table("ingestion_jobs")
