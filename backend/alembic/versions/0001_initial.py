"""Initial roadmap and activity tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("phases", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("number", sa.Integer(), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.UniqueConstraint("number"))
    op.create_index("ix_phases_number", "phases", ["number"], unique=True)
    op.create_table("tasks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("phase_id", sa.Integer(), sa.ForeignKey("phases.id", ondelete="CASCADE"), nullable=False), sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("title", sa.Text(), nullable=False), sa.Column("status", sa.Enum("NOT_STARTED", "IN_PROGRESS", "COMPLETE", "BLOCKED", name="taskstatus", native_enum=False), nullable=False), sa.Column("notes", sa.Text(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_tasks_phase_id", "tasks", ["phase_id"])
    op.create_table("development_activity", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("actor", sa.String(64), nullable=False), sa.Column("action", sa.String(80), nullable=False), sa.Column("entity_type", sa.String(40), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=True), sa.Column("detail", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_development_activity_created_at", "development_activity", ["created_at"])


def downgrade():
    op.drop_table("development_activity")
    op.drop_table("tasks")
    op.drop_table("phases")

