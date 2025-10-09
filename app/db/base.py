"""
Database base models and session management.
"""

import uuid
from datetime import datetime
from typing import Optional, Any, Dict
from sqlmodel import SQLModel, Field, create_engine, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event, text
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class BaseModel(SQLModel):
    """Base model with common fields."""
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        description="Unique identifier"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update timestamp"
    )


class TenantModel(BaseModel):
    """Base model for tenant-scoped entities."""
    
    clinic_id: uuid.UUID = Field(
        foreign_key="clinics.id",
        index=True,
        description="Clinic/tenant identifier"
    )


# Database engine configuration
engine_kwargs = {
    "pool_size": settings.database_pool_size,
    "max_overflow": settings.database_max_overflow,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

# Create async engine
async_engine = create_async_engine(
    settings.database_url,
    **engine_kwargs,
    echo=settings.debug
)

# Create sync engine for migrations
sync_engine = create_engine(
    settings.database_url_sync,
    **engine_kwargs,
    echo=settings.debug
)

# Session makers
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False
)


def get_async_session() -> AsyncSession:
    """Get async database session."""
    return AsyncSessionLocal()


def get_sync_session() -> Session:
    """Get sync database session."""
    return SessionLocal()


# Event listeners removed - SQLModel handles timestamps differently


# Database dependency for FastAPI
async def get_db() -> AsyncSession:
    """Database dependency for FastAPI endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Tenant context management
class TenantContext:
    """Context manager for tenant-scoped database operations."""
    
    def __init__(self, clinic_id: uuid.UUID):
        self.clinic_id = clinic_id
    
    def filter_by_tenant(self, query, model_class):
        """Add tenant filter to query."""
        if hasattr(model_class, 'clinic_id'):
            return query.filter(model_class.clinic_id == self.clinic_id)
        return query
    
    def ensure_tenant(self, instance):
        """Ensure instance belongs to tenant."""
        if hasattr(instance, 'clinic_id'):
            instance.clinic_id = self.clinic_id
        return instance


def get_tenant_context(clinic_id: uuid.UUID) -> TenantContext:
    """Get tenant context for database operations."""
    return TenantContext(clinic_id)


# Database utilities
class DatabaseUtils:
    """Utility functions for database operations."""
    
    @staticmethod
    async def execute_in_transaction(session: AsyncSession, operations):
        """Execute operations within a transaction."""
        async with session.begin():
            try:
                result = await operations(session)
                return result
            except Exception as e:
                await session.rollback()
                raise e
    
    @staticmethod
    def create_idempotency_key() -> str:
        """Create a unique idempotency key."""
        return str(uuid.uuid4())
    
    @staticmethod
    async def check_idempotency(session: AsyncSession, key: str, operation: str) -> Optional[Any]:
        """Check if operation was already performed with given idempotency key."""
        # This would typically query an idempotency_logs table
        # For now, return None (not implemented)
        return None
    
    @staticmethod
    async def log_idempotency(session: AsyncSession, key: str, operation: str, result: Any):
        """Log successful operation with idempotency key."""
        # This would typically insert into an idempotency_logs table
        # For now, no-op (not implemented)
        pass


# Health check utilities
async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and health."""
    try:
        async with AsyncSessionLocal() as session:
            # Simple query to check connectivity
            result = await session.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "database": "connected",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
