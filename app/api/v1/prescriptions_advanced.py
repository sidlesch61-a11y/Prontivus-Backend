"""
Advanced Prescription API with PDF Generation and Digital Signature
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.db.session import get_db_session
from app.core.auth import AuthDependencies
from app.models.database import Prescription, Patient, User, Clinic
from pydantic import BaseModel

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions - Advanced"])


class PrescriptionGeneratePDFRequest(BaseModel):
    """Request to generate and sign prescription PDF."""
    pass  # No body needed, uses prescription ID from URL


class PrescriptionGeneratePDFResponse(BaseModel):
    """Response after PDF generation and signature."""
    success: bool
    message: str
    pdf_url: str
    signed_at: str
    signature_hash: str
    verification_code: str
    qr_code_url: str


@router.post("/{prescription_id}/generate-pdf", response_model=PrescriptionGeneratePDFResponse)
async def generate_and_sign_prescription_pdf(
    prescription_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(AuthDependencies.get_current_user),
):
    """
    Generate PDF and apply digital signature to prescription.
    
    **Workflow:**
    1. Generate PDF with clinic branding
    2. Apply ICP-Brasil A1 digital signature (PAdES format)
    3. Embed QR code for verification
    4. Store signed PDF
    5. Return PDF URL and verification info
    
    **Only doctors can sign prescriptions.**
    """
    # Check if user is doctor
    user_role = getattr(current_user, "role", "").lower()
    if user_role not in ["doctor", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors can sign prescriptions"
        )
    
    # Get prescription with related data
    stmt = select(Prescription).where(Prescription.id == uuid.UUID(prescription_id))
    result = await db.execute(stmt)
    prescription = result.scalar_one_or_none()
    
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    
    # Check if already signed
    if prescription.signed_at:
        raise HTTPException(status_code=400, detail="Prescription already signed")
    
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
    
    if not all([patient, doctor, clinic]):
        raise HTTPException(status_code=500, detail="Missing related data")
    
    try:
        # Generate and sign PDF
        from app.services.digital_signature_prescription import sign_and_generate_prescription_pdf
        
        pdf_bytes, signature_metadata = await sign_and_generate_prescription_pdf(
            prescription,
            clinic,
            doctor,
            patient,
            db
        )
        
        # Generate QR code URL
        verification_code = signature_metadata['verification_code']
        qr_url = f"https://prontivus.com/verify/prescription/{prescription_id}?code={verification_code}"
        
        return PrescriptionGeneratePDFResponse(
            success=True,
            message="Prescription signed successfully",
            pdf_url=prescription.pdf_url,
            signed_at=prescription.signed_at.isoformat(),
            signature_hash=prescription.signature_hash,
            verification_code=verification_code,
            qr_code_url=qr_url
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


@router.get("/{prescription_id}/pdf")
async def download_prescription_pdf(
    prescription_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(AuthDependencies.get_current_user),
):
    """
    Download signed prescription PDF.
    
    Returns the digitally signed PDF file.
    """
    from fastapi.responses import Response
    from app.services.prescription_pdf import generate_prescription_pdf
    
    # Get prescription
    stmt = select(Prescription).where(Prescription.id == uuid.UUID(prescription_id))
    result = await db.execute(stmt)
    prescription = result.scalar_one_or_none()
    
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    
    # Get related entities (same as above, simplified for demo)
    # In production: retrieve from S3/MinIO
    
    # For demo: generate PDF on-the-fly
    # In production: return stored signed PDF
    try:
        patient_stmt = select(Patient).where(Patient.id == prescription.patient_id)
        patient_result = await db.execute(patient_stmt)
        patient = patient_result.scalar_one_or_none()
        
        doctor_stmt = select(User).where(User.id == prescription.doctor_id)
        doctor_result = await db.execute(doctor_stmt)
        doctor = doctor_result.scalar_one_or_none()
        
        clinic_stmt = select(Clinic).where(Clinic.id == prescription.clinic_id)
        clinic_result = await db.execute(clinic_stmt)
        clinic = clinic_result.scalar_one_or_none()
        
        pdf_bytes = generate_prescription_pdf(prescription, clinic, doctor, patient)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=prescription_{prescription_id}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

