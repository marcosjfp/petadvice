"""Durable sessions, one-use account actions, encrypted mail outbox and guest expiry."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('owner', sa.Column('consent_policy_version', sa.String()))
    op.add_column('owner', sa.Column('email_verified_at', sa.DateTime()))
    op.create_table('authsession', sa.Column('id', sa.String(), primary_key=True), sa.Column('owner_id', sa.String(), sa.ForeignKey('owner.id'), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('expires_at', sa.DateTime(), nullable=False), sa.Column('authenticated_at', sa.DateTime(), nullable=False), sa.Column('revoked_at', sa.DateTime()))
    op.create_table('accountaction', sa.Column('token_hash', sa.String(), primary_key=True), sa.Column('owner_id', sa.String(), sa.ForeignKey('owner.id'), nullable=False), sa.Column('kind', sa.String(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('expires_at', sa.DateTime(), nullable=False), sa.Column('used_at', sa.DateTime()))
    op.create_table('emaildelivery', sa.Column('id', sa.String(), primary_key=True), sa.Column('owner_id', sa.String(), sa.ForeignKey('owner.id'), nullable=False), sa.Column('encrypted_payload', sa.String(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('next_attempt_at', sa.DateTime(), nullable=False), sa.Column('expires_at', sa.DateTime(), nullable=False), sa.Column('attempts', sa.Integer(), nullable=False))
    op.create_table('guestaccess', sa.Column('session_id', sa.String(), sa.ForeignKey('triagesession.id'), primary_key=True), sa.Column('token_hash', sa.String(), nullable=False), sa.Column('expires_at', sa.DateTime(), nullable=False))
    for table in ['authsession', 'accountaction', 'emaildelivery']:
        op.create_index(f'ix_{table}_owner_id', table, ['owner_id'])
    for table in ['authsession', 'accountaction', 'guestaccess']:
        op.create_index(f'ix_{table}_expires_at', table, ['expires_at'])


def downgrade():
    for table in ['guestaccess', 'emaildelivery', 'accountaction', 'authsession']:
        op.drop_table(table)
    with op.batch_alter_table('owner') as batch:
        batch.drop_column('email_verified_at')
        batch.drop_column('consent_policy_version')
