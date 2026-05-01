"""
Alembic environment configuration.

This file is executed by Alembic CLI commands (alembic upgrade, alembic revision, etc.).
It sets up the database connection using the app's config and registers all SQLAlchemy
models so Alembic can auto-generate migrations by comparing model definitions with
the current database schema.

We use async mode (run_async_migrations) because our database driver is asyncpg.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import app config to get DATABASE_URL from environment variables
from app.core.config import settings

# Import Base and all models so Alembic can detect changes
from app.db.base import Base
import app.models  # noqa: F401 — registers all models on Base.metadata

# Alembic Config object: gives access to values in alembic.ini
config = context.config

# Override the sqlalchemy.url with the value from our app settings.
# This ensures migrations always use the correct database URL.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up Python logging from alembic.ini config (optional but useful)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata tells Alembic which tables to manage.
# Setting it to Base.metadata enables --autogenerate support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    In offline mode, Alembic generates SQL scripts without connecting to the
    database. Useful for review or applying migrations manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations using a synchronous connection (required by Alembic internals)."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode using an async engine.

    We create a temporary async engine from the config, open a connection,
    and run all pending migrations.
    """
    # Build engine from alembic.ini config (with our URL override applied above)
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool: don't reuse connections during migrations
    )

    async with connectable.connect() as connection:
        # run_sync bridges the async connection to Alembic's sync migration runner
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — runs the async function via asyncio."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
