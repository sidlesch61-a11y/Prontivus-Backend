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
    days_off: Optional[int] = None  # Changed from str to int to match database model
    cid10_code: Optional[str] = None
    
    class Config:
        json_encoders = {
            uuid.UUID: str
        }

class ExamRequestCreateRequest(BaseModel):
    consultation_id: str
    patient_id: str
    exam_type: str
    clinical_indication: str  # Changed from description to clinical_indication
    exam_name: Optional[str] = None  # Optional field for exam name
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
        
        # Get related data
        from app.models.database import Patient, User, Clinic
        
        patient_stmt = select(Patient).where(Patient.id == certificate.patient_id)
        patient_result = await db.execute(patient_stmt)
        patient = patient_result.scalar_one_or_none()
        
        doctor_stmt = select(User).where(User.id == certificate.doctor_id)
        doctor_result = await db.execute(doctor_stmt)
        doctor = doctor_result.scalar_one_or_none()
        
        clinic_stmt = select(Clinic).where(Clinic.id == certificate.clinic_id)
        clinic_result = await db.execute(clinic_stmt)
        clinic = clinic_result.scalar_one_or_none()
        
        if not all([patient, doctor, clinic]):
            raise HTTPException(status_code=500, detail="Missing related data")
        
        # Generate PDF content
        from fastapi.responses import Response
        from datetime import datetime
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Atestado Médico - {patient.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #333; padding-bottom: 20px; }}
                .clinic-name {{ font-size: 18px; font-weight: bold; margin-bottom: 5px; }}
                .clinic-info {{ font-size: 12px; color: #666; }}
                .certificate-title {{ font-size: 16px; font-weight: bold; text-align: center; margin: 30px 0; }}
                .content {{ margin: 20px 0; text-align: justify; }}
                .patient-info {{ margin: 15px 0; }}
                .signature-area {{ margin-top: 50px; text-align: center; }}
                .signature-line {{ border-top: 1px solid #333; width: 300px; margin: 20px auto; }}
                .footer {{ margin-top: 30px; font-size: 10px; text-align: center; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="clinic-name">{clinic.name}</div>
                <div class="clinic-info">
                    {clinic.address}<br>
                    {clinic.phone} | {clinic.email}
                </div>
            </div>
            
            <div class="certificate-title">ATESTADO MÉDICO</div>
            
            <div class="content">
                <div class="patient-info">
                    <strong>Paciente:</strong> {patient.name}<br>
                    <strong>Data de Nascimento:</strong> {patient.date_of_birth.strftime('%d/%m/%Y') if patient.date_of_birth else 'Não informado'}<br>
                    <strong>CPF:</strong> {patient.cpf or 'Não informado'}
                </div>
                
                <p>Atesto para os devidos fins que o(a) paciente acima identificado(a) necessita de {certificate.days_off or '0'} dias de afastamento de suas atividades, devido a:</p>
                
                <p style="margin: 20px 0; padding: 15px; background-color: #f5f5f5; border-left: 4px solid #007bff;">
                    {certificate.content}
                </p>
                
                {f'<p><strong>CID-10:</strong> {certificate.cid10_code}</p>' if certificate.cid10_code else ''}
                
                <p>Este atestado é válido por 30 dias a partir da data de emissão.</p>
            </div>
            
            <div class="signature-area">
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
                <div class="signature-line"></div>
                <p><strong>Dr(a). {doctor.full_name or doctor.name}</strong><br>
                CRM: {doctor.license_number or 'N/A'}<br>
                {clinic.name}</p>
            </div>
            
            <div class="footer">
                <p>Este documento foi gerado eletronicamente e possui validade legal conforme legislação vigente.</p>
            </div>
        </body>
        </html>
        """
        
        # Convert HTML to PDF using weasyprint
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            font_config = FontConfiguration()
            html_doc = HTML(string=html_content)
            css_doc = CSS(string="""
                @page { size: A4; margin: 2cm; }
                body { font-family: 'Times New Roman', serif; }
            """, font_config=font_config)
            
            pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])
            
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=atestado_{certificate_id}.pdf"
                }
            )
            
        except ImportError:
            # Fallback: return HTML content if weasyprint is not available
            return Response(
                content=html_content,
                media_type="text/html",
                headers={
                    "Content-Disposition": f"attachment; filename=atestado_{certificate_id}.html"
                }
            )
        
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
            exam_name=request_data.exam_name or request_data.clinical_indication,  # Use exam_name if provided, otherwise use clinical_indication
            clinical_indication=request_data.clinical_indication,  # Use clinical_indication directly
            urgency=request_data.urgency
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
        
        # Get related data
        from app.models.database import Patient, User, Clinic
        
        patient_stmt = select(Patient).where(Patient.id == exam_request.patient_id)
        patient_result = await db.execute(patient_stmt)
        patient = patient_result.scalar_one_or_none()
        
        doctor_stmt = select(User).where(User.id == exam_request.doctor_id)
        doctor_result = await db.execute(doctor_stmt)
        doctor = doctor_result.scalar_one_or_none()
        
        clinic_stmt = select(Clinic).where(Clinic.id == exam_request.clinic_id)
        clinic_result = await db.execute(clinic_stmt)
        clinic = clinic_result.scalar_one_or_none()
        
        if not all([patient, doctor, clinic]):
            raise HTTPException(status_code=500, detail="Missing related data")
        
        # Generate PDF content
        from fastapi.responses import Response
        from datetime import datetime
        
        urgency_colors = {
            "urgent": "#dc3545",
            "normal": "#28a745", 
            "low": "#ffc107"
        }
        
        urgency_labels = {
            "urgent": "URGENTE",
            "normal": "NORMAL",
            "low": "BAIXA"
        }
        
        urgency_color = urgency_colors.get(exam_request.urgency, "#28a745")
        urgency_label = urgency_labels.get(exam_request.urgency, "NORMAL")
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Solicitação de Exame - {patient.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #333; padding-bottom: 20px; }}
                .clinic-name {{ font-size: 18px; font-weight: bold; margin-bottom: 5px; }}
                .clinic-info {{ font-size: 12px; color: #666; }}
                .exam-title {{ font-size: 16px; font-weight: bold; text-align: center; margin: 30px 0; }}
                .content {{ margin: 20px 0; text-align: justify; }}
                .patient-info {{ margin: 15px 0; }}
                .exam-details {{ margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid {urgency_color}; }}
                .urgency-badge {{ display: inline-block; padding: 4px 8px; background-color: {urgency_color}; color: white; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                .signature-area {{ margin-top: 50px; text-align: center; }}
                .signature-line {{ border-top: 1px solid #333; width: 300px; margin: 20px auto; }}
                .footer {{ margin-top: 30px; font-size: 10px; text-align: center; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="clinic-name">{clinic.name}</div>
                <div class="clinic-info">
                    {clinic.address}<br>
                    {clinic.phone} | {clinic.email}
                </div>
            </div>
            
            <div class="exam-title">SOLICITAÇÃO DE EXAME MÉDICO</div>
            
            <div class="content">
                <div class="patient-info">
                    <strong>Paciente:</strong> {patient.name}<br>
                    <strong>Data de Nascimento:</strong> {patient.date_of_birth.strftime('%d/%m/%Y') if patient.date_of_birth else 'Não informado'}<br>
                    <strong>CPF:</strong> {patient.cpf or 'Não informado'}<br>
                    <strong>Convênio:</strong> {patient.insurance_provider or 'Particular'}
                </div>
                
                <div class="exam-details">
                    <h3>Detalhes do Exame</h3>
                    <p><strong>Tipo de Exame:</strong> {exam_request.exam_type}</p>
                    {f'<p><strong>Nome do Exame:</strong> {exam_request.exam_name}</p>' if exam_request.exam_name else ''}
                    <p><strong>Urgência:</strong> <span class="urgency-badge">{urgency_label}</span></p>
                    <p><strong>Indicação Clínica:</strong></p>
                    <p style="margin: 10px 0; padding: 10px; background-color: white; border-radius: 4px;">
                        {exam_request.clinical_indication}
                    </p>
                    {f'<p><strong>Instruções Especiais:</strong><br>{exam_request.instructions}</p>' if exam_request.instructions else ''}
                </div>
                
                <p><strong>Data da Solicitação:</strong> {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
            </div>
            
            <div class="signature-area">
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
                <div class="signature-line"></div>
                <p><strong>Dr(a). {doctor.full_name or doctor.name}</strong><br>
                CRM: {doctor.license_number or 'N/A'}<br>
                {clinic.name}</p>
            </div>
            
            <div class="footer">
                <p>Este documento foi gerado eletronicamente e possui validade legal conforme legislação vigente.</p>
                <p>Validade: 30 dias a partir da data de emissão</p>
            </div>
        </body>
        </html>
        """
        
        # Convert HTML to PDF using weasyprint
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            font_config = FontConfiguration()
            html_doc = HTML(string=html_content)
            css_doc = CSS(string="""
                @page { size: A4; margin: 2cm; }
                body { font-family: 'Times New Roman', serif; }
            """, font_config=font_config)
            
            pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])
            
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=solicitacao_exame_{exam_request_id}.pdf"
                }
            )
            
        except ImportError:
            # Fallback: return HTML content if weasyprint is not available
            return Response(
                content=html_content,
                media_type="text/html",
                headers={
                    "Content-Disposition": f"attachment; filename=solicitacao_exame_{exam_request_id}.html"
                }
            )
        
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
        
        # Get related data
        from app.models.database import Patient, User, Clinic
        
        patient_stmt = select(Patient).where(Patient.id == referral.patient_id)
        patient_result = await db.execute(patient_stmt)
        patient = patient_result.scalar_one_or_none()
        
        doctor_stmt = select(User).where(User.id == referral.doctor_id)
        doctor_result = await db.execute(doctor_stmt)
        doctor = doctor_result.scalar_one_or_none()
        
        clinic_stmt = select(Clinic).where(Clinic.id == referral.clinic_id)
        clinic_result = await db.execute(clinic_stmt)
        clinic = clinic_result.scalar_one_or_none()
        
        if not all([patient, doctor, clinic]):
            raise HTTPException(status_code=500, detail="Missing related data")
        
        # Generate PDF content
        from fastapi.responses import Response
        from datetime import datetime
        
        urgency_colors = {
            "urgent": "#dc3545",
            "normal": "#28a745", 
            "low": "#ffc107"
        }
        
        urgency_labels = {
            "urgent": "URGENTE",
            "normal": "NORMAL",
            "low": "BAIXA"
        }
        
        urgency_color = urgency_colors.get(referral.urgency, "#28a745")
        urgency_label = urgency_labels.get(referral.urgency, "NORMAL")
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Encaminhamento Médico - {patient.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #333; padding-bottom: 20px; }}
                .clinic-name {{ font-size: 18px; font-weight: bold; margin-bottom: 5px; }}
                .clinic-info {{ font-size: 12px; color: #666; }}
                .referral-title {{ font-size: 16px; font-weight: bold; text-align: center; margin: 30px 0; }}
                .content {{ margin: 20px 0; text-align: justify; }}
                .patient-info {{ margin: 15px 0; }}
                .referral-details {{ margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid {urgency_color}; }}
                .urgency-badge {{ display: inline-block; padding: 4px 8px; background-color: {urgency_color}; color: white; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                .signature-area {{ margin-top: 50px; text-align: center; }}
                .signature-line {{ border-top: 1px solid #333; width: 300px; margin: 20px auto; }}
                .footer {{ margin-top: 30px; font-size: 10px; text-align: center; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="clinic-name">{clinic.name}</div>
                <div class="clinic-info">
                    {clinic.address}<br>
                    {clinic.phone} | {clinic.email}
                </div>
            </div>
            
            <div class="referral-title">ENCAMINHAMENTO MÉDICO</div>
            
            <div class="content">
                <div class="patient-info">
                    <strong>Paciente:</strong> {patient.name}<br>
                    <strong>Data de Nascimento:</strong> {patient.date_of_birth.strftime('%d/%m/%Y') if patient.date_of_birth else 'Não informado'}<br>
                    <strong>CPF:</strong> {patient.cpf or 'Não informado'}<br>
                    <strong>Convênio:</strong> {patient.insurance_provider or 'Particular'}
                </div>
                
                <div class="referral-details">
                    <h3>Detalhes do Encaminhamento</h3>
                    <p><strong>Especialidade:</strong> {referral.specialty}</p>
                    <p><strong>Urgência:</strong> <span class="urgency-badge">{urgency_label}</span></p>
                    <p><strong>Motivo do Encaminhamento:</strong></p>
                    <p style="margin: 10px 0; padding: 10px; background-color: white; border-radius: 4px;">
                        {referral.reason}
                    </p>
                    {f'<p><strong>Observações Adicionais:</strong><br>{referral.notes}</p>' if referral.notes else ''}
                </div>
                
                <p><strong>Data do Encaminhamento:</strong> {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
                
                <div style="margin: 30px 0; padding: 15px; background-color: #e3f2fd; border-radius: 4px;">
                    <h4>Instruções para o Paciente:</h4>
                    <ul>
                        <li>Apresente este encaminhamento na especialidade indicada</li>
                        <li>Leve todos os exames e documentos relacionados ao caso</li>
                        <li>Este encaminhamento é válido por 30 dias</li>
                        <li>Em caso de urgência, procure atendimento imediato</li>
                    </ul>
                </div>
            </div>
            
            <div class="signature-area">
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
                <div class="signature-line"></div>
                <p><strong>Dr(a). {doctor.full_name or doctor.name}</strong><br>
                CRM: {doctor.license_number or 'N/A'}<br>
                {clinic.name}</p>
            </div>
            
            <div class="footer">
                <p>Este documento foi gerado eletronicamente e possui validade legal conforme legislação vigente.</p>
                <p>Validade: 30 dias a partir da data de emissão</p>
            </div>
        </body>
        </html>
        """
        
        # Convert HTML to PDF using weasyprint
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            font_config = FontConfiguration()
            html_doc = HTML(string=html_content)
            css_doc = CSS(string="""
                @page { size: A4; margin: 2cm; }
                body { font-family: 'Times New Roman', serif; }
            """, font_config=font_config)
            
            pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])
            
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=encaminhamento_{referral_id}.pdf"
                }
            )
            
        except ImportError:
            # Fallback: return HTML content if weasyprint is not available
            return Response(
                content=html_content,
                media_type="text/html",
                headers={
                    "Content-Disposition": f"attachment; filename=encaminhamento_{referral_id}.html"
                }
            )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

