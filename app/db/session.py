"""
Database session management and connection utilities.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.base import AsyncSessionLocal


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self):
        self.session_factory = AsyncSessionLocal
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup."""
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def get_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with transaction management."""
        async with self.session_factory() as session:
            async with session.begin():
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise
    
    async def close(self):
        """Close all database connections."""
        # This would close the engine if needed
        pass


# Global database manager
db_manager = DatabaseManager()


# FastAPI dependency
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with db_manager.get_session() as session:
        yield session


# Transaction dependency
async def get_db_transaction() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database transactions."""
    async with db_manager.get_transaction() as session:
        yield session
