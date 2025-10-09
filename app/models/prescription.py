"""
Database models for digital prescriptions with PAdES signatures.
"""

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid

class PrescriptionType(str, Enum):
    """Prescription type enumeration."""
    SIMPLE = "simple"
    ANTIMICROBIAL = "antimicrobial"
    C1 = "C1"  # Controlled substances

class PrescriptionStatus(str, Enum):
    """Prescription status enumeration."""
    DRAFT = "draft"
    SIGNED = "signed"
    VERIFIED = "verified"
    EXPIRED = "expired"
    REVOKED = "revoked"

class Prescription(SQLModel, table=True):
    """Digital prescription model with PAdES signature support."""
    
    __tablename__ = "prescriptions"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patients.id", index=True)
    doctor_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    
    # Prescription content
    items: List[Dict[str, Any]] = Field(sa_column_kwargs={"type_": "JSONB"})
    prescription_type: PrescriptionType = Field(default=PrescriptionType.SIMPLE)
    status: PrescriptionStatus = Field(default=PrescriptionStatus.DRAFT)
    
    # Prescription metadata
    rx_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    notes: Optional[str] = Field(default=None)
    
    # Digital signature information
    signed_pdf_path: Optional[str] = Field(default=None)
    signature_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    qr_token: Optional[str] = Field(default=None, unique=True, index=True)
    
    # Signature details
    signer_user_id: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None)
    certificate_id: Optional[str] = Field(default=None)  # Reference to stored certificate
    signed_at: Optional[datetime] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    patient: Optional["Patient"] = Relationship()
    doctor: Optional["User"] = Relationship()
    signer: Optional["User"] = Relationship()

# Pydantic schemas for API
class PrescriptionItem(SQLModel):
    """Individual prescription item."""
    medication: str = Field(description="Medication name")
    dosage: str = Field(description="Dosage amount")
    frequency: str = Field(description="Frequency of administration")
    duration: str = Field(description="Duration of treatment")
    notes: Optional[str] = Field(default=None, description="Additional notes")

class PrescriptionCreateRequest(SQLModel):
    """Request schema for creating a prescription."""
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    items: List[PrescriptionItem]
    prescription_type: PrescriptionType = PrescriptionType.SIMPLE
    rx_meta: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

class PrescriptionSignRequest(SQLModel):
    """Request schema for signing a prescription."""
    signer_user_id: uuid.UUID
    certificate_id: str
    pin: Optional[str] = None  # Certificate PIN (if needed)

class PrescriptionResponse(SQLModel):
    """Response schema for prescription."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    items: List[Dict[str, Any]]
    prescription_type: PrescriptionType
    status: PrescriptionStatus
    rx_meta: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    signed_pdf_path: Optional[str] = None
    qr_token: Optional[str] = None
    signer_user_id: Optional[uuid.UUID] = None
    signed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None

class PrescriptionSignResponse(SQLModel):
    """Response schema for prescription signing."""
    prescription_id: uuid.UUID
    status: PrescriptionStatus
    signed_pdf_path: str
    qr_token: str
    signature_meta: Dict[str, Any]
    verification_url: str
    message: str

class PrescriptionVerificationResponse(SQLModel):
    """Response schema for prescription verification."""
    valid: bool
    prescription_id: Optional[uuid.UUID] = None
    doctor_name: Optional[str] = None
    doctor_crm: Optional[str] = None
    patient_name: Optional[str] = None
    clinic_name: Optional[str] = None
    signed_at: Optional[datetime] = None
    prescription_type: Optional[PrescriptionType] = None
    signature_meta: Optional[Dict[str, Any]] = None
    verification_timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

# Signature metadata schema
class SignatureMetadata(SQLModel):
    """Digital signature metadata."""
    signature_id: str = Field(description="Unique signature identifier")
    certificate_serial: str = Field(description="Certificate serial number")
    certificate_subject: str = Field(description="Certificate subject")
    certificate_issuer: str = Field(description="Certificate issuer")
    signature_algorithm: str = Field(description="Signature algorithm used")
    hash_algorithm: str = Field(description="Hash algorithm used")
    signature_time: datetime = Field(description="Signature timestamp")
    timestamp_authority: Optional[str] = Field(default=None, description="Timestamp authority used")
    timestamp_token: Optional[str] = Field(default=None, description="Timestamp token")
    signature_hash: str = Field(description="Signature hash")
    pdf_hash: str = Field(description="PDF content hash")
    verification_status: str = Field(default="pending", description="Verification status")

# Certificate management schema
class CertificateInfo(SQLModel):
    """Certificate information for signing."""
    certificate_id: str = Field(description="Certificate identifier")
    subject_name: str = Field(description="Certificate subject name")
    serial_number: str = Field(description="Certificate serial number")
    issuer_name: str = Field(description="Certificate issuer")
    valid_from: datetime = Field(description="Certificate valid from")
    valid_to: datetime = Field(description="Certificate valid to")
    key_usage: List[str] = Field(description="Key usage flags")
    is_active: bool = Field(default=True, description="Certificate active status")

# Validation rules for different prescription types
class PrescriptionValidationRules(SQLModel):
    """Validation rules for different prescription types."""
    
    @staticmethod
    def validate_antimicrobial(items: List[PrescriptionItem]) -> List[str]:
        """Validate antimicrobial prescription according to RDC 471."""
        errors = []
        
        for item in items:
            # Check if medication is antimicrobial
            if any(keyword in item.medication.lower() for keyword in 
                   ['antibiótico', 'antimicrobiano', 'penicilina', 'cefalosporina', 'aminoglicosídeo']):
                
                # RDC 471 validations
                if not item.dosage:
                    errors.append(f"Dosagem obrigatória para {item.medication}")
                
                if not item.frequency:
                    errors.append(f"Frequência obrigatória para {item.medication}")
                
                if not item.duration:
                    errors.append(f"Duração obrigatória para {item.medication}")
                
                # Check duration limits (example: max 14 days for some antibiotics)
                if item.duration and 'dia' in item.duration.lower():
                    try:
                        days = int(item.duration.split()[0])
                        if days > 14:
                            errors.append(f"Duração máxima de 14 dias para {item.medication}")
                    except (ValueError, IndexError):
                        pass
        
        return errors
    
    @staticmethod
    def validate_c1(items: List[PrescriptionItem]) -> List[str]:
        """Validate C1 controlled substance prescription."""
        errors = []
        
        # C1 substances require two copies
        if len(items) == 0:
            errors.append("Prescrição C1 deve conter pelo menos um item")
        
        for item in items:
            # Check if medication is C1 controlled
            c1_substances = ['morfina', 'fentanil', 'metadona', 'codeína', 'tramadol']
            if any(substance in item.medication.lower() for substance in c1_substances):
                
                if not item.dosage:
                    errors.append(f"Dosagem obrigatória para substância controlada {item.medication}")
                
                if not item.frequency:
                    errors.append(f"Frequência obrigatória para substância controlada {item.medication}")
                
                if not item.duration:
                    errors.append(f"Duração obrigatória para substância controlada {item.medication}")
        
        return errors
    
    @staticmethod
    def validate_simple(items: List[PrescriptionItem]) -> List[str]:
        """Validate simple prescription."""
        errors = []
        
        if len(items) == 0:
            errors.append("Prescrição deve conter pelo menos um item")
        
        for item in items:
            if not item.medication:
                errors.append("Nome do medicamento é obrigatório")
            
            if not item.dosage:
                errors.append(f"Dosagem obrigatória para {item.medication}")
        
        return errors

# QR Code data schema
class QRCodeData(SQLModel):
    """QR Code data structure."""
    prescription_id: uuid.UUID
    qr_token: str
    verification_url: str
    signature_hash: str
    created_at: datetime
    expires_at: Optional[datetime] = None
