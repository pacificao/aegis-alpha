"""Add short-lived operator authorization for governed live execution."""
from alembic import op
import sqlalchemy as sa

revision="0026_live_authorization"
down_revision="0025_dividend_allocation"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("live_trading_authorizations",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("max_order_notional",sa.Float(),nullable=False,server_default="1"),
        sa.Column("authorized_by",sa.String(64),nullable=False),
        sa.Column("reason",sa.Text(),nullable=False),
        sa.Column("authorized_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("expires_at",sa.DateTime(timezone=True),nullable=True,index=True),
        sa.Column("authorization_checksum",sa.String(64),nullable=True,unique=True),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
    )
    op.execute("INSERT INTO live_trading_authorizations (id,enabled,max_order_notional,authorized_by,reason) VALUES (1,false,1,'system:migration','Live trading remains disabled pending operator authorization')")

def downgrade():
    op.drop_table("live_trading_authorizations")
