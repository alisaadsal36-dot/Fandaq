"""
Async SQLAlchemy engine, session factory, and base model.
"""

import ssl as _ssl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ── SSL handling for cloud databases (Neon, Supabase, etc.) ──
connect_args = {}
if "ssl" in settings.DATABASE_URL or "neon.tech" in settings.DATABASE_URL:
    ssl_context = _ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = _ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

# Remove ssl=require from URL if present (asyncpg handles it via connect_args)
db_url = settings.DATABASE_URL.replace("?ssl=require", "").replace("&ssl=require", "")

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=connect_args,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
