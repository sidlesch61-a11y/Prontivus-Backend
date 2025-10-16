"""
Extended consultation models for vitals, attachments, and queue management.
"""

from datetime import datetime
from typing import Optional, Dict, Any, Union
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON, String as SQLString, Text
import uuid


class VitalsBase(SQLModel):
    """Base vitals model."""
    blood_pressure: Optional[str] = None  # e.g., "120/80"
    heart_rate: Optional[int] = None  # bpm
    temperature: Optional[float] = None  # celsius
    weight: Optional[float] = None  # kg
    height: Optional[float] = None  # cm
    respiratory_rate: Optional[int] = None  # breaths per minute
    oxygen_saturation: Optional[int] = None  # %
    notes: Optional[str] = None


class Vitals(VitalsBase, table=True):
    """Vitals model - stores patient vital signs."""
    __tablename__ = "vitals"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    consultation_id: uuid.UUID = Field(foreign_key="consultations.id")
    patient_id: uuid.UUID = Field(foreign_key="patients.id")
    recorded_by: uuid.UUID = Field(foreign_key="users.id")
    recorded_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AttachmentBase(SQLModel):
    """Base attachment model."""
    file_name: str
    file_type: str  # PDF, JPG, PNG, DOCX, etc.
    file_size: int  # bytes
    description: Optional[str] = None
    category: Optional[str] = None  # exam, document, image, etc.


class Attachment(AttachmentBase, table=True):
    """Attachment model - stores consultation documents."""
    __tablename__ = "attachments"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    consultation_id: uuid.UUID = Field(foreign_key="consultations.id")
    patient_id: uuid.UUID = Field(foreign_key="patients.id")
    file_url: str  # S3 URL or local path
    uploaded_by: uuid.UUID = Field(foreign_key="users.id")
    uploaded_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


class QueueStatusBase(SQLModel):
    """Base queue status model."""
    status: str = Field(default="waiting")  # waiting, in_progress, completed, cancelled
    priority: int = Field(default=0)  # 0=normal, 1=urgent, 2=emergency
    notes: Optional[str] = None


class QueueStatus(QueueStatusBase, table=True):
    """Queue status model - manages patient queue."""
    __tablename__ = "queue_status"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointments.id")
    patient_id: uuid.UUID = Field(foreign_key="patients.id")
    doctor_id: uuid.UUID = Field(foreign_key="users.id")
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id")
    called_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ConsultationNotesBase(SQLModel):
    """Base consultation notes model."""
    anamnese: Optional[str] = Field(default=None, sa_column=Column(Text))
    physical_exam: Optional[str] = Field(default=None, sa_column=Column(Text))
    evolution: Optional[str] = Field(default=None, sa_column=Column(Text))
    diagnosis: Optional[str] = Field(default=None, sa_column=Column(Text))
    treatment_plan: Optional[str] = Field(default=None, sa_column=Column(Text))
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None


class ConsultationNotes(ConsultationNotesBase, table=True):
    """Consultation notes model - detailed consultation data."""
    __tablename__ = "consultation_notes"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    consultation_id: uuid.UUID = Field(foreign_key="consultations.id", unique=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    auto_saved_at: Optional[datetime] = None


class PrescriptionItemBase(SQLModel):
    """Base prescription item model."""
    medication_name: str
    dosage: str  # e.g., "500mg"
    frequency: str  # e.g., "8/8h", "2x ao dia"
    duration: str  # e.g., "7 dias", "uso contínuo"
    route: str = Field(default="oral")  # oral, intravenous, topical, etc.
    instructions: Optional[str] = None


class PrescriptionItem(PrescriptionItemBase, table=True):
    """Prescription item model - individual medications."""
    __tablename__ = "prescription_items"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    prescription_id: uuid.UUID = Field(foreign_key="prescriptions.id")
    created_at: datetime = Field(default_factory=datetime.now)


class MedicalCertificateBase(SQLModel):
    """Base medical certificate model."""
    certificate_type: str  # atestado, declaracao, laudo
    content: str = Field(sa_column=Column(Text))
    days_off: Optional[int] = None
    cid10_code: Optional[str] = None


class MedicalCertificate(MedicalCertificateBase, table=True):
    """Medical certificate model - atestados and declarations."""
    __tablename__ = "medical_certificates"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    consultation_id: uuid.UUID = Field(foreign_key="consultations.id")
    patient_id: uuid.UUID = Field(foreign_key="patients.id")
    doctor_id: uuid.UUID = Field(foreign_key="users.id")
    pdf_url: Optional[str] = None
    icp_signature_hash: Optional[str] = None
    issued_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


class ExamRequestBase(SQLModel):
    """Base exam request model."""
    exam_type: str  # laboratorial, imagem, procedimento
    exam_name: str
    clinical_indication: str = Field(sa_column=Column(Text))
    urgency: str = Field(default="routine")  # routine, urgent, emergency


class ExamRequest(ExamRequestBase, table=True):
    """Exam request model - solicitação de exames."""
    __tablename__ = "exam_requests"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    consultation_id: uuid.UUID = Field(foreign_key="consultations.id")
    patient_id: uuid.UUID = Field(foreign_key="patients.id")
    doctor_id: uuid.UUID = Field(foreign_key="users.id")
    tiss_guide_id: Optional[uuid.UUID] = Field(default=None, foreign_key="tiss_guides.id")
    pdf_url: Optional[str] = None
    status: str = Field(default="pending")  # pending, scheduled, completed, cancelled
    requested_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


class ReferralBase(SQLModel):
    """Base referral model."""
    specialty: str
    reason: str = Field(sa_column=Column(Text))
    urgency: str = Field(default="routine")
    referred_to_doctor: Optional[str] = None
    referred_to_clinic: Optional[str] = None


class Referral(ReferralBase, table=True):
    """Referral model - encaminhamentos."""
    __tablename__ = "referrals"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    consultation_id: uuid.UUID = Field(foreign_key="consultations.id")
    patient_id: uuid.UUID = Field(foreign_key="patients.id")
    doctor_id: uuid.UUID = Field(foreign_key="users.id")
    pdf_url: Optional[str] = None
    status: str = Field(default="pending")  # pending, scheduled, completed
    referred_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


class VoiceNoteBase(SQLModel):
    """Base voice note model."""
    audio_url: str
    duration_seconds: int
    transcription: Optional[str] = Field(default=None, sa_column=Column(Text))
    note_type: str = Field(default="anamnese")  # anamnese, evolution, general


class VoiceNote(VoiceNoteBase, table=True):
    """Voice note model - audio recordings with transcription."""
    __tablename__ = "voice_notes"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    consultation_id: uuid.UUID = Field(foreign_key="consultations.id")
    recorded_by: uuid.UUID = Field(foreign_key="users.id")
    transcribed_at: Optional[datetime] = None
    recorded_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


# Pydantic schemas for API responses

class VitalsCreate(VitalsBase):
    """Schema for creating vitals."""
    consultation_id: uuid.UUID
    patient_id: uuid.UUID


class VitalsResponse(VitalsBase):
    """Schema for vitals response."""
    id: uuid.UUID
    consultation_id: uuid.UUID
    patient_id: uuid.UUID
    recorded_by: uuid.UUID
    recorded_at: datetime


class VitalsUpsert(SQLModel):
    """Relaxed request schema for creating/updating vitals that tolerates string inputs."""
    consultation_id: uuid.UUID
    patient_id: uuid.UUID
    blood_pressure: Optional[str] = None
    heart_rate: Optional[Union[int, str]] = None
    temperature: Optional[Union[float, str]] = None
    weight: Optional[Union[float, str]] = None
    height: Optional[Union[float, str]] = None
    respiratory_rate: Optional[Union[int, str]] = None
    oxygen_saturation: Optional[Union[int, str]] = None
    notes: Optional[str] = None


class AttachmentCreate(AttachmentBase):
    """Schema for creating attachment."""
    consultation_id: uuid.UUID
    patient_id: uuid.UUID
    file_url: str


class AttachmentResponse(AttachmentBase):
    """Schema for attachment response."""
    id: uuid.UUID
    consultation_id: uuid.UUID
    patient_id: uuid.UUID
    file_url: str
    uploaded_by: uuid.UUID
    uploaded_at: datetime


class QueueStatusResponse(QueueStatusBase):
    """Schema for queue status response."""
    id: uuid.UUID
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    appointment_time: Optional[datetime] = None
    called_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ConsultationNotesUpdate(SQLModel):
    """Schema for updating consultation notes."""
    anamnese: Optional[str] = None
    physical_exam: Optional[str] = None
    evolution: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None


class PrescriptionItemCreate(PrescriptionItemBase):
    """Schema for creating prescription item."""
    pass


class MedicalCertificateCreate(MedicalCertificateBase):
    """Schema for creating medical certificate."""
    consultation_id: uuid.UUID
    patient_id: uuid.UUID


class ExamRequestCreate(ExamRequestBase):
    """Schema for creating exam request."""
    consultation_id: uuid.UUID
    patient_id: uuid.UUID


class ReferralCreate(ReferralBase):
    """Schema for creating referral."""
    consultation_id: uuid.UUID
    patient_id: uuid.UUID


class VoiceNoteCreate(SQLModel):
    """Schema for creating voice note."""
    consultation_id: uuid.UUID
    audio_url: str
    duration_seconds: int
    note_type: str = "anamnese"

