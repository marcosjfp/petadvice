from alembic import context
from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import NullPool

from app.db import normalize_database_url
from app.settings import get_settings
from app.models import schema  # noqa: F401

config = context.config
url = normalize_database_url(get_settings().database_url)

if context.is_offline_mode():
    context.configure(url=url, target_metadata=SQLModel.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = config.attributes.get('connection')
    engine = None if supplied is not None else create_engine(url, poolclass=NullPool)
    connection = supplied if supplied is not None else engine.connect()
    try:
        context.configure(connection=connection, target_metadata=SQLModel.metadata,
                          render_as_batch=connection.dialect.name == 'sqlite', compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if supplied is None:
            connection.close()
            engine.dispose()
