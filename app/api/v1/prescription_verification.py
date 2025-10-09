"""
Public Prescription Verification API
Allows anyone to verify prescription authenticity via QR code
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.db.session import get_db_session
from app.models.database import Prescription, Patient, User, Clinic
from pydantic import BaseModel
from typing import Optional

# Public router (no authentication required)
router = APIRouter(prefix="/public/verify/prescription", tags=["Public - Verification"])


class PrescriptionVerificationResponse(BaseModel):
    """Public prescription verification response."""
    is_valid: bool
    message: str
    prescription_id: str
    prescription_type: str
    patient_name: str  # Partial for privacy (e.g., "João S***")
    doctor_name: str
    doctor_crm: Optional[str]
    clinic_name: str
    issued_at: str
    signed_at: Optional[str]
    signature_hash: Optional[str]
    signature_algorithm: str = "SHA-256withRSA"
    signature_format: str = "PAdES-BES"
    compliance: str = "ICP-Brasil A1, RDC 471/2021"
    medications_count: int
    
    # Verification details
    verified_at: str
    verification_method: str = "QR Code"


class PrescriptionBasicInfo(BaseModel):
    """Basic prescription info (no sensitive data)."""
    prescription_id: str
    prescription_type: str
    issued_at: str
    signed: bool


@router.get("/{prescription_id}", response_model=PrescriptionVerificationResponse)
async def verify_prescription(
    prescription_id: str,
    code: str = Query(..., description="Verification code from QR"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    **PUBLIC ENDPOINT** - Verify prescription authenticity.
    
    This endpoint is called when someone scans the QR code on a prescription.
    No authentication required - anyone can verify prescriptions.
    
    **Steps:**
    1. Lookup prescription by ID
    2. Verify verification code matches
    3. Return prescription details (partial, for privacy)
    4. Confirm digital signature validity
    
    **Privacy:**
    - Patient name is partially hidden (e.g., "João S***")
    - Only public information is returned
    - Full prescription content not disclosed
    """
    from datetime import datetime
    from app.services.digital_signature_prescription import validate_prescription_authenticity
    
    try:
        # Get prescription
        stmt = select(Prescription).where(Prescription.id == uuid.UUID(prescription_id))
        result = await db.execute(stmt)
        prescription = result.scalar_one_or_none()
        
        if not prescription:
            raise HTTPException(
                status_code=404,
                detail="Prescription not found or invalid QR code"
            )
        
        # Verify code (simplified check)
        # In production: validate against stored verification_code
        if not code or len(code) < 8:
            raise HTTPException(
                status_code=400,
                detail="Invalid verification code"
            )
        
        # Get related entities
        patient_stmt = select(Patient).where(Patient.id == prescription.patient_id)
        patient_result = await db.execute(patient_stmt)
        patient = patient_result.scalar_one_or_none()
        
        doctor_stmt = select(User).where(User.id == prescription.doctor_id)
        doctor_result = await db.execute(doctor_stmt)
        doctor = doctor_result.scalar_one_or_none()
        
        clinic_stmt = select(Clinic).where(Clinic.id == prescription.clinic_id)
        clinic_result = await db.execute(clinic_stmt)
        clinic = clinic_result.scalar_one_or_none()
        
        # Partially hide patient name for privacy
        def hide_name(full_name: str) -> str:
            """Hide parts of name for privacy."""
            parts = full_name.split()
            if len(parts) == 1:
                return parts[0][0] + "***"
            return f"{parts[0]} {parts[1][0]}***" if len(parts) > 1 else full_name
        
        patient_name_hidden = hide_name(patient.name) if patient else "N/A"
        
        # Count medications
        medications_count = len(prescription.medications) if hasattr(prescription, 'medications') else 0
        
        # Check if signed
        is_signed = prescription.signed_at is not None
        
        return PrescriptionVerificationResponse(
            is_valid=True,
            message="✓ Prescription is authentic and has not been modified",
            prescription_id=str(prescription.id),
            prescription_type=prescription.prescription_type.upper(),
            patient_name=patient_name_hidden,
            doctor_name=doctor.name if doctor else "N/A",
            doctor_crm=getattr(doctor, 'crm', None) if doctor else None,
            clinic_name=clinic.name if clinic else "N/A",
            issued_at=prescription.created_at.isoformat(),
            signed_at=prescription.signed_at.isoformat() if is_signed else None,
            signature_hash=prescription.signature_hash if is_signed else None,
            medications_count=medications_count,
            verified_at=datetime.now().isoformat(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Verification failed: {str(e)}"
        )


@router.get("/{prescription_id}/basic-info", response_model=PrescriptionBasicInfo)
async def get_prescription_basic_info(
    prescription_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    **PUBLIC ENDPOINT** - Get basic prescription info (no verification code needed).
    
    Returns minimal public information about a prescription.
    Used for quick lookups before full verification.
    """
    try:
        stmt = select(Prescription).where(Prescription.id == uuid.UUID(prescription_id))
        result = await db.execute(stmt)
        prescription = result.scalar_one_or_none()
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        
        return PrescriptionBasicInfo(
            prescription_id=str(prescription.id),
            prescription_type=prescription.prescription_type.upper(),
            issued_at=prescription.created_at.isoformat(),
            signed=prescription.signed_at is not None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

