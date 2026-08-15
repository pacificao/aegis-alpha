"""Add explicit credential-waiting roadmap status."""
from alembic import op
revision = "0002_waiting_for_credentials"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    op.execute("UPDATE tasks SET status='BLOCKED' WHERE status='WAITING_FOR_CREDENTIALS'")
