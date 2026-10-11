"""
db/engine.py

Async SQLAlchemy engine + session factory.

Supports:
  - SQLite  (default): sqlite+aiosqlite:///./gateway.db
  - PostgreSQL:        postgresql+asyncpg://user:pass@host/db

Set DATABASE_URL in your environment to switch drivers.
"""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
_DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./gateway.db",
)
_IS_SQLITE = _DATABASE_URL.startswith("sqlite")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the singleton async engine, creating it on first call."""
    global _engine
    if _engine is None:
        connect_args = {"check_same_thread": False} if _IS_SQLITE else {}

        # NullPool for SQLite — avoids cross-thread issues in async contexts.
        # pool_size / max_overflow are invalid for NullPool so we only pass
        # them for Postgres where the asyncpg driver uses a real pool.
        engine_kwargs: dict = {
            "echo": os.environ.get("DB_ECHO", "false").lower() == "true",
            "connect_args": connect_args,
            "poolclass": NullPool if _IS_SQLITE else None,
        }
        if not _IS_SQLITE:
            engine_kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "10"))
            engine_kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "20"))
            engine_kwargs["pool_pre_ping"] = True

        _engine = create_async_engine(_DATABASE_URL, **engine_kwargs)
        safe_url = _DATABASE_URL.split("@")[-1] if "@" in _DATABASE_URL else _DATABASE_URL
        logger.info("Database engine initialised → %s", safe_url)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the singleton async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager yielding a transactional DB session.

    Commits on clean exit, rolls back on any exception — the caller never
    needs to manage commit/rollback manually.

    Usage::

        async with get_db_session() as session:
            session.add(some_model_instance)
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all ORM-declared tables.  Called once at application startup."""
    from db.models import Base  # local import avoids circular dependency

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All database tables created / verified.")


async def close_db() -> None:
    """Dispose the engine connection pool.  Called on application shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed.")
