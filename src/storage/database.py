"""Database connection and session management"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.common.config import get_settings
from src.common.logging import get_logger

logger = get_logger(__name__)

# Base class for all models
Base = declarative_base()

# Database engines (sync and async)
settings = get_settings()

# Convert postgresql:// to postgresql+psycopg2:// for sync engine
sync_database_url = settings.database_url.replace("postgresql://", "postgresql+psycopg2://")
engine = create_engine(sync_database_url, echo=settings.is_development, pool_pre_ping=True)

# Convert postgresql:// to postgresql+asyncpg:// for async engine (for future use)
# For now, we'll use sync engine with psycopg2
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database - create all tables"""
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")


def check_db_connection() -> bool:
    """Check if database connection is healthy"""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
