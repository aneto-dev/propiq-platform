"""
Alembic migration environment.

Configured for SQLAlchemy 2.0 async engine (asyncpg driver).

Key decisions:
- DATABASE_URL is read from app.core.config.Settings, not from alembic.ini.
  Migrations always use the same connection string as the application, driven
  by environment variables. No duplication of credentials.
- target_metadata = Base.metadata enables autogenerate: Alembic compares
  the current database state against registered ORM models and generates
  the necessary ALTER/CREATE/DROP statements.
- At Commit 0.5, Base.metadata has no tables registered. Running
  `alembic upgrade head` applies zero migrations — this is correct.
  Models are added in Commit 3.1.
- NullPool is used for migration runs. Migrations are one-shot operations;
  pooling adds no benefit and can leave connections open after the command
  exits.

Architecture: PERSISTENCE_ARCHITECTURE.md Part 14 — migration philosophy.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all ORM models so their tables are registered with Base.metadata
# before autogenerate inspects it. Without these imports, metadata is empty
# and autogenerate produces no output.
import app.db.models.audit  # noqa: F401
import app.db.models.configuration  # noqa: F401
import app.db.models.deal  # noqa: F401
import app.db.models.investor_profile  # noqa: F401
import app.db.models.property  # noqa: F401
import app.db.models.snapshot  # noqa: F401
import app.db.models.user  # noqa: F401
from alembic import context

# ---------------------------------------------------------------------------
# Application imports
# ---------------------------------------------------------------------------
# Import Base before any model imports so that Base.metadata is populated
# when this file runs. As models are added to app/db/models/ in Commit 3.1,
# they will be imported here (or via a models/__init__.py) to register
# their tables with Base.metadata for autogenerate to detect.
from app.core.config import get_settings
from app.db.base import Base

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to alembic.ini values
# ---------------------------------------------------------------------------
config = context.config

# Apply Python logging configuration from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Target metadata for autogenerate
# ---------------------------------------------------------------------------
# This MetaData is what Alembic compares against the current database state.
# Tables are registered here as ORM models inherit from Base.
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Override sqlalchemy.url with application's DATABASE_URL from environment
# ---------------------------------------------------------------------------
# This ensures migrations always use the same connection string as the app.
# No hardcoded credentials in alembic.ini.
_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.database_url)


# ---------------------------------------------------------------------------
# Offline migrations (generates SQL without connecting)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL without a live database connection. Useful for reviewing
    changes before applying them, or for generating SQL for a DBA.

    Usage: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (connects to the database)
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    """
    Execute migrations using an active synchronous connection.

    Called via run_sync() to bridge the async engine into Alembic's
    synchronous migration API.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Detect column type changes (e.g. VARCHAR → TEXT).
        compare_type=True,
        # Detect server_default changes.
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create a temporary async engine and run migrations via run_sync.

    Uses NullPool — migrations are one-shot operations and do not benefit
    from connection pooling. NullPool also ensures the connection is
    cleanly closed when the migration command exits.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode (default: `alembic upgrade head`).

    Calls run_async_migrations inside asyncio.run() to bridge the async
    engine into Alembic's synchronous entry point.
    """
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
