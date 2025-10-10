"""
SQLModel models for Prontivus database schema.
These models match the database tables we created.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON, Enum as SQLEnum
from pydantic import EmailStr
import uuid


class ClinicBase(SQLModel):
    """Base clinic model."""
    name: str
    cnpj_cpf: Optional[str] = None
    contact_email: str
    contact_phone: Optional[str] = None
    logo_url: Optional[str] = None
    settings: Optional[Dict[str, Any]] = Field(default_factory=lambda: {}, sa_column=Column(JSON))
    status: str = Field(default="active")


class Clinic(ClinicBase, table=True):
    """Clinic model - represents a tenant."""
    __tablename__ = "clinics"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    users: List["User"] = Relationship(back_populates="clinic")
    patients: List["Patient"] = Relationship(back_populates="clinic")
    appointments: List["Appointment"] = Relationship(back_populates="clinic")
    medical_records: List["MedicalRecord"] = Relationship(back_populates="clinic")
    files: List["File"] = Relationship(back_populates="clinic")
    invoices: List["Invoice"] = Relationship(back_populates="clinic")
    licenses: List["License"] = Relationship(back_populates="clinic")
    audit_logs: List["AuditLog"] = Relationship(back_populates="clinic")


class UserBase(SQLModel):
    """Base user model."""
    name: str
    email: str
    phone: Optional[str] = None
    role: str = Field(default="patient")
    is_active: bool = Field(default=True)
    last_login: Optional[datetime] = None


class User(UserBase, table=True):
    """User model."""
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id")
    password_hash: str
    twofa_secret: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    clinic: Optional[Clinic] = Relationship(back_populates="users")
    appointments_as_doctor: List["Appointment"] = Relationship(back_populates="doctor")
    medical_records: List["MedicalRecord"] = Relationship(back_populates="doctor")
    audit_logs: List["AuditLog"] = Relationship(back_populates="user")


class PatientBase(SQLModel):
    """Base patient model."""
    name: str
    birthdate: Optional[date] = None
    gender: str = Field(default="unknown")
    cpf: Optional[str] = None
    address: Optional[Dict[str, Any]] = Field(default_factory=lambda: {}, sa_column=Column(JSON))
    phone: Optional[str] = None
    email: Optional[str] = None
    insurance_number: Optional[str] = None
    insurance_provider: Optional[str] = None


class Patient(PatientBase, table=True):
    """Patient model."""
    __tablename__ = "patients"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    clinic: Optional[Clinic] = Relationship(back_populates="patients")
    appointments: List["Appointment"] = Relationship(back_populates="patient")
    medical_records: List["MedicalRecord"] = Relationship(back_populates="patient")
    files: List["File"] = Relationship(back_populates="patient")
    invoices: List["Invoice"] = Relationship(back_populates="patient")


class AppointmentBase(SQLModel):
    """Base appointment model."""
    start_time: datetime
    end_time: datetime
    status: str = Field(default="scheduled")


class Appointment(AppointmentBase, table=True):
    """Appointment model."""
    __tablename__ = "appointments"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id")
    patient_id: str = Field(foreign_key="patients.id")
    doctor_id: str = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    clinic: Optional[Clinic] = Relationship(back_populates="appointments")
    patient: Optional[Patient] = Relationship(back_populates="appointments")
    doctor: Optional[User] = Relationship(back_populates="appointments_as_doctor")
    medical_records: List["MedicalRecord"] = Relationship(back_populates="appointment")
    # files: List["File"] = Relationship(back_populates="appointment")  # Commented out - column doesn't exist in DB


class MedicalRecordBase(SQLModel):
    """Base medical record model."""
    anamnesis: Optional[str] = None
    physical_exam: Optional[str] = None
    diagnosis: Optional[str] = None
    icd_code: Optional[str] = None
    treatment_plan: Optional[str] = None


class MedicalRecord(MedicalRecordBase, table=True):
    """Medical record model."""
    __tablename__ = "medical_records"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    appointment_id: Optional[str] = Field(default=None, foreign_key="appointments.id")
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id")
    doctor_id: Optional[str] = Field(default=None, foreign_key="users.id")
    patient_id: str = Field(foreign_key="patients.id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    appointment: Optional[Appointment] = Relationship(back_populates="medical_records")
    clinic: Optional[Clinic] = Relationship(back_populates="medical_records")
    doctor: Optional[User] = Relationship(back_populates="medical_records")
    patient: Optional[Patient] = Relationship(back_populates="medical_records")
    prescriptions: List["Prescription"] = Relationship(back_populates="record")
    files: List["File"] = Relationship(back_populates="record")


class PrescriptionBase(SQLModel):
    """Base prescription model."""
    medication_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None


class Prescription(PrescriptionBase, table=True):
    """Prescription model."""
    __tablename__ = "prescriptions"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    record_id: str = Field(foreign_key="medical_records.id")
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    record: Optional[MedicalRecord] = Relationship(back_populates="prescriptions")


class FileBase(SQLModel):
    """Base file model."""
    filename: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    storage_path: str
    file_metadata: Optional[Dict[str, Any]] = Field(default_factory=lambda: {}, sa_column=Column("metadata", JSON))
    scan_status: str = Field(default="pending")


class File(FileBase, table=True):
    """File model."""
    __tablename__ = "files"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id")
    uploaded_by: Optional[str] = Field(default=None, foreign_key="users.id")
    patient_id: Optional[str] = Field(default=None, foreign_key="patients.id")
    record_id: Optional[str] = Field(default=None, foreign_key="medical_records.id")
    # appointment_id: Optional[str] = Field(default=None, foreign_key="appointments.id")  # Commented out - column doesn't exist in DB
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    clinic: Optional[Clinic] = Relationship(back_populates="files")
    patient: Optional[Patient] = Relationship(back_populates="files")
    record: Optional[MedicalRecord] = Relationship(back_populates="files")
    # appointment: Optional[Appointment] = Relationship(back_populates="files")  # Commented out - column doesn't exist in DB


class InvoiceBase(SQLModel):
    """Base invoice model."""
    amount: float
    method: Optional[str] = None
    status: str = Field(default="pending")
    due_date: Optional[date] = None
    paid_at: Optional[datetime] = None
    payment_metadata: Optional[Dict[str, Any]] = Field(default_factory=lambda: {}, sa_column=Column(JSON))


class Invoice(InvoiceBase, table=True):
    """Invoice model."""
    __tablename__ = "invoices"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id")
    patient_id: Optional[str] = Field(default=None, foreign_key="patients.id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    clinic: Optional[Clinic] = Relationship(back_populates="invoices")
    patient: Optional[Patient] = Relationship(back_populates="invoices")


class LicenseBase(SQLModel):
    """Base license model."""
    plan: str
    modules: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))
    users_limit: int = Field(default=0)
    units_limit: int = Field(default=0)
    start_at: datetime
    end_at: datetime
    status: str = Field(default="active")
    signature: Optional[str] = None


class License(LicenseBase, table=True):
    """License model."""
    __tablename__ = "licenses"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    clinic: Optional[Clinic] = Relationship(back_populates="licenses")


class AuditLogBase(SQLModel):
    """Base audit log model."""
    action: str
    entity: str
    entity_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    details: Optional[Dict[str, Any]] = Field(default_factory=lambda: {}, sa_column=Column(JSON))


class AuditLog(AuditLogBase, table=True):
    """Audit log model."""
    __tablename__ = "audit_logs"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: Optional[uuid.UUID] = Field(default=None, foreign_key="clinics.id")
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    clinic: Optional[Clinic] = Relationship(back_populates="audit_logs")
    user: Optional[User] = Relationship(back_populates="audit_logs")


class NotificationBase(SQLModel):
    """Base notification model."""
    type: Optional[str] = None
    title: str
    body: Optional[str] = None
    meta: Optional[Dict[str, Any]] = Field(default_factory=lambda: {}, sa_column=Column(JSON))
    read: bool = Field(default=False)


class Notification(NotificationBase, table=True):
    """Notification model."""
    __tablename__ = "notifications"
    __table_args__ = {'extend_existing': True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: Optional[uuid.UUID] = Field(default=None, foreign_key="clinics.id")
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.now)


# Pydantic models for API requests/responses
class UserCreate(SQLModel):
    """User creation model."""
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    role: str = Field(default="patient")


class UserLogin(SQLModel):
    """User login model."""
    email: str
    password: str


class UserResponse(UserBase):
    """User response model."""
    id: str
    clinic_id: str
    created_at: datetime
    updated_at: datetime


class PatientCreate(SQLModel):
    """Patient creation model."""
    name: str
    birthdate: Optional[date] = None
    gender: str = Field(default="unknown")
    cpf: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    allergies: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))
    medical_conditions: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))


class PatientResponse(PatientBase):
    """Patient response model."""
    id: str
    clinic_id: str
    created_at: datetime
    updated_at: datetime


class AppointmentCreate(SQLModel):
    """Appointment creation model."""
    patient_id: str
    doctor_id: str
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None


class AppointmentResponse(AppointmentBase):
    """Appointment response model."""
    id: str
    clinic_id: str
    patient_id: str
    doctor_id: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(SQLModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class HealthResponse(SQLModel):
    """Health check response model."""
    status: str
    version: str
    environment: str
    database: str
    timestamp: datetime


class CID10CodeDB(SQLModel, table=True):
    """CID-10/11 diagnostic codes database."""
    __tablename__ = "cid10_codes"
    __table_args__ = {'extend_existing': True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(max_length=10, index=True, unique=True)
    description: str
    category: Optional[str] = Field(default=None, max_length=10)
    type: Optional[str] = Field(default="CID-10", max_length=20)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
