"""
NEXUS Async Database Engine & Session Management
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from packages.config.nexus_config import get_settings
from packages.shared.nexus_shared.logging import get_logger

logger = get_logger("nexus.database")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_sqlite_connection(engine: AsyncEngine) -> None:
    """Enforce WAL mode and 30-second busy timeout for SQLite concurrency."""

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
        finally:
            cursor.close()


def ensure_sqlite_directory(url: str) -> None:
    if "sqlite" in url:
        # Extract file path from sqlite+aiosqlite:///path or sqlite:///path
        for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
            if prefix in url:
                path_part = url.split(prefix, 1)[1]
                if path_part and path_part != ":memory:":
                    os.makedirs(os.path.dirname(os.path.abspath(path_part)), exist_ok=True)
                break


async def init_database() -> AsyncEngine:
    global _engine, _session_factory
    settings = get_settings()

    target_url = os.environ.get("DATABASE_URL", settings.database_url)

    import sys
    is_standalone = os.environ.get("NEXUS_STANDALONE", "0") == "1" or getattr(sys, "frozen", False)
    if is_standalone and "sqlite" not in target_url:
        target_url = settings.sqlite_fallback_url

    # If postgres target, test connection; fallback to SQLite if unreachable
    if "postgres" in target_url:
        test_engine = None
        try:
            test_engine = create_async_engine(
                target_url,
                echo=settings.database_echo,
                pool_pre_ping=True,
            )
            async with test_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            _engine = test_engine
            logger.info("connected_to_postgresql", url=target_url.split("@")[-1])
        except Exception as e:  # noqa: BLE001
            if test_engine:
                await test_engine.dispose()
            logger.warning(
                "postgres_unreachable_falling_back_to_sqlite",
                error=str(e),
                fallback=settings.sqlite_fallback_url,
            )
            ensure_sqlite_directory(settings.sqlite_fallback_url)
            _engine = create_async_engine(
                settings.sqlite_fallback_url,
                echo=settings.database_echo,
            )
            configure_sqlite_connection(_engine)
            async with _engine.begin() as conn:
                from packages.shared.nexus_shared.models import Base
                await conn.run_sync(Base.metadata.create_all)
    else:
        chosen_url = target_url or settings.sqlite_fallback_url
        if "sqlite" in chosen_url:
            ensure_sqlite_directory(chosen_url)
        _engine = create_async_engine(
            chosen_url,
            echo=settings.database_echo,
        )
        if "sqlite" in chosen_url:
            configure_sqlite_connection(_engine)
            async with _engine.begin() as conn:
                from packages.shared.nexus_shared.models import Base
                await conn.run_sync(Base.metadata.create_all)
        logger.info("connected_to_sqlite", url=chosen_url)

    _session_factory = async_sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _session_factory


async def close_database() -> None:
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database_engine_closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        await init_database()
    assert _session_factory is not None

    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_health() -> tuple[bool, str]:
    if _engine is None:
        try:
            await init_database()
        except Exception as e:  # noqa: BLE001
            return False, f"Failed to initialize database: {e}"

    assert _engine is not None
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "healthy"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
