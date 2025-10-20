"""
PDF Generation API endpoints for Prontivus.
Provides JSON responses with PDF URLs for frontend consumption.
"""

import uuid
import io
import base64
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.db.session import get_db_session
from app.models import Consultation, Patient, User, Clinic
from app.services.pdf_generator import PDFGenerator

router = APIRouter()


class PDFGenerationRequest(BaseModel):
    """PDF generation request schema."""
    document_type: str
    consultation_id: str
    output_type: str = "pdf"  # 'pdf' or 'base64'


class PDFGenerationResponse(BaseModel):
    """PDF generation response schema."""
    success: bool
    document_type: str
    consultation_id: str
    pdf_url: Optional[str] = None
    pdf_base64: Optional[str] = None
    filename: str
    message: str
    generated_at: datetime


@router.post("/generate", response_model=PDFGenerationResponse)
async def generate_pdf(
    request: PDFGenerationRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Generate PDF and return JSON response with PDF data.
    
    Document types:
    - receita_simples: Simple prescription
    - receita_azul: Controlled prescription
    - atestado: Medical certificate
    - guia_sadt: SADT guide
    - justificativa_exames: Exam justification
    - encaminhamento: Medical referral
    - guia_exame: Exam guide
    - encaminhamento_especialista: Specialist referral
    """
    try:
        # Validate document type
        valid_types = [
            "receita_simples", "receita_azul", "atestado", 
            "guia_sadt", "justificativa_exames", "encaminhamento",
            "guia_exame", "encaminhamento_especialista"
        ]
        if request.document_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de documento inválido. Tipos válidos: {', '.join(valid_types)}"
            )
        
        # Get consultation data
        consultation_result = await db.execute(
            select(Consultation).where(
                Consultation.id == request.consultation_id,
                Consultation.clinic_id == current_user.clinic_id
            )
        )
        consultation = consultation_result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consulta não encontrada"
            )
        
        # Get patient data
        patient_result = await db.execute(
            select(Patient).where(Patient.id == consultation.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paciente não encontrado"
            )
        
        # Get doctor data
        doctor_result = await db.execute(
            select(User).where(User.id == consultation.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Médico não encontrado"
            )
        
        # Get clinic data
        clinic_result = await db.execute(
            select(Clinic).where(Clinic.id == consultation.clinic_id)
        )
        clinic = clinic_result.scalar_one_or_none()
        
        if not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clínica não encontrada"
            )
        
        # Generate PDF
        pdf_generator = PDFGenerator()
        pdf_content = await pdf_generator.generate_document(
            document_type=document_type,
            consultation=consultation,
            patient=patient,
            doctor=doctor,
            clinic=clinic
        )
        
        # Create filename
        filename = f"{document_type}_{patient.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Prepare response based on output type
        if output_type == "base64":
            # Convert PDF to base64 for frontend consumption
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            return PDFGenerationResponse(
                success=True,
                document_type=request.document_type,
                consultation_id=request.consultation_id,
                pdf_base64=pdf_base64,
                filename=filename,
                message="PDF gerado com sucesso",
                generated_at=datetime.now()
            )
        else:
            # For now, return base64 even for 'pdf' type to ensure frontend compatibility
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            return PDFGenerationResponse(
                success=True,
                document_type=request.document_type,
                consultation_id=request.consultation_id,
                pdf_base64=pdf_base64,
                filename=filename,
                message="PDF gerado com sucesso",
                generated_at=datetime.now()
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar PDF: {str(e)}"
        )


@router.post("/generate-consolidated", response_model=PDFGenerationResponse)
async def generate_consolidated_pdf(
    consultation_id: str,
    output_type: str = Query("pdf", description="Output type: pdf or base64"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Generate consolidated PDF with all documents for a consultation.
    """
    try:
        # Get consultation data
        consultation_result = await db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.clinic_id == current_user.clinic_id
            )
        )
        consultation = consultation_result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consulta não encontrada"
            )
        
        # Get patient data
        patient_result = await db.execute(
            select(Patient).where(Patient.id == consultation.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paciente não encontrado"
            )
        
        # Get doctor data
        doctor_result = await db.execute(
            select(User).where(User.id == consultation.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Médico não encontrado"
            )
        
        # Get clinic data
        clinic_result = await db.execute(
            select(Clinic).where(Clinic.id == consultation.clinic_id)
        )
        clinic = clinic_result.scalar_one_or_none()
        
        if not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clínica não encontrada"
            )
        
        # Generate consolidated PDF
        pdf_generator = PDFGenerator()
        pdf_content = await pdf_generator.generate_consolidated_documents(
            consultation=consultation,
            patient=patient,
            doctor=doctor,
            clinic=clinic
        )
        
        # Create filename
        filename = f"documentos_consolidados_{patient.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Convert PDF to base64 for frontend consumption
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
        
        return PDFGenerationResponse(
            success=True,
            document_type="consolidated",
            consultation_id=consultation_id,
            pdf_base64=pdf_base64,
            filename=filename,
            message="PDF consolidado gerado com sucesso",
            generated_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar PDF consolidado: {str(e)}"
        )


@router.get("/document-types")
async def get_document_types():
    """Get list of available document types."""
    return {
        "document_types": [
            {
                "id": "receita_simples",
                "name": "Receita Simples",
                "description": "Prescrição médica padrão"
            },
            {
                "id": "receita_azul",
                "name": "Receita Azul (Controlada)",
                "description": "Prescrição para medicamentos controlados"
            },
            {
                "id": "atestado",
                "name": "Atestado Médico",
                "description": "Atestado de saúde"
            },
            {
                "id": "guia_sadt",
                "name": "Guia SADT",
                "description": "Solicitação de procedimentos"
            },
            {
                "id": "justificativa_exames",
                "name": "Justificativa de Exames",
                "description": "Justificativas clínicas"
            },
            {
                "id": "encaminhamento",
                "name": "Encaminhamento Médico",
                "description": "Encaminhamentos gerais"
            },
            {
                "id": "guia_exame",
                "name": "Guia de Exames",
                "description": "Guia para exames laboratoriais e de imagem"
            },
            {
                "id": "encaminhamento_especialista",
                "name": "Encaminhamento para Especialista",
                "description": "Encaminhamento para especialidades médicas"
            }
        ]
    }
