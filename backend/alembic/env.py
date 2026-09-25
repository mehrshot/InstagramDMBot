import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core.config import get_settings
from app.models import Base
from app.models.base import UTCDateTime

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = get_settings().database_url


def _render_item(type_, obj, autogen_context):
    # Our UTCDateTime is a plain timezone-aware DateTime in the database; writing it as such
    # keeps migrations free of app imports.
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _configure(connection=None) -> None:
    context.configure(
        connection=connection,
        url=None if connection else database_url,
        target_metadata=target_metadata,
        compare_type=True,
        render_item=_render_item,
        # SQLite can't ALTER most things; batch mode makes local/dev migrations work there too.
        render_as_batch=database_url.startswith("sqlite"),
        literal_binds=connection is None,
    )


def run_migrations_offline() -> None:
    _configure()
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
