"""
Print document API endpoints for Prontivus.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid
import json

from app.core.auth import get_current_user, require_medical_records_read
from app.db.session import get_db_session
from app.models import Consultation, Patient, User, PrintLog
from app.schemas import PrintDocumentRequest, PrintConsolidatedRequest

router = APIRouter()

@router.post("/document/{doc_type}/{consultation_id}", status_code=status.HTTP_200_OK)
async def print_document(
    doc_type: str,
    consultation_id: str,
    output_type: str = Query("pdf", description="Output type: pdf or direct_print"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Generate and print a specific document type for a consultation.
    
    Document types: receita_simples, receita_azul, atestado, guia_sadt, 
                   justificativa_exames, encaminhamento
    """
    try:
        # Get consultation data
        consultation_result = await db.execute(
            select(Consultation).where(Consultation.id == consultation_id)
        )
        consultation = consultation_result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        # Get patient data
        patient_result = await db.execute(
            select(Patient).where(Patient.id == consultation.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        # Generate document based on type
        document_data = await _generate_document_data(doc_type, consultation, patient, current_user)
        
        # Log print action
        print_log = PrintLog(
            id=str(uuid.uuid4()),
            consultation_id=consultation_id,
            document_type=doc_type,
            doctor_id=current_user.id,
            output_type=output_type,
            clinic_id=current_user.clinic_id,
            created_at=datetime.utcnow()
        )
        
        db.add(print_log)
        await db.commit()
        
        return {
            "success": True,
            "message": f"Documento {doc_type} gerado com sucesso",
            "document_data": document_data,
            "print_log_id": print_log.id,
            "output_type": output_type
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar documento: {str(e)}")

@router.post("/consolidated/{consultation_id}", status_code=status.HTTP_200_OK)
async def print_consolidated_documents(
    consultation_id: str,
    output_type: str = Query("pdf", description="Output type: pdf or direct_print"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Generate consolidated PDF with all documents for a consultation.
    """
    try:
        # Get consultation data
        consultation_result = await db.execute(
            select(Consultation).where(Consultation.id == consultation_id)
        )
        consultation = consultation_result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        # Get patient data
        patient_result = await db.execute(
            select(Patient).where(Patient.id == consultation.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        # Generate all documents
        all_documents = []
        document_types = ["receita_simples", "receita_azul", "atestado", "guia_sadt", 
                         "justificativa_exames", "encaminhamento"]
        
        for doc_type in document_types:
            if consultation.data.get(doc_type):  # Only include if document exists
                doc_data = await _generate_document_data(doc_type, consultation, patient, current_user)
                all_documents.append({
                    "type": doc_type,
                    "data": doc_data
                })
        
        # Log consolidated print action
        print_log = PrintLog(
            id=str(uuid.uuid4()),
            consultation_id=consultation_id,
            document_type="consolidated",
            doctor_id=current_user.id,
            output_type=output_type,
            clinic_id=current_user.clinic_id,
            created_at=datetime.utcnow()
        )
        
        db.add(print_log)
        await db.commit()
        
        return {
            "success": True,
            "message": "Documentos consolidados gerados com sucesso",
            "documents": all_documents,
            "print_log_id": print_log.id,
            "output_type": output_type
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar documentos consolidados: {str(e)}")

async def _generate_document_data(doc_type: str, consultation: Consultation, 
                                patient: Patient, doctor: User) -> Dict[str, Any]:
    """
    Generate document data based on type and consultation information.
    """
    base_data = {
        "clinic_name": doctor.clinic.name if hasattr(doctor, 'clinic') else "Clínica",
        "clinic_city": doctor.clinic.city if hasattr(doctor, 'clinic') else "Cidade",
        "clinic_logo": doctor.clinic.logo_url if hasattr(doctor, 'clinic') else None,
        "doctor_name": doctor.name,
        "doctor_crm": doctor.crm,
        "patient_name": patient.name,
        "patient_cpf": patient.cpf,
        "patient_birthdate": patient.birthdate.isoformat() if patient.birthdate else None,
        "consultation_date": consultation.created_at.isoformat(),
        "footer": "Prontivus — Cuidado inteligente"
    }
    
    # Add specific data based on document type
    if doc_type == "receita_simples":
        return {
            **base_data,
            "title": "RECEITA MÉDICA",
            "medications": consultation.data.get("prescriptions", []),
            "instructions": consultation.data.get("instructions", "")
        }
    
    elif doc_type == "receita_azul":
        return {
            **base_data,
            "title": "RECEITA DE MEDICAMENTO CONTROLADO",
            "controlled_medications": consultation.data.get("controlled_prescriptions", []),
            "patient_id": patient.id
        }
    
    elif doc_type == "atestado":
        return {
            **base_data,
            "title": "ATESTADO MÉDICO",
            "diagnosis": consultation.data.get("diagnosis", ""),
            "rest_period": consultation.data.get("rest_period", ""),
            "recommendations": consultation.data.get("recommendations", "")
        }
    
    elif doc_type == "guia_sadt":
        return {
            **base_data,
            "title": "GUIA SADT",
            "exam_type": consultation.data.get("exam_type", ""),
            "exam_description": consultation.data.get("exam_description", ""),
            "urgency": consultation.data.get("urgency", "normal")
        }
    
    elif doc_type == "justificativa_exames":
        return {
            **base_data,
            "title": "JUSTIFICATIVA DE EXAMES",
            "exam_justification": consultation.data.get("exam_justification", ""),
            "clinical_findings": consultation.data.get("clinical_findings", ""),
            "exam_requests": consultation.data.get("exam_requests", [])
        }
    
    elif doc_type == "encaminhamento":
        return {
            **base_data,
            "title": "ENCAMINHAMENTO MÉDICO",
            "specialist_type": consultation.data.get("specialist_type", ""),
            "reason": consultation.data.get("referral_reason", ""),
            "urgency": consultation.data.get("urgency", "normal"),
            "observations": consultation.data.get("observations", "")
        }
    
    else:
        raise HTTPException(status_code=400, detail=f"Tipo de documento não suportado: {doc_type}")
