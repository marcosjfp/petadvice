"""Align PostgreSQL timestamp storage with SQLModel's aware UTC datetime fields."""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

TIMESTAMPS = {
    'owner': ('consent_given_at', 'email_verified_at', 'created_at'),
    'triagesession': ('started_at',),
    'authsession': ('created_at', 'expires_at', 'authenticated_at', 'revoked_at'),
    'accountaction': ('created_at', 'expires_at', 'used_at'),
    'emaildelivery': ('created_at', 'next_attempt_at', 'expires_at'),
    'guestaccess': ('expires_at',),
    'maintenancestatus': ('last_success_at',),
}


def change_timezone(aware: bool):
    if op.get_bind().dialect.name != 'postgresql':
        return  # SQLite stores UTC values without a native timezone type.
    for table, columns in TIMESTAMPS.items():
        for column in columns:
            op.alter_column(table, column,
                            existing_type=sa.DateTime(timezone=not aware),
                            type_=sa.DateTime(timezone=aware),
                            postgresql_using=f'"{column}" AT TIME ZONE \'UTC\'')


def upgrade():
    change_timezone(True)


def downgrade():
    change_timezone(False)
