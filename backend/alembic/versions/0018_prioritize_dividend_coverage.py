"""Prioritize Robinhood fundamentals needed by the dividend calendar."""
from alembic import op

revision="0018_dividend_coverage"
down_revision="0017_scheduled_action_quality"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("UPDATE ingestion_jobs SET priority=4 WHERE provider='robinhood' AND dataset='get_equity_fundamentals' AND status='QUEUED'")

def downgrade():
    op.execute("UPDATE ingestion_jobs SET priority=6 WHERE provider='robinhood' AND dataset='get_equity_fundamentals' AND status='QUEUED' AND priority=4")
