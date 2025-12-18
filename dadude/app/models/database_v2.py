"""
DaDude v2.0 - Database Engine and Session Management
PostgreSQL async support with connection pooling
"""
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from loguru import logger

from ..config import get_settings
from .database import Base

# Global engine instances
_async_engine = None
_sync_engine = None
_async_session_factory = None
_sync_session_factory = None


def get_async_engine():
    """Get or create async database engine (PostgreSQL)"""
    global _async_engine

    if _async_engine is None:
        settings = get_settings()

        # Use NullPool for SQLite, QueuePool for PostgreSQL
        if settings.is_sqlite:
            pool_class = NullPool
            pool_kwargs = {}
        else:
            pool_class = QueuePool
            pool_kwargs = {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_recycle": settings.db_pool_recycle,
                "pool_pre_ping": True,  # Check connection health
            }

        _async_engine = create_async_engine(
            settings.database_url,
            echo=settings.log_level == "DEBUG",
            poolclass=pool_class,
            **pool_kwargs
        )

        logger.info(f"Async database engine created: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'local'}")

    return _async_engine


def get_sync_engine():
    """Get or create sync database engine (for migrations/tooling)"""
    global _sync_engine

    if _sync_engine is None:
        settings = get_settings()
        sync_url = settings.database_url_sync_computed

        _sync_engine = create_engine(
            sync_url,
            echo=settings.log_level == "DEBUG",
            pool_pre_ping=True,
        )

        logger.info(f"Sync database engine created")

    return _sync_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get async session factory"""
    global _async_session_factory

    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _async_session_factory


def get_sync_session_factory() -> sessionmaker[Session]:
    """Get sync session factory"""
    global _sync_session_factory

    if _sync_session_factory is None:
        engine = get_sync_engine()
        _sync_session_factory = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _sync_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes to get async database session.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_session)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def async_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for async database sessions.

    Usage:
        async with async_session_context() as session:
            result = await session.execute(select(Item))
            items = result.scalars().all()
    """
    factory = get_async_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def get_sync_session() -> Session:
    """
    Get sync database session (for background tasks, migrations).
    Remember to close the session when done.

    Usage:
        session = get_sync_session()
        try:
            items = session.query(Item).all()
        finally:
            session.close()
    """
    factory = get_sync_session_factory()
    return factory()


async def init_async_db():
    """Initialize async database (create tables if not exist)"""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Async database tables initialized")


def init_sync_db():
    """Initialize sync database (create tables if not exist)"""
    engine = get_sync_engine()
    Base.metadata.create_all(engine)
    logger.info("Sync database tables initialized")


async def close_async_engine():
    """Close async database engine (call on shutdown)"""
    global _async_engine, _async_session_factory

    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None
        logger.info("Async database engine closed")


def close_sync_engine():
    """Close sync database engine"""
    global _sync_engine, _sync_session_factory

    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
        _sync_session_factory = None
        logger.info("Sync database engine closed")


# Health check
async def check_database_health() -> dict:
    """Check database connection health"""
    try:
        async with async_session_context() as session:
            # Simple query to test connection
            result = await session.execute("SELECT 1")
            _ = result.scalar()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
