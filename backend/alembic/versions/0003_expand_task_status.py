"""Expand roadmap status storage for WAITING_FOR_CREDENTIALS."""
import sqlalchemy as sa
from alembic import op
revision = "0003_expand_task_status"
down_revision = "0002_waiting_for_credentials"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.alter_column("tasks", "status", existing_type=sa.String(length=11), type_=sa.String(length=32), existing_nullable=False)

def downgrade() -> None:
    op.execute("UPDATE tasks SET status='BLOCKED' WHERE status='WAITING_FOR_CREDENTIALS'")
    op.alter_column("tasks", "status", existing_type=sa.String(length=32), type_=sa.String(length=11), existing_nullable=False)
