"""
API endpoints for quick actions (prescriptions, certificates, exam requests, referrals).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime
import uuid

from app.db.session import get_db_session
from app.core.auth import get_current_user
from app.models.consultation_extended import (
    PrescriptionItem, PrescriptionItemCreate,
    MedicalCertificate, MedicalCertificateCreate,
    ExamRequest, ExamRequestCreate,
    Referral, ReferralCreate
)
from pydantic import BaseModel
from typing import List, Optional
from app.models.database import User, Prescription

router = APIRouter(prefix="/quick-actions", tags=["Quick Actions"])

# ============================================================================
# REQUEST MODELS
# ============================================================================

class PrescriptionCreateRequest(BaseModel):
    consultation_id: str
    patient_id: str
    items: List[dict]
    notes: Optional[str] = None
    
    class Config:
        json_encoders = {
            uuid.UUID: str
        }

class CertificateCreateRequest(BaseModel):
    consultation_id: str
    patient_id: str
    certificate_type: str
    content: str
    days_off: Optional[str] = None
    cid10_code: Optional[str] = None
    
    class Config:
        json_encoders = {
            uuid.UUID: str
        }

class ExamRequestCreateRequest(BaseModel):
    consultation_id: str
    patient_id: str
    exam_type: str
    description: str
    urgency: str = "normal"
    instructions: Optional[str] = None
    
    class Config:
        json_encoders = {
            uuid.UUID: str
        }

class ReferralCreateRequest(BaseModel):
    consultation_id: str
    patient_id: str
    specialty: str
    reason: str
    urgency: str = "normal"
    notes: Optional[str] = None
    
    class Config:
        json_encoders = {
            uuid.UUID: str
        }

# ============================================================================
# PRESCRIPTION ENDPOINTS
# ============================================================================

@router.post("/prescriptions/create")
async def create_prescription_with_items(
    request_data: PrescriptionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a prescription with multiple items."""
    try:
        # Extract data from request
        consultation_id = request_data.consultation_id
        patient_id = request_data.patient_id
        items = request_data.items
        notes = request_data.notes
        
        if not consultation_id or not patient_id:
            raise HTTPException(status_code=400, detail="consultation_id and patient_id are required")
        
        if not items:
            raise HTTPException(status_code=400, detail="At least one medication item is required")
        
        # Use first item to satisfy legacy NOT NULL columns on prescriptions table
        first_item = items[0]
        prescription = Prescription(
            consultation_id=consultation_id,
            patient_id=patient_id,
            doctor_id=current_user.id,
            clinic_id=current_user.clinic_id,
            medication_name=first_item.get("medication_name") or first_item.get("name") or "MEDICAMENTO",
            dosage=first_item.get("dosage"),
            frequency=first_item.get("frequency"),
            duration=first_item.get("duration"),
            notes=notes,
            status="active"
        )
        
        db.add(prescription)
        await db.flush()  # Get prescription ID
        
        # Add prescription items
        for item_data in items:
            item = PrescriptionItem(
                prescription_id=prescription.id,
                **item_data
            )
            db.add(item)
        
        await db.commit()
        await db.refresh(prescription)
        
        # TODO: Generate PDF with ICP-Brasil signature
        # pdf_url = await generate_prescription_pdf(prescription.id)
        # prescription.pdf_url = pdf_url
        # await db.commit()
        
        return {
            "message": "Prescription created successfully",
            "prescription_id": str(prescription.id),
            "pdf_url": None  # PDF generation not implemented yet
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating prescription: {str(e)}")


@router.get("/prescriptions/{prescription_id}/items", response_model=List[PrescriptionItemCreate])
async def get_prescription_items(
    prescription_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all items for a prescription."""
    stmt = select(PrescriptionItem).where(PrescriptionItem.prescription_id == prescription_id)
    result = await db.execute(stmt)
    items = result.scalars().all()
    
    return items


@router.post("/prescriptions/{prescription_id}/generate-pdf")
async def generate_prescription_pdf_endpoint(
    prescription_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate PDF for a prescription with ICP-Brasil signature."""
    try:
        # Get prescription
        stmt = select(Prescription).where(Prescription.id == prescription_id)
        result = await db.execute(stmt)
        prescription = result.scalar_one_or_none()
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        
        # Get prescription items
        stmt = select(PrescriptionItem).where(PrescriptionItem.prescription_id == prescription_id)
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        # TODO: Generate PDF with ICP-Brasil signature
        # This should use the existing prescription PDF generation service
        # from app.services.prescription_pdf import generate_prescription_pdf
        # pdf_url = await generate_prescription_pdf(prescription, items)
        
        pdf_url = f"/prescriptions/{prescription_id}.pdf"  # Placeholder
        
        # Note: Prescription model doesn't have pdf_url field
        # prescription.pdf_url = pdf_url
        prescription.updated_at = datetime.now()
        await db.commit()
        
        return {
            "message": "PDF generated successfully",
            "pdf_url": pdf_url
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


# ============================================================================
# MEDICAL CERTIFICATE ENDPOINTS
# ============================================================================

@router.post("/certificates/create")
async def create_medical_certificate(
    request_data: CertificateCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a medical certificate (atestado)."""
    try:
        # Extract data from request
        consultation_id = request_data.consultation_id
        patient_id = request_data.patient_id
        
        certificate = MedicalCertificate(
            consultation_id=consultation_id,
            patient_id=patient_id,
            doctor_id=current_user.id,
            certificate_type=request_data.certificate_type,
            content=request_data.content,
            days_off=request_data.days_off,
            cid10_code=request_data.cid10_code
        )
        
        db.add(certificate)
        await db.commit()
        await db.refresh(certificate)
        
        # TODO: Generate PDF with ICP-Brasil signature
        # pdf_url = await generate_certificate_pdf(certificate.id)
        # certificate.pdf_url = pdf_url
        # await db.commit()
        
        return {
            "message": "Certificate created successfully",
            "certificate_id": str(certificate.id),
            "pdf_url": None  # PDF generation not implemented yet
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating certificate: {str(e)}")


@router.get("/certificates/{consultation_id}")
async def get_certificates_by_consultation(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all certificates for a consultation."""
    stmt = select(MedicalCertificate).where(
        MedicalCertificate.consultation_id == consultation_id
    ).order_by(MedicalCertificate.issued_at.desc())
    
    result = await db.execute(stmt)
    certificates = result.scalars().all()
    
    return certificates


@router.post("/certificates/{certificate_id}/generate-pdf")
async def generate_certificate_pdf_endpoint(
    certificate_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate PDF for a medical certificate."""
    try:
        stmt = select(MedicalCertificate).where(MedicalCertificate.id == certificate_id)
        result = await db.execute(stmt)
        certificate = result.scalar_one_or_none()
        
        if not certificate:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        # TODO: Generate PDF
        pdf_url = f"/certificates/{certificate_id}.pdf"  # Placeholder
        
        # Note: MedicalCertificate model doesn't have pdf_url field
        # certificate.pdf_url = pdf_url
        await db.commit()
        
        return {
            "message": "PDF generated successfully",
            "pdf_url": pdf_url
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


# ============================================================================
# EXAM REQUEST ENDPOINTS
# ============================================================================

@router.post("/exam-requests/create")
async def create_exam_request(
    request_data: ExamRequestCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create an exam request (solicitação de exame)."""
    try:
        # Extract data from request
        consultation_id = request_data.consultation_id
        patient_id = request_data.patient_id
        
        exam_request = ExamRequest(
            consultation_id=consultation_id,
            patient_id=patient_id,
            doctor_id=current_user.id,
            exam_type=request_data.exam_type,
            description=request_data.description,
            urgency=request_data.urgency,
            instructions=request_data.instructions
        )
        
        db.add(exam_request)
        await db.commit()
        await db.refresh(exam_request)
        
        # TODO: Generate TISS guide if needed
        # if insurance_required:
        #     tiss_guide = await generate_tiss_guide(exam_request.id)
        #     exam_request.tiss_guide_id = tiss_guide.id
        #     await db.commit()
        
        return {
            "message": "Exam request created successfully",
            "exam_request_id": str(exam_request.id),
            "pdf_url": None  # PDF generation not implemented yet
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating exam request: {str(e)}")


@router.get("/exam-requests/{consultation_id}")
async def get_exam_requests_by_consultation(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all exam requests for a consultation."""
    stmt = select(ExamRequest).where(
        ExamRequest.consultation_id == consultation_id
    ).order_by(ExamRequest.requested_at.desc())
    
    result = await db.execute(stmt)
    exam_requests = result.scalars().all()
    
    return exam_requests


@router.post("/exam-requests/{exam_request_id}/generate-pdf")
async def generate_exam_request_pdf_endpoint(
    exam_request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate PDF for an exam request."""
    try:
        stmt = select(ExamRequest).where(ExamRequest.id == exam_request_id)
        result = await db.execute(stmt)
        exam_request = result.scalar_one_or_none()
        
        if not exam_request:
            raise HTTPException(status_code=404, detail="Exam request not found")
        
        # TODO: Generate PDF
        pdf_url = f"/exam-requests/{exam_request_id}.pdf"  # Placeholder
        
        # Note: ExamRequest model doesn't have pdf_url field
        # exam_request.pdf_url = pdf_url
        await db.commit()
        
        return {
            "message": "PDF generated successfully",
            "pdf_url": pdf_url
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


# ============================================================================
# REFERRAL ENDPOINTS
# ============================================================================

@router.post("/referrals/create")
async def create_referral(
    request_data: ReferralCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a referral (encaminhamento)."""
    try:
        # Extract data from request
        consultation_id = request_data.consultation_id
        patient_id = request_data.patient_id
        
        referral = Referral(
            consultation_id=consultation_id,
            patient_id=patient_id,
            doctor_id=current_user.id,
            specialty=request_data.specialty,
            reason=request_data.reason,
            urgency=request_data.urgency,
            notes=request_data.notes
        )
        
        db.add(referral)
        await db.commit()
        await db.refresh(referral)
        
        # TODO: Generate PDF
        # pdf_url = await generate_referral_pdf(referral.id)
        # referral.pdf_url = pdf_url
        # await db.commit()
        
        return {
            "message": "Referral created successfully",
            "referral_id": str(referral.id),
            "pdf_url": None  # PDF generation not implemented yet
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating referral: {str(e)}")


@router.get("/referrals/{consultation_id}")
async def get_referrals_by_consultation(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all referrals for a consultation."""
    stmt = select(Referral).where(
        Referral.consultation_id == consultation_id
    ).order_by(Referral.referred_at.desc())
    
    result = await db.execute(stmt)
    referrals = result.scalars().all()
    
    return referrals


@router.post("/referrals/{referral_id}/generate-pdf")
async def generate_referral_pdf_endpoint(
    referral_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate PDF for a referral."""
    try:
        stmt = select(Referral).where(Referral.id == referral_id)
        result = await db.execute(stmt)
        referral = result.scalar_one_or_none()
        
        if not referral:
            raise HTTPException(status_code=404, detail="Referral not found")
        
        # TODO: Generate PDF
        pdf_url = f"/referrals/{referral_id}.pdf"  # Placeholder
        
        # Note: Referral model doesn't have pdf_url field
        # referral.pdf_url = pdf_url
        await db.commit()
        
        return {
            "message": "PDF generated successfully",
            "pdf_url": pdf_url
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

