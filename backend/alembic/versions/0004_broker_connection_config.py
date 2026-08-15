"""Persist non-secret broker MCP connection metadata."""
import sqlalchemy as sa
from alembic import op
revision = "0004_broker_connection_config"
down_revision = "0003_expand_task_status"
branch_labels = None
depends_on = None

def upgrade() -> None:
    table = op.create_table(
        "broker_connection_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("connection_name", sa.String(length=80), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider"),
    )
    op.create_index("ix_broker_connection_config_provider", "broker_connection_config", ["provider"], unique=True)
    op.bulk_insert(table, [{"id": 1, "provider": "robinhood", "connection_name": "Robinhood Agentic", "endpoint": "https://agent.robinhood.com/mcp/trading", "mode": "READ_ONLY"}])

def downgrade() -> None:
    op.drop_index("ix_broker_connection_config_provider", table_name="broker_connection_config")
    op.drop_table("broker_connection_config")
