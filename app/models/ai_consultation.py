"""
Database models for AI-powered consultation recording and summarization.
"""

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid

class RecordingStatus(str, Enum):
    """Recording status enumeration."""
    PENDING = "pending"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AISummaryStatus(str, Enum):
    """AI summary status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class STTProvider(str, Enum):
    """Speech-to-Text provider enumeration."""
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE = "azure"
    AWS = "aws"

class LLMProvider(str, Enum):
    """Large Language Model provider enumeration."""
    OPENAI = "openai"
    VERTEX = "vertex"
    ANTHROPIC = "anthropic"

class Recording(SQLModel, table=True):
    """Recording model for consultation audio files."""
    
    __tablename__ = "recordings"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    consultation_id: uuid.UUID = Field(foreign_key="appointments.id", index=True)
    started_by: uuid.UUID = Field(foreign_key="users.id", index=True)
    
    # Consent information
    consent_given: bool = Field(default=False)
    consent_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # File information
    storage_path: Optional[str] = Field(default=None)
    file_size: Optional[int] = Field(default=None)
    content_type: Optional[str] = Field(default=None)
    
    # Status and metadata
    status: RecordingStatus = Field(default=RecordingStatus.PENDING)
    record_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    consultation: Optional["Appointment"] = Relationship(back_populates="recordings")
    started_by_user: Optional["User"] = Relationship()
    ai_summaries: List["AISummary"] = Relationship(back_populates="recording")

class AISummary(SQLModel, table=True):
    """AI-generated summary model for consultation recordings."""
    
    __tablename__ = "ai_summaries"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recording_id: uuid.UUID = Field(foreign_key="recordings.id", index=True)
    
    # Processing information
    stt_provider: STTProvider = Field(default=STTProvider.OPENAI)
    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI)
    
    # Content
    transcript_text: Optional[str] = Field(default=None)
    summary_json: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Status and metadata
    status: AISummaryStatus = Field(default=AISummaryStatus.PENDING)
    processing_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Cost tracking
    stt_cost: Optional[float] = Field(default=None)
    llm_cost: Optional[float] = Field(default=None)
    total_cost: Optional[float] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    
    # Relationships
    recording: Optional["Recording"] = Relationship(back_populates="ai_summaries")

# Pydantic schemas for API
class RecordingStartRequest(SQLModel):
    """Request schema for starting a recording."""
    consent: bool
    record_meta: Optional[Dict[str, Any]] = None

class RecordingStartResponse(SQLModel):
    """Response schema for starting a recording."""
    recording_id: uuid.UUID
    upload_url: str
    expires_in: int  # seconds

class RecordingCompleteRequest(SQLModel):
    """Request schema for completing a recording."""
    recording_id: uuid.UUID
    file_uploaded: bool = True

class RecordingCompleteResponse(SQLModel):
    """Response schema for completing a recording."""
    recording_id: uuid.UUID
    status: RecordingStatus
    message: str

class AISummaryResponse(SQLModel):
    """Response schema for AI summary."""
    id: uuid.UUID
    recording_id: uuid.UUID
    status: AISummaryStatus
    transcript_text: Optional[str] = None
    summary_json: Optional[Dict[str, Any]] = None
    stt_provider: STTProvider
    llm_provider: LLMProvider
    total_cost: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

class AIAcceptRequest(SQLModel):
    """Request schema for accepting AI summary."""
    summary_id: uuid.UUID
    edited_payload: Dict[str, Any]

class AIAcceptResponse(SQLModel):
    """Response schema for accepting AI summary."""
    summary_id: uuid.UUID
    medical_record_id: Optional[uuid.UUID] = None
    status: str
    message: str

# Structured AI summary schema
class StructuredSummary(SQLModel):
    """Structured AI summary schema."""
    
    # Anamnese estruturada
    anamnese: Dict[str, Any] = Field(description="Structured anamnesis")
    
    # Hipóteses diagnósticas
    hypotheses: List[Dict[str, Any]] = Field(description="Diagnostic hypotheses with CID codes")
    
    # Exames sugeridos
    suggested_exams: List[str] = Field(description="Suggested examinations")
    
    # Conduta proposta
    proposed_treatment: Dict[str, Any] = Field(description="Proposed treatment plan")
    
    # Metadados
    confidence_score: Optional[float] = Field(default=None, description="Overall confidence score")
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds")
    tokens_used: Optional[int] = Field(default=None, description="LLM tokens used")

# Diagnostic hypothesis schema
class DiagnosticHypothesis(SQLModel):
    """Diagnostic hypothesis with CID code."""
    cid_code: str = Field(description="CID-10 code")
    description: str = Field(description="Diagnosis description")
    confidence: float = Field(description="Confidence score (0-1)")
    reasoning: Optional[str] = Field(default=None, description="Reasoning for this hypothesis")

# Treatment plan schema
class TreatmentPlan(SQLModel):
    """Treatment plan structure."""
    medications: List[Dict[str, Any]] = Field(description="Prescribed medications")
    procedures: List[str] = Field(description="Recommended procedures")
    follow_up: Optional[str] = Field(default=None, description="Follow-up instructions")
    lifestyle_recommendations: Optional[List[str]] = Field(default=None, description="Lifestyle recommendations")
