"""Preserve the guidance, rule explanations and context shown for completed checks."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_triagesession_pet_started_id', 'triagesession', ['pet_id', 'started_at', 'id'])
    op.add_column('triagesession', sa.Column('result_snapshot', sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    op.drop_index('ix_triagesession_pet_started_id', table_name='triagesession')
    with op.batch_alter_table('triagesession') as batch:
        batch.drop_column('result_snapshot')
