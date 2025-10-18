"""
Consultation finalization API endpoints.
Handles automatic generation of consultation history when finalizing consultations.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.db.session import get_db_session
from app.models import Consultation, Patient, User, AuditLog

router = APIRouter()


class ConsultationFinalizationRequest(BaseModel):
    """Consultation finalization request schema."""
    final_notes: Optional[str] = None
    diagnosis_code: Optional[str] = None
    treatment_summary: Optional[str] = None


class ConsultationFinalizationResponse(BaseModel):
    """Consultation finalization response schema."""
    success: bool
    message: str
    consultation_id: str
    finalized_at: datetime
    history_record_id: Optional[str] = None


@router.post("/finalize/{consultation_id}", response_model=ConsultationFinalizationResponse)
async def finalize_consultation(
    consultation_id: str,
    request: ConsultationFinalizationRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Finalize a consultation and automatically generate historical record.
    
    This endpoint:
    1. Updates consultation status to 'completed'
    2. Stores all consultation data as historical record
    3. Creates audit log entry
    4. Returns confirmation with history record ID
    """
    try:
        # Get consultation
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
        
        # Check if already finalized
        if consultation.status == 'completed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consulta já foi finalizada"
            )
        
        # Update consultation status and final data
        consultation.status = 'completed'
        consultation.updated_at = datetime.now()
        
        # Add final notes if provided
        if request.final_notes:
            if consultation.notes:
                consultation.notes += f"\n\n--- Notas Finais ---\n{request.final_notes}"
            else:
                consultation.notes = f"--- Notas Finais ---\n{request.final_notes}"
        
        # Update diagnosis code if provided
        if request.diagnosis_code:
            consultation.diagnosis_code = request.diagnosis_code
        
        # Update treatment summary if provided
        if request.treatment_summary:
            if consultation.treatment_plan:
                consultation.treatment_plan += f"\n\n--- Resumo do Tratamento ---\n{request.treatment_summary}"
            else:
                consultation.treatment_plan = f"--- Resumo do Tratamento ---\n{request.treatment_summary}"
        
        # Commit consultation updates
        await db.commit()
        await db.refresh(consultation)
        
        # Create historical record (this would be stored in a separate history table)
        history_record_id = str(uuid.uuid4())
        
        # For now, we'll create an audit log entry as the history record
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="consultation_finalized",
            entity="consultation",
            entity_id=consultation.id,
            details={
                "consultation_id": str(consultation.id),
                "patient_id": str(consultation.patient_id),
                "doctor_id": str(consultation.doctor_id),
                "finalized_at": datetime.now().isoformat(),
                "diagnosis": consultation.diagnosis,
                "diagnosis_code": consultation.diagnosis_code,
                "treatment_plan": consultation.treatment_plan,
                "chief_complaint": consultation.chief_complaint,
                "history_present_illness": consultation.history_present_illness,
                "physical_examination": consultation.physical_examination,
                "vital_signs": consultation.vital_signs,
                "final_notes": request.final_notes,
                "history_record_id": history_record_id
            }
        )
        
        db.add(audit_log)
        await db.commit()
        
        # Create additional audit log for consultation completion
        completion_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="consultation_completed",
            entity="consultation",
            entity_id=consultation.id,
            details={
                "consultation_id": str(consultation.id),
                "patient_id": str(consultation.patient_id),
                "completed_at": datetime.now().isoformat(),
                "status": "completed"
            }
        )
        
        db.add(completion_log)
        await db.commit()
        
        return ConsultationFinalizationResponse(
            success=True,
            message="Consulta finalizada com sucesso e histórico gerado automaticamente",
            consultation_id=consultation_id,
            finalized_at=datetime.now(),
            history_record_id=history_record_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao finalizar consulta: {str(e)}"
        )


@router.get("/history/{patient_id}")
async def get_patient_consultation_history(
    patient_id: str,
    page: int = 1,
    size: int = 20,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get consultation history for a patient.
    
    Returns a timeline of past consultations with:
    - Date and time
    - Doctor name
    - Diagnosis summary
    - Key notes
    """
    try:
        # Verify patient exists and belongs to clinic
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.clinic_id == current_user.clinic_id
            )
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paciente não encontrado"
            )
        
        # Get consultation history from audit logs
        history_result = await db.execute(
            select(AuditLog).where(
                AuditLog.clinic_id == current_user.clinic_id,
                AuditLog.action == "consultation_finalized",
                AuditLog.details["patient_id"].astext == patient_id
            ).order_by(AuditLog.created_at.desc())
        )
        
        history_logs = history_result.scalars().all()
        
        # Format history data
        history_items = []
        for log in history_logs:
            details = log.details or {}
            
            # Get doctor name
            doctor_result = await db.execute(
                select(User.name).where(User.id == log.user_id)
            )
            doctor_name = doctor_result.scalar_one_or_none() or "Médico não encontrado"
            
            history_items.append({
                "id": details.get("history_record_id", str(log.id)),
                "consultation_id": details.get("consultation_id"),
                "date": log.created_at.strftime("%d/%m/%Y"),
                "time": log.created_at.strftime("%H:%M"),
                "datetime": log.created_at.isoformat(),
                "doctor_name": doctor_name,
                "diagnosis": details.get("diagnosis", "N/A"),
                "diagnosis_code": details.get("diagnosis_code"),
                "summary": details.get("final_notes", details.get("treatment_plan", "Consulta realizada")),
                "chief_complaint": details.get("chief_complaint"),
                "treatment_plan": details.get("treatment_plan"),
                "vital_signs": details.get("vital_signs")
            })
        
        # Apply pagination
        total = len(history_items)
        start = (page - 1) * size
        end = start + size
        paginated_items = history_items[start:end]
        
        return {
            "items": paginated_items,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size,
            "patient_name": patient.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar histórico do paciente: {str(e)}"
        )


@router.get("/history/{patient_id}/timeline")
async def get_patient_timeline(
    patient_id: str,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get patient consultation timeline for display in Atendimento Médico.
    
    Returns a simplified timeline format suitable for the medical attendance screen.
    """
    try:
        # Get consultation history
        history_response = await get_patient_consultation_history(
            patient_id=patient_id,
            page=1,
            size=50,  # Get more items for timeline
            current_user=current_user,
            db=db
        )
        
        # Format for timeline display
        timeline_items = []
        for item in history_response["items"]:
            # Create timeline entry
            timeline_entry = {
                "id": item["id"],
                "date": item["date"],
                "time": item["time"],
                "datetime": item["datetime"],
                "title": f"Consulta — {item['chief_complaint'] or 'Consulta médica'}",
                "doctor_name": item["doctor_name"],
                "diagnosis": item["diagnosis"],
                "summary": item["summary"][:100] + "..." if len(item["summary"]) > 100 else item["summary"],
                "is_expanded": False,
                "details": {
                    "chief_complaint": item["chief_complaint"],
                    "diagnosis": item["diagnosis"],
                    "diagnosis_code": item["diagnosis_code"],
                    "treatment_plan": item["treatment_plan"],
                    "vital_signs": item["vital_signs"]
                }
            }
            timeline_items.append(timeline_entry)
        
        return {
            "patient_name": history_response["patient_name"],
            "timeline": timeline_items,
            "total_consultations": history_response["total"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar timeline do paciente: {str(e)}"
        )
