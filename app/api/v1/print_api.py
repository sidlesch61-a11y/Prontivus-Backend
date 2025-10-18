"""
Document printing API endpoints for Prontivus.
Supports PDF generation and direct printer output for medical documents.
"""

import uuid
import io
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.db.session import get_db_session
from app.models import Consultation, Patient, User, Clinic
from app.services.pdf_generator import PDFGenerator
from app.services.print_service import PrintService

router = APIRouter()


class PrintLogCreate(BaseModel):
    """Print log creation schema."""
    document_type: str
    consultation_id: str
    doctor_id: str
    output_type: str  # 'pdf' or 'direct_print'
    success: bool
    error_message: Optional[str] = None


class PrintLogResponse(BaseModel):
    """Print log response schema."""
    id: str
    document_type: str
    consultation_id: str
    doctor_id: str
    output_type: str
    success: bool
    error_message: Optional[str] = None
    created_at: datetime
    doctor_name: Optional[str] = None


class PrintDocumentRequest(BaseModel):
    """Print document request schema."""
    output_type: str = "pdf"  # 'pdf' or 'direct_print'
    include_header: bool = True
    include_footer: bool = True
    include_signature: bool = True


@router.get("/document/{document_type}/{consultation_id}")
async def print_document(
    document_type: str,
    consultation_id: str,
    output_type: str = Query("pdf", description="Output type: pdf or direct_print"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Print a specific document type for a consultation.
    
    Document types:
    - receita_simples: Simple prescription
    - receita_azul: Controlled prescription
    - atestado: Medical certificate
    - guia_sadt: SADT guide
    - justificativa_exames: Exam justification
    - encaminhamento: Medical referral
    """
    try:
        # Validate document type
        valid_types = [
            "receita_simples", "receita_azul", "atestado", 
            "guia_sadt", "justificativa_exames", "encaminhamento"
        ]
        if document_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de documento inválido. Tipos válidos: {', '.join(valid_types)}"
            )
        
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
            select(Clinic).where(Clinic.id == current_user.clinic_id)
        )
        clinic = clinic_result.scalar_one_or_none()
        
        if not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clínica não encontrada"
            )
        
        # Generate document
        pdf_generator = PDFGenerator()
        print_service = PrintService()
        
        if output_type == "pdf":
            # Generate PDF
            pdf_content = await pdf_generator.generate_document(
                document_type=document_type,
                consultation=consultation,
                patient=patient,
                doctor=doctor,
                clinic=clinic
            )
            
            # Log print action
            await print_service.log_print_action(
                db=db,
                document_type=document_type,
                consultation_id=consultation_id,
                doctor_id=current_user.id,
                output_type="pdf",
                success=True
            )
            
            return StreamingResponse(
                io.BytesIO(pdf_content),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={document_type}_{consultation_id}.pdf"
                }
            )
        
        elif output_type == "direct_print":
            # Direct print to printer
            success = await print_service.print_direct(
                document_type=document_type,
                consultation=consultation,
                patient=patient,
                doctor=doctor,
                clinic=clinic
            )
            
            # Log print action
            await print_service.log_print_action(
                db=db,
                document_type=document_type,
                consultation_id=consultation_id,
                doctor_id=current_user.id,
                output_type="direct_print",
                success=success
            )
            
            if success:
                return {"message": "Documento enviado para impressão com sucesso"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Erro ao enviar documento para impressão"
                )
        
    except HTTPException:
        raise
    except Exception as e:
        # Log error
        await print_service.log_print_action(
            db=db,
            document_type=document_type,
            consultation_id=consultation_id,
            doctor_id=current_user.id,
            output_type=output_type,
            success=False,
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar documento: {str(e)}"
        )


@router.get("/consolidated/{consultation_id}")
async def print_consolidated_documents(
    consultation_id: str,
    output_type: str = Query("pdf", description="Output type: pdf or direct_print"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Print all documents for a consultation in a consolidated PDF.
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
        
        # Get related data
        patient_result = await db.execute(
            select(Patient).where(Patient.id == consultation.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        
        doctor_result = await db.execute(
            select(User).where(User.id == consultation.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        
        clinic_result = await db.execute(
            select(Clinic).where(Clinic.id == current_user.clinic_id)
        )
        clinic = clinic_result.scalar_one_or_none()
        
        if not all([patient, doctor, clinic]):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dados da consulta incompletos"
            )
        
        # Generate consolidated PDF
        pdf_generator = PDFGenerator()
        print_service = PrintService()
        
        if output_type == "pdf":
            # Generate consolidated PDF
            pdf_content = await pdf_generator.generate_consolidated_documents(
                consultation=consultation,
                patient=patient,
                doctor=doctor,
                clinic=clinic
            )
            
            # Log print action
            await print_service.log_print_action(
                db=db,
                document_type="consolidated",
                consultation_id=consultation_id,
                doctor_id=current_user.id,
                output_type="pdf",
                success=True
            )
            
            return StreamingResponse(
                io.BytesIO(pdf_content),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=consolidated_{consultation_id}.pdf"
                }
            )
        
        elif output_type == "direct_print":
            # Direct print consolidated documents
            success = await print_service.print_consolidated_direct(
                consultation=consultation,
                patient=patient,
                doctor=doctor,
                clinic=clinic
            )
            
            # Log print action
            await print_service.log_print_action(
                db=db,
                document_type="consolidated",
                consultation_id=consultation_id,
                doctor_id=current_user.id,
                output_type="direct_print",
                success=success
            )
            
            if success:
                return {"message": "Documentos consolidados enviados para impressão com sucesso"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Erro ao enviar documentos consolidados para impressão"
                )
        
    except HTTPException:
        raise
    except Exception as e:
        # Log error
        await print_service.log_print_action(
            db=db,
            document_type="consolidated",
            consultation_id=consultation_id,
            doctor_id=current_user.id,
            output_type=output_type,
            success=False,
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar documentos consolidados: {str(e)}"
        )


@router.get("/logs")
async def get_print_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get print logs for the current clinic."""
    try:
        # This would require a PrintLog model to be created
        # For now, return a placeholder response
        return {
            "items": [],
            "total": 0,
            "page": page,
            "size": size,
            "pages": 0
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar logs de impressão: {str(e)}"
        )