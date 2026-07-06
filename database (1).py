"""
Database connection, session management, and initialization.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def get_engine(database_url: str):
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_factory(database_url: str):
    global _session_factory
    if _session_factory is None:
        engine = get_engine(database_url)
        _session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def init_db(database_url: str):
    """Create all tables."""
    from db.models import Base as ModelsBase
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(ModelsBase.metadata.create_all)
    logger.info("Database tables created successfully")


async def get_db_session(database_url: str):
    """Async context manager for DB sessions."""
    factory = get_session_factory(database_url)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
