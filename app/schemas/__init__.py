"""
Pydantic schemas for request/response models.
"""

import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator

from app.models import (
    UserRole, ClinicStatus, AppointmentStatus, AppointmentSource,
    InvoiceStatus, PaymentMethod, LicenseStatus, ActivationStatus
)

# Import new schemas
from .consultation_finalization import (
    ConsultationFinalizeRequest, ConsultationFinalizeResponse,
    ConsultationHistoryItem, ConsultationHistoryResponse,
    PrintDocumentRequest, PrintConsolidatedRequest
)


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    model_config = {
        "from_attributes": True,
        "use_enum_values": True
    }


# Auth schemas
class UserRegister(BaseSchema):
    """User registration schema."""
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.ADMIN


class ClinicRegister(BaseSchema):
    """Clinic registration schema."""
    name: str = Field(..., min_length=2, max_length=255)
    cnpj_cpf: str = Field(..., min_length=11, max_length=20)
    contact_email: EmailStr
    contact_phone: str = Field(..., min_length=10, max_length=20)


class RegisterRequest(BaseSchema):
    """Complete registration request."""
    clinic: ClinicRegister
    user: UserRegister


class LoginRequest(BaseSchema):
    """Login request schema."""
    email: EmailStr
    password: str
    two_fa_code: Optional[str] = Field(None, min_length=6, max_length=8, description="6-digit 2FA code or 8-character backup code")


class TokenResponse(BaseSchema):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseSchema):
    """Refresh token request."""
    refresh_token: str


class TwoFactorRequest(BaseSchema):
    """2FA verification request."""
    token: str = Field(..., min_length=6, max_length=6)


class UserResponse(BaseSchema):
    """User response schema."""
    id: uuid.UUID
    name: str
    email: str
    phone: Optional[str]
    role: str
    is_active: bool
    last_login: Optional[datetime]
    clinic_id: uuid.UUID


class UserUpdate(BaseSchema):
    """User update schema."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)


# Clinic schemas
class ClinicResponse(BaseSchema):
    """Clinic response schema."""
    id: uuid.UUID
    name: str
    cnpj_cpf: str
    contact_email: str
    contact_phone: str
    logo_url: Optional[str]
    status: str  # Changed from ClinicStatus enum to str to handle any case
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime


class ClinicUpdate(BaseSchema):
    """Clinic update schema - all fields optional for partial updates."""
    name: Optional[str] = None
    contact_email: Optional[str] = None  # Changed from EmailStr to avoid validation on None
    contact_phone: Optional[str] = None
    logo_url: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


# Patient schemas
class PatientCreate(BaseSchema):
    """Patient creation schema."""
    name: str = Field(..., min_length=2, max_length=255)
    birthdate: date
    gender: str = Field(..., min_length=1, max_length=10)
    cpf: str = Field(..., min_length=11, max_length=14)
    address: Optional[Dict[str, Any]] = Field(default_factory=dict)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr]
    insurance_number: Optional[str] = Field(None, max_length=50)
    insurance_provider: Optional[str] = Field(None, max_length=100)
    
    @validator('cpf')
    def validate_cpf(cls, v):
        # Basic CPF validation (11 digits)
        cpf_digits = ''.join(filter(str.isdigit, v))
        if len(cpf_digits) != 11:
            raise ValueError('CPF must have 11 digits')
        return cpf_digits


class PatientUpdate(BaseSchema):
    """Patient update schema."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    birthdate: Optional[date]
    gender: Optional[str] = Field(None, min_length=1, max_length=10)
    address: Optional[Dict[str, Any]]
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr]
    insurance_number: Optional[str] = Field(None, max_length=50)
    insurance_provider: Optional[str] = Field(None, max_length=100)


class PatientResponse(BaseSchema):
    """Patient response schema."""
    id: uuid.UUID
    name: str
    birthdate: Optional[date]
    gender: str
    cpf: Optional[str]
    address: Optional[Dict[str, Any]]
    city: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    insurance_number: Optional[str]
    insurance_provider: Optional[str]
    clinic_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# Appointment schemas
class AppointmentCreate(BaseSchema):
    """Appointment creation schema."""
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: Optional[AppointmentStatus] = AppointmentStatus.SCHEDULED
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v


class AppointmentUpdate(BaseSchema):
    """Appointment update schema."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None


class AppointmentResponse(BaseSchema):
    """Appointment response schema."""
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    clinic_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    
    # Related data
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None


# Medical record schemas
class MedicalRecordCreate(BaseSchema):
    """Medical record creation schema."""
    patient_id: uuid.UUID
    appointment_id: Optional[uuid.UUID] = None
    anamnesis: Optional[str] = Field(None, max_length=5000)
    physical_exam: Optional[str] = Field(None, max_length=5000)
    diagnosis: Optional[str] = Field(None, max_length=2000)
    icd_code: Optional[str] = Field(None, max_length=20)
    treatment_plan: Optional[str] = Field(None, max_length=5000)


class MedicalRecordUpdate(BaseSchema):
    """Medical record update schema."""
    anamnesis: Optional[str] = Field(None, max_length=5000)
    physical_exam: Optional[str] = Field(None, max_length=5000)
    diagnosis: Optional[str] = Field(None, max_length=2000)
    icd_code: Optional[str] = Field(None, max_length=20)
    treatment_plan: Optional[str] = Field(None, max_length=5000)


class MedicalRecordResponse(BaseSchema):
    """Medical record response schema."""
    id: uuid.UUID
    appointment_id: Optional[uuid.UUID]
    doctor_id: Optional[uuid.UUID]
    patient_id: uuid.UUID
    clinic_id: uuid.UUID
    anamnesis: Optional[str]
    physical_exam: Optional[str]
    diagnosis: Optional[str]
    icd_code: Optional[str]
    treatment_plan: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    # Related data
    doctor_name: Optional[str] = None
    patient_name: Optional[str] = None


# REMOVED DUPLICATE - See line 330 for correct PrescriptionCreate schema


# File/Exam schemas
class FilePresignRequest(BaseSchema):
    """File presign request schema."""
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=100)
    file_size: Optional[int] = Field(None, gt=0)


class FilePresignResponse(BaseSchema):
    """File presign response schema."""
    upload_url: str
    file_id: uuid.UUID
    expires_in: int


class FileCompleteRequest(BaseSchema):
    """File complete request schema."""
    file_id: uuid.UUID
    record_id: Optional[uuid.UUID] = None
    exam_type: str = Field(..., min_length=1, max_length=100)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class FileResponse(BaseSchema):
    """File response schema."""
    id: uuid.UUID
    file_url: str
    type: str
    metadata: Dict[str, Any]
    uploaded_by: uuid.UUID
    created_at: datetime


# Invoice schemas
class InvoiceCreate(BaseSchema):
    """Invoice creation schema."""
    patient_id: uuid.UUID
    appointment_id: Optional[uuid.UUID] = None
    amount: float = Field(..., gt=0)
    method: Optional[str] = None
    status: Optional[str] = "pending"
    due_date: Optional[date] = None
    payment_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class InvoiceResponse(BaseSchema):
    """Invoice response schema."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    patient_id: Optional[uuid.UUID]
    appointment_id: Optional[uuid.UUID]
    amount: float
    method: Optional[str]
    status: str
    due_date: Optional[date]
    paid_at: Optional[datetime]
    payment_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    # Related data
    patient_name: Optional[str] = None


# Prescription schemas
class MedicationItem(BaseSchema):
    """Medication item in a prescription."""
    medication_name: str = Field(..., min_length=1, max_length=255)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)  # Optional - some medications don't need frequency
    duration: Optional[str] = Field(None, max_length=100)   # Optional - some medications are continuous


class PrescriptionCreate(BaseSchema):
    """Prescription creation schema - for prescriptions with multiple medications."""
    patient_id: uuid.UUID
    prescription_type: str = "simple"  # simple, antimicrobial, C1
    medications: List[MedicationItem] = Field(..., min_items=1)
    notes: Optional[str] = None
    record_id: Optional[uuid.UUID] = None


class PrescriptionCreateSingle(BaseSchema):
    """Single medication prescription creation schema (for compatibility)."""
    patient_id: uuid.UUID
    medication_name: str = Field(..., min_length=2, max_length=255)
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    duration: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    record_id: Optional[uuid.UUID] = None


class PrescriptionUpdate(BaseSchema):
    """Prescription update schema."""
    medication_name: Optional[str] = Field(None, min_length=2, max_length=255)
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    duration: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class PrescriptionResponse(BaseSchema):
    """Prescription response schema."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    record_id: Optional[uuid.UUID]
    medication_name: str
    dosage: Optional[str]
    frequency: Optional[str]
    duration: Optional[str]
    notes: Optional[str]
    created_at: datetime
    patient_id: Optional[str] = None  # For frontend display
    patient_name: Optional[str] = None  # For frontend display
    doctor_name: Optional[str] = None  # For frontend display


# License schemas
class LicenseCreate(BaseSchema):
    """License creation schema."""
    plan: str = Field(..., min_length=1, max_length=100)
    modules: List[str] = Field(default_factory=list)
    users_limit: int = Field(..., gt=0)
    units_limit: int = Field(..., gt=0)
    start_at: datetime
    end_at: datetime


class LicenseActivateRequest(BaseSchema):
    """License activation request schema."""
    instance_id: str = Field(..., min_length=1, max_length=100)
    device_info: Dict[str, Any] = Field(default_factory=dict)


class LicenseResponse(BaseSchema):
    """License response schema."""
    id: uuid.UUID
    plan: str
    modules: List[str]
    users_limit: int
    units_limit: int
    start_at: datetime
    end_at: datetime
    status: LicenseStatus
    created_at: datetime


# Sync schemas
class SyncEvent(BaseSchema):
    """Sync event schema."""
    client_event_id: uuid.UUID
    event_type: str = Field(..., min_length=1, max_length=100)
    payload: Dict[str, Any]
    client_timestamp: datetime
    idempotency_key: str = Field(..., min_length=1, max_length=100)


class SyncRequest(BaseSchema):
    """Sync request schema."""
    events: List[SyncEvent] = Field(..., min_items=1, max_items=100)


class SyncResult(BaseSchema):
    """Sync result schema."""
    client_event_id: uuid.UUID
    server_id: Optional[uuid.UUID]
    status: str
    error: Optional[str] = None


class SyncResponse(BaseSchema):
    """Sync response schema."""
    results: List[SyncResult]


# Webhook schemas
class WebhookRequest(BaseSchema):
    """Generic webhook request schema."""
    event_type: str
    data: Dict[str, Any]
    signature: Optional[str] = None
    idempotency_key: Optional[str] = None


# Error schemas
class ErrorResponse(BaseSchema):
    """Error response schema."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# Pagination schemas
class PaginationParams(BaseSchema):
    """Pagination parameters."""
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class PaginatedResponse(BaseSchema):
    """Paginated response schema."""
    items: List[dict] = []
    total: int = 0
    page: int = 1
    size: int = 20
    pages: int = 0
