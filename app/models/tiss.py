"""
Database models for TISS Multi-Convênio system.
"""

from sqlmodel import SQLModel, Field, Relationship, Column
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum
import uuid

class TISSProviderStatus(str, Enum):
    """TISS Provider status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TESTING = "testing"

class TISSJobStatus(str, Enum):
    """TISS Job status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"
    MANUAL_REVIEW = "manual_review"

class TISSJobType(str, Enum):
    """TISS Job type enumeration."""
    INVOICE = "invoice"
    SADT = "sadt"
    CONSULTATION = "consultation"
    PROCEDURE = "procedure"

class TISSLogLevel(str, Enum):
    """TISS Log level enumeration."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"

class TISSEthicalLockType(str, Enum):
    """TISS Ethical lock type enumeration."""
    DUPLICATE_INVOICE = "duplicate_invoice"
    CID_COLLISION = "cid_collision"
    PROCEDURE_COLLISION = "procedure_collision"
    PATIENT_COLLISION = "patient_collision"

class TISSProvider(SQLModel, table=True):
    """TISS Provider configuration model."""
    
    __tablename__ = "tiss_providers"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Provider identification
    name: str = Field(description="Provider name")
    code: str = Field(description="Provider code")
    cnpj: str = Field(description="Provider CNPJ")
    
    # Connection configuration
    endpoint_url: str = Field(description="TISS endpoint URL")
    environment: str = Field(default="production", description="Environment (production, homologation)")
    
    # Authentication
    username: str = Field(description="TISS username")
    password_encrypted: str = Field(description="Encrypted password")
    certificate_path: Optional[str] = Field(default=None, description="Certificate file path")
    
    # Configuration
    timeout_seconds: int = Field(default=30, description="Request timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=60, description="Retry delay in seconds")
    
    # Status and testing
    status: TISSProviderStatus = Field(default=TISSProviderStatus.INACTIVE)
    last_test_result: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    last_tested_at: Optional[datetime] = Field(default=None)
    last_successful_request: Optional[datetime] = Field(default=None)
    
    # Metadata
    config_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    notes: Optional[str] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    jobs: List["TISSJob"] = Relationship(back_populates="provider")
    logs: List["TISSLog"] = Relationship(back_populates="provider")

class TISSJob(SQLModel, table=True):
    """TISS Job model for processing invoices/procedures."""
    
    __tablename__ = "tiss_jobs"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    provider_id: uuid.UUID = Field(foreign_key="tiss_providers.id", index=True)
    
    # Job identification
    job_type: TISSJobType = Field(description="Type of TISS job")
    invoice_id: Optional[uuid.UUID] = Field(foreign_key="invoices.id", default=None, index=True)
    procedure_code: Optional[str] = Field(default=None, description="TUSS procedure code")
    
    # Job data
    payload: Dict[str, Any] = Field(sa_column=Column(JSONB))
    response_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    
    # Status and processing
    status: TISSJobStatus = Field(default=TISSJobStatus.PENDING)
    attempts: int = Field(default=0, description="Number of processing attempts")
    max_attempts: int = Field(default=3, description="Maximum attempts allowed")
    
    # Scheduling
    scheduled_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    
    # Error handling
    last_error: Optional[str] = Field(default=None)
    last_error_at: Optional[datetime] = Field(default=None)
    next_retry_at: Optional[datetime] = Field(default=None)
    
    # Ethical locks
    ethical_lock_type: Optional[TISSEthicalLockType] = Field(default=None)
    ethical_lock_reason: Optional[str] = Field(default=None)
    manual_review_required: bool = Field(default=False)
    
    # Metadata
    job_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    priority: int = Field(default=0, description="Job priority (higher = more priority)")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    provider: Optional["TISSProvider"] = Relationship(back_populates="jobs")
    invoice: Optional["Invoice"] = Relationship()
    logs: List["TISSLog"] = Relationship(back_populates="job")

class TISSLog(SQLModel, table=True):
    """TISS Log model for tracking all TISS operations."""
    
    __tablename__ = "tiss_logs"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    provider_id: Optional[uuid.UUID] = Field(foreign_key="tiss_providers.id", default=None, index=True)
    job_id: Optional[uuid.UUID] = Field(foreign_key="tiss_jobs.id", default=None, index=True)
    
    # Log details
    level: TISSLogLevel = Field(description="Log level")
    message: str = Field(description="Log message")
    details: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    
    # Request/Response data
    request_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    response_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    response_status_code: Optional[int] = Field(default=None)
    response_time_ms: Optional[int] = Field(default=None)
    
    # Context
    operation: str = Field(description="Operation performed")
    user_id: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None)
    ip_address: Optional[str] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    provider: Optional["TISSProvider"] = Relationship(back_populates="logs")
    job: Optional["TISSJob"] = Relationship(back_populates="logs")
    user: Optional["User"] = Relationship()

class TISSEthicalLock(SQLModel, table=True):
    """TISS Ethical Lock model for preventing duplicate submissions."""
    
    __tablename__ = "tiss_ethical_locks"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Lock identification
    lock_type: TISSEthicalLockType = Field(description="Type of ethical lock")
    invoice_id: Optional[uuid.UUID] = Field(foreign_key="invoices.id", default=None, index=True)
    procedure_code: Optional[str] = Field(default=None, description="TUSS procedure code")
    patient_id: Optional[uuid.UUID] = Field(foreign_key="patients.id", default=None, index=True)
    
    # Lock details
    reason: str = Field(description="Reason for the lock")
    conflicting_job_id: Optional[uuid.UUID] = Field(foreign_key="tiss_jobs.id", default=None)
    manual_review_required: bool = Field(default=True)
    
    # Resolution
    resolved: bool = Field(default=False)
    resolved_at: Optional[datetime] = Field(default=None)
    resolved_by: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None)
    resolution_notes: Optional[str] = Field(default=None)
    
    # Metadata
    lock_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    invoice: Optional["Invoice"] = Relationship()
    patient: Optional["Patient"] = Relationship()
    conflicting_job: Optional["TISSJob"] = Relationship()
    resolved_by_user: Optional["User"] = Relationship()

# Pydantic schemas for API
class TISSProviderCreateRequest(SQLModel):
    """Request schema for creating TISS provider."""
    name: str = Field(description="Provider name")
    code: str = Field(description="Provider code")
    cnpj: str = Field(description="Provider CNPJ")
    endpoint_url: str = Field(description="TISS endpoint URL")
    environment: str = Field(default="production", description="Environment")
    username: str = Field(description="TISS username")
    password: str = Field(description="TISS password")
    certificate_path: Optional[str] = Field(default=None, description="Certificate path")
    timeout_seconds: int = Field(default=30, description="Request timeout")
    max_retries: int = Field(default=3, description="Maximum retries")
    retry_delay_seconds: int = Field(default=60, description="Retry delay")
    config_meta: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

class TISSProviderResponse(SQLModel):
    """Response schema for TISS provider."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    name: str
    code: str
    cnpj: str
    endpoint_url: str
    environment: str
    username: str
    password_encrypted: str  # Masked in actual response
    certificate_path: Optional[str] = None
    timeout_seconds: int
    max_retries: int
    retry_delay_seconds: int
    status: TISSProviderStatus
    last_test_result: Optional[Dict[str, Any]] = None
    last_tested_at: Optional[datetime] = None
    last_successful_request: Optional[datetime] = None
    config_meta: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class TISSJobCreateRequest(SQLModel):
    """Request schema for creating TISS job."""
    provider_id: uuid.UUID = Field(description="TISS provider ID")
    job_type: TISSJobType = Field(description="Job type")
    invoice_id: Optional[uuid.UUID] = Field(default=None, description="Invoice ID")
    procedure_code: Optional[str] = Field(default=None, description="Procedure code")
    payload: Dict[str, Any] = Field(description="Job payload")
    priority: int = Field(default=0, description="Job priority")
    job_meta: Optional[Dict[str, Any]] = None

class TISSJobResponse(SQLModel):
    """Response schema for TISS job."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    provider_id: uuid.UUID
    job_type: TISSJobType
    invoice_id: Optional[uuid.UUID] = None
    procedure_code: Optional[str] = None
    payload: Dict[str, Any]
    response_data: Optional[Dict[str, Any]] = None
    status: TISSJobStatus
    attempts: int
    max_attempts: int
    scheduled_at: datetime
    processed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    ethical_lock_type: Optional[TISSEthicalLockType] = None
    ethical_lock_reason: Optional[str] = None
    manual_review_required: bool
    job_meta: Optional[Dict[str, Any]] = None
    priority: int
    created_at: datetime
    updated_at: datetime

class TISSLogResponse(SQLModel):
    """Response schema for TISS log."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    provider_id: Optional[uuid.UUID] = None
    job_id: Optional[uuid.UUID] = None
    level: TISSLogLevel
    message: str
    details: Optional[Dict[str, Any]] = None
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    response_status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    operation: str
    user_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    created_at: datetime

class TISSTestConnectionRequest(SQLModel):
    """Request schema for testing TISS provider connection."""
    username: Optional[str] = Field(default=None, description="Override username")
    password: Optional[str] = Field(default=None, description="Override password")
    endpoint_url: Optional[str] = Field(default=None, description="Override endpoint")

class TISSTestConnectionResponse(SQLModel):
    """Response schema for TISS provider connection test."""
    success: bool
    message: str
    response_time_ms: Optional[int] = None
    status_code: Optional[int] = None
    response_data: Optional[Dict[str, Any]] = None
    tested_at: datetime = Field(default_factory=datetime.utcnow)

class TISSEthicalLockResponse(SQLModel):
    """Response schema for TISS ethical lock."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    lock_type: TISSEthicalLockType
    invoice_id: Optional[uuid.UUID] = None
    procedure_code: Optional[str] = None
    patient_id: Optional[uuid.UUID] = None
    reason: str
    conflicting_job_id: Optional[uuid.UUID] = None
    manual_review_required: bool
    resolved: bool
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[uuid.UUID] = None
    resolution_notes: Optional[str] = None
    lock_meta: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

# Validation and utility classes
class TISSEthicalLockChecker:
    """Utility class for checking ethical locks."""
    
    @staticmethod
    def check_duplicate_invoice(clinic_id: uuid.UUID, invoice_id: uuid.UUID) -> Optional[str]:
        """Check for duplicate invoice submission."""
        # This would be implemented in the service layer
        return None
    
    @staticmethod
    def check_cid_collision(clinic_id: uuid.UUID, patient_id: uuid.UUID, procedure_code: str) -> Optional[str]:
        """Check for CID collision (same patient, same procedure)."""
        # This would be implemented in the service layer
        return None
    
    @staticmethod
    def check_procedure_collision(clinic_id: uuid.UUID, procedure_code: str, date_range: tuple) -> Optional[str]:
        """Check for procedure collision within date range."""
        # This would be implemented in the service layer
        return None

class TISSJobScheduler:
    """Utility class for scheduling TISS jobs."""
    
    @staticmethod
    def calculate_next_retry(attempt: int, base_delay: int = 60) -> datetime:
        """Calculate next retry time with exponential backoff."""
        import math
        delay_seconds = base_delay * (2 ** attempt)
        return datetime.utcnow() + timedelta(seconds=delay_seconds)
    
    @staticmethod
    def should_retry(attempt: int, max_attempts: int) -> bool:
        """Check if job should be retried."""
        return attempt < max_attempts
