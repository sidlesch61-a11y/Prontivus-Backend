"""
Enhanced database models for missing/incomplete tables.
These extend the existing schema with additional requirements.
"""
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON, Index, text
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid


class PrescriptionType(str, Enum):
    """Prescription type enumeration."""
    SIMPLE = "simple"
    ANTIMICROBIAL = "antimicrobial"
    CONTROLLED_C1 = "controlled_c1"


class DigitalPrescription(SQLModel, table=True):
    """Enhanced prescription model with digital signature support."""
    
    __tablename__ = "digital_prescriptions"
    __table_args__ = (
        Index('idx_digital_prescriptions_clinic', 'clinic_id'),
        Index('idx_digital_prescriptions_patient', 'patient_id'),
        Index('idx_digital_prescriptions_doctor', 'doctor_id'),
        Index('idx_digital_prescriptions_created', 'created_at'),
        {'extend_existing': True}
    )
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patients.id", index=True)
    doctor_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    emr_id: Optional[uuid.UUID] = Field(foreign_key="medical_records.id", default=None)
    
    # Prescription details
    prescription_type: PrescriptionType = Field(default=PrescriptionType.SIMPLE)
    medications: List[Dict[str, Any]] = Field(sa_column=Column(JSON))
    notes: Optional[str] = None
    
    # Digital signature fields
    pdf_url: Optional[str] = None
    pdf_path: Optional[str] = None
    signed_hash: Optional[str] = Field(description="SHA-256 signature hash")
    signature_timestamp: Optional[datetime] = None
    signature_certificate_id: Optional[str] = None
    
    # QR Code verification
    qr_code_url: Optional[str] = None
    qr_code_data: Optional[str] = None
    verification_code: Optional[str] = Field(unique=True, description="Public verification code")
    
    # Compliance tracking
    signed_at: Optional[datetime] = None
    compliance_flags: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Audit
    viewed_by: Optional[List[Dict[str, Any]]] = Field(default_factory=list, sa_column=Column(JSON))
    viewed_count: int = Field(default=0)
    last_viewed_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Soft delete
    deleted_at: Optional[datetime] = None
    is_deleted: bool = Field(default=False)


class HealthPlanIntegration(SQLModel, table=True):
    """Health plan OAuth2 integration model."""
    
    __tablename__ = "health_plan_integrations"
    __table_args__ = (
        Index('idx_health_plans_clinic', 'clinic_id'),
        Index('idx_health_plans_status', 'status'),
        {'extend_existing': True}
    )
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Provider information
    provider_name: str = Field(description="Health plan provider name")
    provider_code: str = Field(description="Provider code/identifier")
    
    # OAuth2 configuration
    base_url: str = Field(description="API base URL")
    client_id: str = Field(description="OAuth2 client ID")
    client_secret_encrypted: str = Field(description="Encrypted OAuth2 client secret")
    scope: Optional[str] = Field(default=None, description="OAuth2 scopes")
    
    # Token management
    access_token_encrypted: Optional[str] = Field(default=None, description="Encrypted access token")
    refresh_token_encrypted: Optional[str] = Field(default=None, description="Encrypted refresh token")
    token_expires_at: Optional[datetime] = Field(default=None)
    token_last_refreshed: Optional[datetime] = Field(default=None)
    
    # Connection status
    status: str = Field(default="inactive", description="Connection status")
    last_status_check: Optional[datetime] = None
    last_successful_call: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    
    # Configuration
    config_meta: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Soft delete
    deleted_at: Optional[datetime] = None
    is_deleted: bool = Field(default=False)


class AILog(SQLModel, table=True):
    """AI usage log model for tracking costs and usage."""
    
    __tablename__ = "ai_logs"
    __table_args__ = (
        Index('idx_ai_logs_user', 'user_id'),
        Index('idx_ai_logs_clinic', 'clinic_id'),
        Index('idx_ai_logs_created', 'created_at'),
        {'extend_existing': True}
    )
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    
    # AI request details
    model: str = Field(description="AI model used (gpt-4, whisper, etc.)")
    provider: str = Field(description="AI provider (openai, google, anthropic)")
    request_type: str = Field(description="Type of request (transcription, summarization, etc.)")
    
    # Usage tracking
    tokens_used: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    
    # Cost tracking
    cost: Optional[float] = Field(default=0.0, description="Cost in USD")
    cost_currency: str = Field(default="USD")
    
    # Request/Response
    request_payload: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    response_payload: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    
    # Performance
    duration_seconds: Optional[float] = None
    success: bool = Field(default=True)
    error_message: Optional[str] = None
    
    # Context
    consultation_id: Optional[uuid.UUID] = None
    recording_id: Optional[uuid.UUID] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReportsCache(SQLModel, table=True):
    """Reports cache model for storing pre-computed reports."""
    
    __tablename__ = "reports_cache"
    __table_args__ = (
        Index('idx_reports_cache_clinic', 'clinic_id'),
        Index('idx_reports_cache_type', 'report_type'),
        Index('idx_reports_cache_generated', 'generated_at'),
        {'extend_existing': True}
    )
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Report identification
    report_type: str = Field(description="Type of report (appointments_week, revenue_month, etc.)")
    report_key: str = Field(description="Unique key for this report configuration")
    
    # Report data
    data_json: Dict[str, Any] = Field(sa_column=Column(JSON))
    
    # Parameters
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Cache management
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(description="When this cache expires")
    is_valid: bool = Field(default=True)
    
    # Metadata
    generation_duration_seconds: Optional[float] = None
    record_count: Optional[int] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EnhancedFile(SQLModel, table=True):
    """Enhanced file model with additional fields."""
    
    __tablename__ = "files_enhanced"
    __table_args__ = (
        Index('idx_files_clinic', 'clinic_id'),
        Index('idx_files_patient', 'patient_id'),
        Index('idx_files_entity', 'entity_type', 'entity_id'),
        {'extend_existing': True}
    )
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    uploaded_by: uuid.UUID = Field(foreign_key="users.id")
    
    # Entity relationship (polymorphic)
    entity_type: str = Field(description="Type of entity (medical_record, prescription, patient)")
    entity_id: uuid.UUID = Field(description="ID of related entity")
    patient_id: Optional[uuid.UUID] = Field(foreign_key="patients.id", default=None)
    
    # File information
    filename: str
    file_type: str
    file_size: int
    file_path: str
    file_url: Optional[str] = None
    
    # Security
    file_hash: Optional[str] = Field(description="SHA-256 file hash")
    encryption_key: Optional[str] = None
    is_encrypted: bool = Field(default=False)
    
    # Metadata
    description: Optional[str] = None
    file_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    
    # Status
    status: str = Field(default="uploaded")
    scan_status: str = Field(default="pending", description="Virus scan status")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Soft delete
    deleted_at: Optional[datetime] = None
    is_deleted: bool = Field(default=False)

