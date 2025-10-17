"""
Print API endpoints for medical documents.
"""

import os
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.db.session import get_db_session
from app.models.database import User
from app.api.v1.auth import get_current_user
from app.models.print_models import PrintRequest, PrintResponse, PrintLog
from app.models.database import Consultation

# Conditional import for enhanced print service
try:
    from app.services.enhanced_print_service import enhanced_print_service
    PRINT_SERVICE_AVAILABLE = True
except ImportError:
    PRINT_SERVICE_AVAILABLE = False
    enhanced_print_service = None

router = APIRouter()


@router.post("/print/document/{document_type}/{consultation_id}", response_model=PrintResponse)
async def print_document(
    document_type: str,
    consultation_id: UUID,
    preview: bool = Query(False, description="Se deve gerar preview em vez de imprimir"),
    printer_name: str = Query(None, description="Nome da impressora"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Imprimir documento médico.
    
    Tipos de documento suportados:
    - prescription: Receita médica
    - prescription_controlled: Receita azul (controlada)
    - certificate: Atestado médico
    - exam_request: Solicitação de exame
    - referral: Encaminhamento médico
    - sadt_guide: Guia SADT
    """
    
    # Validate document type
    valid_types = ["prescription", "prescription_controlled", "certificate", "exam_request", "referral", "sadt_guide"]
    if document_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de documento inválido. Tipos válidos: {', '.join(valid_types)}"
        )
    
    if not PRINT_SERVICE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de impressão não disponível. weasyprint não está instalado."
        )
    
    try:
        result = await enhanced_print_service.print_document(
            db=db,
            consultation_id=consultation_id,
            document_type=document_type,
            printed_by=current_user.id,
            preview=preview,
            printer_name=printer_name
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar impressão: {str(e)}"
        )


@router.post("/print/consolidated/{consultation_id}", response_model=PrintResponse)
async def print_consolidated_documents(
    consultation_id: UUID,
    document_types: List[str] = Query(default=None, description="Tipos de documentos para consolidar"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Imprimir todos os documentos consolidados em um único PDF.
    """
    
    if not PRINT_SERVICE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de impressão não disponível. weasyprint não está instalado."
        )
    
    try:
        result = await enhanced_print_service.print_consolidated_documents(
            db=db,
            consultation_id=consultation_id,
            printed_by=current_user.id,
            document_types=document_types
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar impressão consolidada: {str(e)}"
        )


@router.get("/print/preview/{filename}")
async def get_preview_file(filename: str):
    """Obter arquivo de preview para visualização."""
    file_path = f"temp_prints/{filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo de preview não encontrado"
        )
    
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename
    )


@router.get("/print/logs", response_model=List[PrintLog])
async def get_print_logs(
    consultation_id: UUID = Query(None, description="ID da consulta"),
    document_type: str = Query(None, description="Tipo de documento"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Obter logs de impressão."""
    
    query = select(PrintLog)
    
    if consultation_id:
        query = query.where(PrintLog.consultation_id == consultation_id)
    
    if document_type:
        query = query.where(PrintLog.document_type == document_type)
    
    # Only show logs for current user's clinic
    query = query.join(Consultation).where(Consultation.clinic_id == current_user.clinic_id)
    
    logs = await db.exec(query.order_by(PrintLog.printed_at.desc())).all()
    return logs


@router.get("/print/status/{print_id}")
async def get_print_status(
    print_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Verificar status de uma impressão."""
    
    print_log = await db.get(PrintLog, print_id)
    if not print_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log de impressão não encontrado"
        )
    
    # Verify access
    consultation = await db.get(Consultation, print_log.consultation_id)
    if not consultation or consultation.clinic_id != current_user.clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado"
        )
    
    return {
        "print_id": print_log.id,
        "status": print_log.status,
        "printed_at": print_log.printed_at,
        "error_message": print_log.error_message
    }


@router.delete("/print/logs/{print_id}")
async def delete_print_log(
    print_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Excluir log de impressão."""
    
    print_log = await db.get(PrintLog, print_id)
    if not print_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log de impressão não encontrado"
        )
    
    # Verify access
    consultation = await db.get(Consultation, print_log.consultation_id)
    if not consultation or consultation.clinic_id != current_user.clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado"
        )
    
    await db.delete(print_log)
    await db.commit()
    
    return {"message": "Log de impressão excluído com sucesso"}
