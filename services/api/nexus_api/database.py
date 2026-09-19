"""
NEXUS Async Database Engine & Session Management
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
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


async def init_database() -> AsyncEngine:
    global _engine, _session_factory
    settings = get_settings()

    target_url = os.environ.get("DATABASE_URL", settings.database_url)

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
            os.makedirs(".nexus", exist_ok=True)
            _engine = create_async_engine(
                settings.sqlite_fallback_url,
                echo=settings.database_echo,
            )
    else:
        os.makedirs(".nexus", exist_ok=True)
        _engine = create_async_engine(
            target_url or settings.sqlite_fallback_url,
            echo=settings.database_echo,
        )
        logger.info("connected_to_sqlite", url=settings.sqlite_fallback_url)

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
