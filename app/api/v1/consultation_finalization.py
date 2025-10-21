"""
Consultation finalization API endpoints.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
import uuid

from app.core.auth import get_current_user, require_medical_records_write, require_medical_records_read
from app.db.session import get_db_session
from app.models import Consultation, Patient, User, MedicalRecord
from app.schemas import ConsultationFinalizeRequest

router = APIRouter()

@router.post("/finalize/{consultation_id}", status_code=status.HTTP_200_OK)
async def finalize_consultation(
    consultation_id: str,
    request: ConsultationFinalizeRequest,
    current_user = Depends(require_medical_records_write),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Finalize a consultation and generate historical record.
    """
    try:
        # Get consultation data
        consultation_result = await db.execute(
            select(Consultation).where(Consultation.id == consultation_id)
        )
        consultation = consultation_result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        # Check if consultation is already finalized
        if consultation.status == "completed":
            raise HTTPException(status_code=400, detail="Consulta já foi finalizada")
        
        # Update consultation with final data
        consultation_data = {
            **consultation.data,
            "anamnesis": request.anamnesis,
            "diagnosis": request.diagnosis,
            "exams": request.exams,
            "prescriptions": request.prescriptions,
            "observations": request.observations,
            "finalization_notes": request.finalization_notes,
            "finalized_by": current_user.id,
            "finalized_at": datetime.utcnow().isoformat()
        }
        
        # Update consultation status and data
        await db.execute(
            update(Consultation)
            .where(Consultation.id == consultation_id)
            .values(
                status="completed",
                data=consultation_data,
                updated_at=datetime.utcnow()
            )
        )
        
        # Create a new consultation record for history
        history_consultation = Consultation(
            id=str(uuid.uuid4()),
            patient_id=consultation.patient_id,
            doctor_id=current_user.id,
            clinic_id=current_user.clinic_id,
            status="completed",
            type="history_record",
            data={
                "original_consultation_id": consultation_id,
                "anamnesis": request.anamnesis,
                "diagnosis": request.diagnosis,
                "exams": request.exams,
                "prescriptions": request.prescriptions,
                "observations": request.observations,
                "finalization_notes": request.finalization_notes,
                "created_from": "finalization",
                "created_at": datetime.utcnow().isoformat(),
                "finalized_by": current_user.id,
                "finalized_at": datetime.utcnow().isoformat()
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(history_consultation)
        
        # Create medical record for the records page
        medical_record = MedicalRecord(
            id=str(uuid.uuid4()),
            appointment_id=consultation.appointment_id,
            clinic_id=current_user.clinic_id,
            doctor_id=current_user.id,
            patient_id=consultation.patient_id,
            record_type="encounter",
            anamnesis=request.anamnesis or "",
            physical_exam=request.observations or "",
            diagnosis=request.diagnosis or "",
            icd_code="",  # Will be filled if diagnosis_code is provided
            treatment_plan=request.finalization_notes or "",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(medical_record)
        await db.commit()
        
        return {
            "success": True,
            "message": "Consulta finalizada com sucesso",
            "consultation_id": consultation_id,
            "history_record_id": history_consultation.id,
            "medical_record_id": medical_record.id,
            "finalized_at": datetime.utcnow().isoformat(),
            "finalized_by": current_user.name
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao finalizar consulta: {str(e)}")

@router.get("/history/{patient_id}", status_code=status.HTTP_200_OK)
async def get_consultation_history(
    patient_id: str,
    page: int = 1,
    size: int = 20,
    current_user = Depends(require_medical_records_read),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get consultation history for a patient in timeline format.
    """
    try:
        # Get patient consultations
        offset = (page - 1) * size
        
        consultations_result = await db.execute(
            select(Consultation)
            .where(
                Consultation.patient_id == patient_id,
                Consultation.clinic_id == current_user.clinic_id,
                Consultation.status == "completed"
            )
            .order_by(Consultation.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        
        consultations = consultations_result.scalars().all()
        
        # Get total count
        count_result = await db.execute(
            select(Consultation)
            .where(
                Consultation.patient_id == patient_id,
                Consultation.clinic_id == current_user.clinic_id,
                Consultation.status == "completed"
            )
        )
        total = len(count_result.scalars().all())
        
        # Format for timeline display
        timeline_data = []
        for consultation in consultations:
            timeline_data.append({
                "id": consultation.id,
                "date": consultation.created_at.isoformat(),
                "title": consultation.data.get("diagnosis", "Consulta Médica"),
                "doctor_name": current_user.name,  # You might want to get actual doctor name
                "summary": consultation.data.get("finalization_notes", "")[:100] + "..." if len(consultation.data.get("finalization_notes", "")) > 100 else consultation.data.get("finalization_notes", ""),
                "diagnosis": consultation.data.get("diagnosis", ""),
                "cid_code": consultation.data.get("cid_code", ""),
                "type": consultation.type,
                "data": consultation.data
            })
        
        return {
            "success": True,
            "timeline": timeline_data,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar histórico: {str(e)}")