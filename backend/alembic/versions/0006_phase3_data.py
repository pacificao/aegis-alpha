"""Add Phase 3 trusted data foundation."""
from alembic import op
import sqlalchemy as sa

revision = "0006_phase3_data"
down_revision = "0005_phase2_console"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("data_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
        sa.Column("provider_type", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("credential_status", sa.String(30), nullable=False, server_default="NOT_REQUIRED"),
        sa.Column("base_url", sa.String(255), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_data_providers_name", "data_providers", ["name"], unique=True)
    op.create_table("instruments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("asset_type", sa.String(30), nullable=False, server_default="EQUITY"),
        sa.Column("exchange", sa.String(30), nullable=False, server_default=""),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("cik", sa.String(10), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=False))
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"], unique=True)
    op.create_index("ix_instruments_cik", "instruments", ["cik"])
    op.create_table("data_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("data_type", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval", sa.String(20), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("quality_status", sa.String(20), nullable=False, server_default="VALID"),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.UniqueConstraint("provider_id", "data_type", "checksum", name="uq_data_record_provider_type_checksum"))
    for column in ("provider_id","instrument_id","data_type","event_time","ingested_at","checksum"):
        op.create_index(f"ix_data_records_{column}", "data_records", [column])
    op.create_table("ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dataset", sa.String(40), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""))
    op.create_index("ix_ingestion_runs_provider_id", "ingestion_runs", ["provider_id"])
    op.create_index("ix_ingestion_runs_dataset", "ingestion_runs", ["dataset"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_table("data_quality_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("data_records.id", ondelete="CASCADE"), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False), sa.Column("code", sa.String(60), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    for column in ("record_id","severity","code","created_at"):
        op.create_index(f"ix_data_quality_issues_{column}", "data_quality_issues", [column])

def downgrade() -> None:
    op.drop_table("data_quality_issues")
    op.drop_table("ingestion_runs")
    op.drop_table("data_records")
    op.drop_table("instruments")
    op.drop_table("data_providers")
