"""
Database models for native telemedicine system with WebRTC orchestration.
"""

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
import uuid

class TelemedSessionStatus(str, Enum):
    """Telemedicine session status enumeration."""
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"
    FAILED = "failed"

class TelemedSessionEvent(str, Enum):
    """Telemedicine session event types."""
    CREATED = "created"
    JOINED = "joined"
    LEFT = "left"
    CONSENT_GIVEN = "consent_given"
    CONSENT_DENIED = "consent_denied"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    RECORDING_FAILED = "recording_failed"
    ENDED = "ended"
    ERROR = "error"

class TelemedUserRole(str, Enum):
    """Telemedicine user role enumeration."""
    DOCTOR = "doctor"
    PATIENT = "patient"
    ADMIN = "admin"

class TelemedSession(SQLModel, table=True):
    """Telemedicine session model."""
    
    __tablename__ = "telemed_sessions"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointments.id", index=True)
    doctor_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patients.id", index=True)
    
    # Session identification
    link_token: str = Field(unique=True, index=True, description="JWT token for session access")
    session_id: str = Field(unique=True, index=True, description="SFU session identifier")
    room_id: str = Field(description="SFU room identifier")
    
    # Session configuration
    allow_recording: bool = Field(default=False, description="Whether recording is allowed")
    recording_encrypted: bool = Field(default=True, description="Whether recording is encrypted")
    max_duration_minutes: int = Field(default=60, description="Maximum session duration")
    
    # Time management
    scheduled_start: datetime = Field(description="Scheduled session start time")
    scheduled_end: datetime = Field(description="Scheduled session end time")
    actual_start: Optional[datetime] = Field(default=None, description="Actual session start time")
    actual_end: Optional[datetime] = Field(default=None, description="Actual session end time")
    
    # Session status
    status: TelemedSessionStatus = Field(default=TelemedSessionStatus.SCHEDULED)
    
    # Consent management
    doctor_consent: Optional[bool] = Field(default=None, description="Doctor consent for recording")
    patient_consent: Optional[bool] = Field(default=None, description="Patient consent for recording")
    consent_timestamp: Optional[datetime] = Field(default=None, description="When consent was given")
    
    # Recording information
    recording_file_path: Optional[str] = Field(default=None, description="Path to recording file")
    recording_file_size: Optional[int] = Field(default=None, description="Recording file size in bytes")
    recording_duration_seconds: Optional[int] = Field(default=None, description="Recording duration")
    recording_encryption_key: Optional[str] = Field(default=None, description="Encryption key for recording")
    
    # SFU configuration
    sfu_config: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    turn_credentials: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Session metadata
    session_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    error_message: Optional[str] = Field(default=None, description="Error message if session failed")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    appointment: Optional["Appointment"] = Relationship()
    doctor: Optional["User"] = Relationship()
    patient: Optional["Patient"] = Relationship()
    logs: List["TelemedSessionLog"] = Relationship(back_populates="session")

class TelemedSessionLog(SQLModel, table=True):
    """Telemedicine session log model."""
    
    __tablename__ = "telemed_session_logs"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="telemed_sessions.id", index=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Event details
    event: TelemedSessionEvent = Field(description="Event type")
    user_id: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None, description="User who triggered event")
    user_role: Optional[TelemedUserRole] = Field(default=None, description="Role of user who triggered event")
    
    # Event metadata
    meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    message: Optional[str] = Field(default=None, description="Event message")
    
    # Technical details
    ip_address: Optional[str] = Field(default=None, description="IP address of user")
    user_agent: Optional[str] = Field(default=None, description="User agent string")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    session: Optional["TelemedSession"] = Relationship(back_populates="logs")
    clinic: Optional["Clinic"] = Relationship()
    user: Optional["User"] = Relationship()

class TelemedRecording(SQLModel, table=True):
    """Telemedicine recording model."""
    
    __tablename__ = "telemed_recordings"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="telemed_sessions.id", index=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Recording details
    file_path: str = Field(description="Path to recording file")
    file_size: int = Field(description="File size in bytes")
    duration_seconds: int = Field(description="Recording duration in seconds")
    format: str = Field(default="webm", description="Recording format")
    
    # Encryption
    encrypted: bool = Field(default=True, description="Whether file is encrypted")
    encryption_key: Optional[str] = Field(default=None, description="Encryption key")
    encryption_algorithm: str = Field(default="AES-256-GCM", description="Encryption algorithm")
    
    # Processing status
    processing_status: str = Field(default="pending", description="Processing status")
    processing_error: Optional[str] = Field(default=None, description="Processing error message")
    
    # Storage
    storage_provider: str = Field(default="s3", description="Storage provider")
    storage_bucket: str = Field(description="Storage bucket")
    storage_key: str = Field(description="Storage key")
    
    # Metadata
    recording_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    session: Optional["TelemedSession"] = Relationship()
    clinic: Optional["Clinic"] = Relationship()

# Pydantic schemas for API
class TelemedSessionCreateRequest(SQLModel):
    """Request schema for creating telemedicine session."""
    appointment_id: uuid.UUID = Field(description="Appointment ID")
    doctor_id: uuid.UUID = Field(description="Doctor ID")
    allow_recording: bool = Field(default=False, description="Whether recording is allowed")
    max_duration_minutes: int = Field(default=60, description="Maximum session duration")
    scheduled_start: datetime = Field(description="Scheduled session start time")
    scheduled_end: datetime = Field(description="Scheduled session end time")

class TelemedSessionResponse(SQLModel):
    """Response schema for telemedicine session."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    appointment_id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    link_token: str
    session_id: str
    room_id: str
    allow_recording: bool
    recording_encrypted: bool
    max_duration_minutes: int
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: TelemedSessionStatus
    doctor_consent: Optional[bool] = None
    patient_consent: Optional[bool] = None
    consent_timestamp: Optional[datetime] = None
    recording_file_path: Optional[str] = None
    recording_file_size: Optional[int] = None
    recording_duration_seconds: Optional[int] = None
    sfu_config: Optional[Dict[str, Any]] = None
    session_meta: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class TelemedJoinRequest(SQLModel):
    """Request schema for joining telemedicine session."""
    link_token: str = Field(description="Session link token")
    user_role: TelemedUserRole = Field(description="User role (doctor/patient)")

class TelemedJoinResponse(SQLModel):
    """Response schema for joining telemedicine session."""
    session_id: str = Field(description="SFU session ID")
    room_id: str = Field(description="SFU room ID")
    sfu_endpoint: str = Field(description="SFU endpoint URL")
    turn_credentials: Dict[str, Any] = Field(description="TURN server credentials")
    ice_servers: List[Dict[str, Any]] = Field(description="ICE servers configuration")
    session_config: Dict[str, Any] = Field(description="Session configuration")
    expires_at: datetime = Field(description="Session expiration time")

class TelemedConsentRequest(SQLModel):
    """Request schema for consent management."""
    user_id: uuid.UUID = Field(description="User ID")
    consent: bool = Field(description="Consent given or denied")
    consent_type: str = Field(default="recording", description="Type of consent")

class TelemedConsentResponse(SQLModel):
    """Response schema for consent management."""
    session_id: uuid.UUID
    user_id: uuid.UUID
    consent: bool
    consent_type: str
    timestamp: datetime
    message: str

class TelemedSessionEndRequest(SQLModel):
    """Request schema for ending telemedicine session."""
    reason: Optional[str] = Field(default=None, description="Reason for ending session")
    notes: Optional[str] = Field(default=None, description="Session notes")

class TelemedSessionEndResponse(SQLModel):
    """Response schema for ending telemedicine session."""
    session_id: uuid.UUID
    status: TelemedSessionStatus
    duration_seconds: Optional[int] = None
    recording_file_path: Optional[str] = None
    message: str

class TelemedSessionLogResponse(SQLModel):
    """Response schema for telemedicine session log."""
    id: uuid.UUID
    session_id: uuid.UUID
    event: TelemedSessionEvent
    user_id: Optional[uuid.UUID] = None
    user_role: Optional[TelemedUserRole] = None
    meta: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

# WebRTC and SFU configuration schemas
class WebRTCCredentials(SQLModel):
    """WebRTC credentials schema."""
    ice_servers: List[Dict[str, Any]] = Field(description="ICE servers configuration")
    turn_username: str = Field(description="TURN username")
    turn_password: str = Field(description="TURN password")
    turn_ttl: int = Field(default=3600, description="TURN credentials TTL in seconds")

class SFUConfig(SQLModel):
    """SFU configuration schema."""
    endpoint: str = Field(description="SFU endpoint URL")
    api_key: str = Field(description="SFU API key")
    room_id: str = Field(description="SFU room ID")
    session_id: str = Field(description="SFU session ID")
    capabilities: Dict[str, Any] = Field(description="SFU capabilities")

class RecordingConfig(SQLModel):
    """Recording configuration schema."""
    enabled: bool = Field(description="Whether recording is enabled")
    format: str = Field(default="webm", description="Recording format")
    quality: str = Field(default="high", description="Recording quality")
    encryption: bool = Field(default=True, description="Whether to encrypt recording")
    storage_provider: str = Field(default="s3", description="Storage provider")
    storage_bucket: str = Field(description="Storage bucket")

# Utility classes
class TelemedSessionValidator:
    """Utility class for telemedicine session validation."""
    
    @staticmethod
    def validate_session_time_window(scheduled_start: datetime, scheduled_end: datetime) -> bool:
        """Validate session time window."""
        now = datetime.utcnow()
        return scheduled_start <= now <= scheduled_end
    
    @staticmethod
    def validate_session_duration(scheduled_start: datetime, scheduled_end: datetime, max_duration_minutes: int) -> bool:
        """Validate session duration."""
        duration = scheduled_end - scheduled_start
        max_duration = timedelta(minutes=max_duration_minutes)
        return duration <= max_duration
    
    @staticmethod
    def is_session_active(session: TelemedSession) -> bool:
        """Check if session is active."""
        return (
            session.status == TelemedSessionStatus.ACTIVE and
            session.actual_start is not None and
            (session.actual_end is None or session.actual_end > datetime.utcnow())
        )

class TelemedRecordingManager:
    """Utility class for telemedicine recording management."""
    
    @staticmethod
    def generate_recording_filename(session_id: str, timestamp: datetime) -> str:
        """Generate recording filename."""
        return f"telemed_{session_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.webm"
    
    @staticmethod
    def calculate_recording_duration(start_time: datetime, end_time: datetime) -> int:
        """Calculate recording duration in seconds."""
        duration = end_time - start_time
        return int(duration.total_seconds())
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/(1024**2):.1f} MB"
        else:
            return f"{size_bytes/(1024**3):.1f} GB"
