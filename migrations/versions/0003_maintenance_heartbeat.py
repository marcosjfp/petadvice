"""Track successful maintenance so readiness detects a stopped worker."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('maintenancestatus', sa.Column('job', sa.String(), primary_key=True), sa.Column('last_success_at', sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table('maintenancestatus')
