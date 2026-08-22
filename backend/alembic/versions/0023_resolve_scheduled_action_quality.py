"""Resolve scheduled corporate-action timestamp findings."""
from alembic import op

revision = "0023_scheduled_quality"
down_revision = "0022_dividend_full_qualification"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE data_records SET quality_status='VALID'
        WHERE data_type='CORPORATE_ACTION' AND quality_status='REJECTED'
          AND id IN (SELECT record_id FROM data_quality_issues WHERE code='FUTURE_TIMESTAMP')
    """)
    op.execute("""
        UPDATE data_quality_issues
        SET severity='RESOLVED', detail='Scheduled corporate action; future event date is valid.'
        WHERE code='FUTURE_TIMESTAMP' AND severity<>'RESOLVED'
          AND record_id IN (SELECT id FROM data_records WHERE data_type='CORPORATE_ACTION')
    """)


def downgrade():
    pass
