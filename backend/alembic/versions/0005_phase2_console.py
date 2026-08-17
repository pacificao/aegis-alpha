"""Add Phase 2 console scenarios and operator preferences."""
from alembic import op
import sqlalchemy as sa

revision = "0005_phase2_console"
down_revision = "0004_broker_connection_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_scenarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("strategy_type", sa.String(length=60), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("lifecycle", sa.String(length=20), nullable=False, server_default="RESEARCH"),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("lifecycle IN ('RESEARCH', 'PAUSED')", name="ck_scenario_phase2_lifecycle"),
    )
    op.create_table(
        "operator_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("compact_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("page_size", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("confirm_sensitive_actions", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("page_size BETWEEN 10 AND 100", name="ck_operator_page_size"),
    )


def downgrade() -> None:
    op.drop_table("operator_preferences")
    op.drop_table("strategy_scenarios")
