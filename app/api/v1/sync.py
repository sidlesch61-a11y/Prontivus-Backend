"""
Sync API endpoints for offline-first functionality.
"""

from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.auth import get_current_user
from app.core.security import security
from app.db.session import get_db_transaction
from app.models import Patient, Appointment, MedicalRecord, AuditLog
from app.schemas import SyncRequest, SyncResponse, SyncResult

router = APIRouter()


@router.post("/events", response_model=SyncResponse)
async def sync_events(
    request: SyncRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_transaction)
):
    """Process offline sync events with idempotency."""
    results = []
    
    for event in request.events:
        try:
            # Check idempotency
            idempotency_key = security.hash_idempotency_key(event.idempotency_key)
            
            # TODO: Check if event was already processed using idempotency_key
            # For now, we'll process all events
            
            # Process event based on type
            server_id = await process_sync_event(
                event, current_user, db
            )
            
            results.append(SyncResult(
                client_event_id=event.client_event_id,
                server_id=server_id,
                status="success"
            ))
            
        except Exception as e:
            results.append(SyncResult(
                client_event_id=event.client_event_id,
                server_id=None,
                status="error",
                error=str(e)
            ))
    
    return SyncResponse(results=results)


async def process_sync_event(
    event, current_user, db: AsyncSession
) -> str:
    """Process a single sync event."""
    event_type = event.event_type
    payload = event.payload
    
    if event_type == "create_patient":
        return await create_patient_from_sync(payload, current_user, db)
    
    elif event_type == "update_patient":
        return await update_patient_from_sync(payload, current_user, db)
    
    elif event_type == "create_appointment":
        return await create_appointment_from_sync(payload, current_user, db)
    
    elif event_type == "create_medical_record":
        return await create_medical_record_from_sync(payload, current_user, db)
    
    elif event_type == "upload_exam_placeholder":
        return await create_exam_placeholder_from_sync(payload, current_user, db)
    
    else:
        raise ValueError(f"Unknown event type: {event_type}")


async def create_patient_from_sync(
    payload: Dict[str, Any], current_user, db: AsyncSession
) -> str:
    """Create patient from sync event."""
    # Check if patient already exists by CPF
    existing_patient = await db.execute(
        select(Patient).where(
            Patient.clinic_id == current_user.clinic_id,
            Patient.cpf == payload["cpf"]
        )
    )
    
    if existing_patient.scalar_one_or_none():
        return str(existing_patient.scalar().id)
    
    # Create new patient
    patient = Patient(
        clinic_id=current_user.clinic_id,
        name=payload["name"],
        birthdate=datetime.fromisoformat(payload["birthdate"]).date(),
        gender=payload["gender"],
        cpf=payload["cpf"],
        address=payload.get("address", {}),
        phone=payload.get("phone"),
        email=payload.get("email"),
        insurance_number=payload.get("insurance_number"),
        insurance_provider=payload.get("insurance_provider")
    )
    
    db.add(patient)
    await db.flush()
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="patient_created_sync",
        entity="patient",
        entity_id=patient.id,
        details={"sync_source": "offline"}
    )
    db.add(audit_log)
    
    return str(patient.id)


async def update_patient_from_sync(
    payload: Dict[str, Any], current_user, db: AsyncSession
) -> str:
    """Update patient from sync event."""
    patient_id = payload["patient_id"]
    
    # Get patient
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id
        )
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise ValueError("Patient not found")
    
    # Update fields
    update_fields = ["name", "address", "phone", "email", "insurance_number", "insurance_provider"]
    for field in update_fields:
        if field in payload:
            setattr(patient, field, payload[field])
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="patient_updated_sync",
        entity="patient",
        entity_id=patient.id,
        details={"sync_source": "offline", "updated_fields": list(payload.keys())}
    )
    db.add(audit_log)
    
    return str(patient.id)


async def create_appointment_from_sync(
    payload: Dict[str, Any], current_user, db: AsyncSession
) -> str:
    """Create appointment from sync event."""
    # Verify patient exists
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == payload["patient_id"],
            Patient.clinic_id == current_user.clinic_id
        )
    )
    patient = patient_result.scalar_one_or_none()
    
    if not patient:
        raise ValueError("Patient not found")
    
    # Verify doctor exists
    doctor_result = await db.execute(
        select(Patient).where(
            Patient.id == payload["doctor_id"],
            Patient.clinic_id == current_user.clinic_id
        )
    )
    doctor = doctor_result.scalar_one_or_none()
    
    if not doctor:
        raise ValueError("Doctor not found")
    
    # Create appointment
    appointment = Appointment(
        clinic_id=current_user.clinic_id,
        patient_id=payload["patient_id"],
        doctor_id=payload["doctor_id"],
        start_time=datetime.fromisoformat(payload["start_time"]),
        end_time=datetime.fromisoformat(payload["end_time"]),
        source=payload.get("source", "mobile"),
        notes=payload.get("notes")
    )
    
    db.add(appointment)
    await db.flush()
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="appointment_created_sync",
        entity="appointment",
        entity_id=appointment.id,
        details={"sync_source": "offline"}
    )
    db.add(audit_log)
    
    return str(appointment.id)


async def create_medical_record_from_sync(
    payload: Dict[str, Any], current_user, db: AsyncSession
) -> str:
    """Create medical record from sync event."""
    # Verify appointment exists
    appointment_result = await db.execute(
        select(Appointment).where(
            Appointment.id == payload["appointment_id"],
            Appointment.clinic_id == current_user.clinic_id
        )
    )
    appointment = appointment_result.scalar_one_or_none()
    
    if not appointment:
        raise ValueError("Appointment not found")
    
    # Create medical record
    record = MedicalRecord(
        clinic_id=current_user.clinic_id,
        appointment_id=payload["appointment_id"],
        doctor_id=current_user.id,
        patient_id=appointment.patient_id,
        anamnesis=payload.get("anamnesis"),
        physical_exam=payload.get("physical_exam"),
        diagnosis=payload.get("diagnosis"),
        icd_code=payload.get("icd_code"),
        treatment_plan=payload.get("treatment_plan")
    )
    
    db.add(record)
    await db.flush()
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="medical_record_created_sync",
        entity="medical_record",
        entity_id=record.id,
        details={"sync_source": "offline"}
    )
    db.add(audit_log)
    
    return str(record.id)


async def create_exam_placeholder_from_sync(
    payload: Dict[str, Any], current_user, db: AsyncSession
) -> str:
    """Create exam placeholder from sync event."""
    # This would typically create a placeholder exam record
    # that gets updated when the actual file is uploaded
    
    # For now, return a placeholder ID
    # In a real implementation, you would create an Exam record
    return "placeholder_exam_id"
