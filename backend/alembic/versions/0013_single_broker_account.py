"""scope brokerage synchronization to one pseudonymous account"""
from alembic import op
import sqlalchemy as sa
revision="0013_single_broker_account";down_revision="0012_phase9_gateway";branch_labels=None;depends_on=None
def upgrade():op.add_column("broker_connection_config",sa.Column("selected_account_ref",sa.String(32),nullable=True))
def downgrade():op.drop_column("broker_connection_config","selected_account_ref")
