"""
API endpoints for offline sync events and idempotency.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, and_
from typing import List, Optional, Dict, Any
import uuid
import json
import logging
import asyncio
from datetime import datetime, timedelta

from ..models.sync_events import (
    ClientSyncEvent, SyncBatch, SyncConflict,
    SyncEventType, SyncEventStatus,
    SyncEventRequest, SyncEventsRequest, SyncEventResult,
    SyncEventsResponse, SyncConflictResponse,
    SyncEventProcessor, SyncConflictResolver, SyncEventValidator
)
from ..core.auth import get_current_user, get_current_tenant, require_permission
from ..db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])

@router.post("/events", response_model=SyncEventsResponse)
async def process_sync_events(
    request_data: SyncEventsRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Process batch of sync events with idempotency."""
    
    try:
        # Generate server-side batch ID
        batch_id = str(uuid.uuid4())
        
        # Create batch record
        batch = SyncBatch(
            batch_id=batch_id,
            client_batch_id=request_data.batch_id,
            clinic_id=current_tenant.id,
            total_events=len(request_data.events),
            status=SyncEventStatus.PROCESSING,
            processing_started_at=datetime.utcnow()
        )
        
        db.add(batch)
        db.commit()
        db.refresh(batch)
        
        # Process each event
        results = []
        processed_count = 0
        failed_count = 0
        skipped_count = 0
        
        for event_request in request_data.events:
            try:
                result = await process_single_sync_event(
                    event_request, current_user, current_tenant, db, batch_id
                )
                results.append(result)
                
                if result.status == "ok":
                    processed_count += 1
                elif result.status == "skipped":
                    skipped_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing sync event {event_request.client_event_id}: {str(e)}")
                
                result = SyncEventResult(
                    client_event_id=event_request.client_event_id,
                    status="failed",
                    error_msg=str(e)
                )
                results.append(result)
                failed_count += 1
        
        # Update batch status
        batch.processed_events = processed_count
        batch.failed_events = failed_count
        batch.skipped_events = skipped_count
        batch.status = SyncEventStatus.PROCESSED if failed_count == 0 else SyncEventStatus.FAILED
        batch.processing_completed_at = datetime.utcnow()
        batch.has_errors = failed_count > 0
        
        if batch.has_errors:
            batch.error_summary = {
                "total_errors": failed_count,
                "error_types": list(set(r.error_msg for r in results if r.error_msg))
            }
        
        db.add(batch)
        db.commit()
        
        # Create response summary
        summary = {
            "total_events": len(request_data.events),
            "processed_events": processed_count,
            "failed_events": failed_count,
            "skipped_events": skipped_count,
            "success_rate": (processed_count / len(request_data.events)) * 100 if request_data.events else 0,
            "processing_time_ms": (datetime.utcnow() - batch.processing_started_at).total_seconds() * 1000
        }
        
        return SyncEventsResponse(
            batch_id=batch_id,
            results=results,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Error processing sync batch: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process sync events: {str(e)}"
        )

async def process_single_sync_event(
    event_request: SyncEventRequest,
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session,
    batch_id: str
) -> SyncEventResult:
    """Process a single sync event with idempotency."""
    
    try:
        # Check for existing event with same client_event_id
        existing_event = db.exec(
            select(ClientSyncEvent).where(
                and_(
                    ClientSyncEvent.clinic_id == current_tenant.id,
                    ClientSyncEvent.client_event_id == event_request.client_event_id
                )
            )
        ).first()
        
        if existing_event:
            # Return existing mapping
            return SyncEventResult(
                client_event_id=event_request.client_event_id,
                status="ok" if existing_event.status == SyncEventStatus.PROCESSED else "skipped",
                server_id=existing_event.server_entity_id,
                processing_metadata=existing_event.processing_metadata
            )
        
        # Check for idempotency key conflicts
        if event_request.idempotency_key:
            existing_idempotency = db.exec(
                select(ClientSyncEvent).where(
                    and_(
                        ClientSyncEvent.clinic_id == current_tenant.id,
                        ClientSyncEvent.idempotency_key == event_request.idempotency_key
                    )
                )
            ).first()
            
            if existing_idempotency:
                return SyncEventResult(
                    client_event_id=event_request.client_event_id,
                    status="ok" if existing_idempotency.status == SyncEventStatus.PROCESSED else "skipped",
                    server_id=existing_idempotency.server_entity_id,
                    processing_metadata=existing_idempotency.processing_metadata
                )
        
        # Validate event payload
        if not SyncEventProcessor.validate_event_payload(event_request.type, event_request.payload):
            return SyncEventResult(
                client_event_id=event_request.client_event_id,
                status="failed",
                error_msg="Invalid payload for event type"
            )
        
        # Create sync event record
        sync_event = ClientSyncEvent(
            clinic_id=current_tenant.id,
            client_event_id=event_request.client_event_id,
            idempotency_key=event_request.idempotency_key or SyncEventProcessor.generate_idempotency_key(
                event_request.type, event_request.payload
            ),
            event_type=event_request.type,
            payload=event_request.payload,
            client_timestamp=event_request.client_timestamp,
            status=SyncEventStatus.PROCESSING,
            processing_attempts=1
        )
        
        db.add(sync_event)
        db.commit()
        db.refresh(sync_event)
        
        # Process event based on type
        server_entity_id = await process_event_by_type(
            event_request.type, event_request.payload, current_user, current_tenant, db
        )
        
        # Update sync event with result
        sync_event.status = SyncEventStatus.PROCESSED
        sync_event.processed = True
        sync_event.server_entity_id = server_entity_id
        sync_event.processed_at = datetime.utcnow()
        sync_event.processing_metadata = {
            "processed_at": datetime.utcnow().isoformat(),
            "processed_by": str(current_user["id"]),
            "batch_id": batch_id
        }
        
        db.add(sync_event)
        db.commit()
        
        return SyncEventResult(
            client_event_id=event_request.client_event_id,
            status="ok",
            server_id=server_entity_id,
            processing_metadata=sync_event.processing_metadata
        )
        
    except Exception as e:
        # Update sync event with error
        if 'sync_event' in locals():
            sync_event.status = SyncEventStatus.FAILED
            sync_event.last_error = str(e)
            sync_event.processing_attempts += 1
            db.add(sync_event)
            db.commit()
        
        return SyncEventResult(
            client_event_id=event_request.client_event_id,
            status="failed",
            error_msg=str(e)
        )

async def process_event_by_type(
    event_type: SyncEventType,
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Process event based on its type."""
    
    if event_type == SyncEventType.CREATE_PATIENT:
        return await create_patient_from_sync(payload, current_user, current_tenant, db)
    
    elif event_type == SyncEventType.UPDATE_PATIENT:
        return await update_patient_from_sync(payload, current_user, current_tenant, db)
    
    elif event_type == SyncEventType.DELETE_PATIENT:
        return await delete_patient_from_sync(payload, current_user, current_tenant, db)
    
    elif event_type == SyncEventType.CREATE_APPOINTMENT:
        return await create_appointment_from_sync(payload, current_user, current_tenant, db)
    
    elif event_type == SyncEventType.UPDATE_APPOINTMENT:
        return await update_appointment_from_sync(payload, current_user, current_tenant, db)
    
    elif event_type == SyncEventType.DELETE_APPOINTMENT:
        return await delete_appointment_from_sync(payload, current_user, current_tenant, db)
    
    elif event_type == SyncEventType.CREATE_MEDICAL_RECORD:
        return await create_medical_record_from_sync(payload, current_user, current_tenant, db)
    
    elif event_type == SyncEventType.UPDATE_MEDICAL_RECORD:
        return await update_medical_record_from_sync(payload, current_user, current_tenant, db)
    
    elif event_type == SyncEventType.DELETE_MEDICAL_RECORD:
        return await delete_medical_record_from_sync(payload, current_user, current_tenant, db)
    
    else:
        raise ValueError(f"Unsupported event type: {event_type}")

# Event processors for different entity types
async def create_patient_from_sync(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Create patient from sync event."""
    
    # Validate patient data
    errors = SyncEventValidator.validate_patient_data(payload)
    if errors:
        raise ValueError(f"Patient validation errors: {', '.join(errors)}")
    
    # Check for existing patient by email
    existing_patient = db.exec(
        select("Patient").where(
            and_(
                "Patient.clinic_id == current_tenant.id",
                "Patient.email == payload['email']"
            )
        )
    ).first()
    
    if existing_patient:
        # Return existing patient ID
        return existing_patient.id
    
    # Create new patient
    patient_id = str(uuid.uuid4())
    await db.execute("""
        INSERT INTO patients (
            id, clinic_id, name, birthdate, gender, cpf, address,
            phone, email, insurance_number, insurance_provider,
            metadata, archived, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
    """,
    patient_id,
    current_tenant.id,
    payload.get("name"),
    payload.get("birthdate"),
    payload.get("gender", "unknown"),
    payload.get("cpf"),
    json.dumps(payload.get("address", {})),
    payload.get("phone"),
    payload.get("email"),
    payload.get("insurance_number"),
    payload.get("insurance_provider"),
    json.dumps(payload.get("metadata", {})),
    False,
    datetime.utcnow(),
    datetime.utcnow()
    )
    
    return uuid.UUID(patient_id)

async def update_patient_from_sync(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Update patient from sync event."""
    
    patient_id = payload.get("id")
    if not patient_id:
        raise ValueError("Patient ID is required for update")
    
    # Check if patient exists
    patient = db.exec(
        select("Patient").where(
            and_(
                "Patient.id == patient_id",
                "Patient.clinic_id == current_tenant.id"
            )
        )
    ).first()
    
    if not patient:
        raise ValueError("Patient not found")
    
    # Update patient
    await db.execute("""
        UPDATE patients SET
            name = COALESCE($1, name),
            birthdate = COALESCE($2, birthdate),
            gender = COALESCE($3, gender),
            cpf = COALESCE($4, cpf),
            address = COALESCE($5, address),
            phone = COALESCE($6, phone),
            email = COALESCE($7, email),
            insurance_number = COALESCE($8, insurance_number),
            insurance_provider = COALESCE($9, insurance_provider),
            metadata = COALESCE($10, metadata),
            updated_at = $11
        WHERE id = $12
    """,
    payload.get("name"),
    payload.get("birthdate"),
    payload.get("gender"),
    payload.get("cpf"),
    json.dumps(payload.get("address", {})),
    payload.get("phone"),
    payload.get("email"),
    payload.get("insurance_number"),
    payload.get("insurance_provider"),
    json.dumps(payload.get("metadata", {})),
    datetime.utcnow(),
    patient_id
    )
    
    return uuid.UUID(patient_id)

async def delete_patient_from_sync(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Delete patient from sync event."""
    
    patient_id = payload.get("id")
    if not patient_id:
        raise ValueError("Patient ID is required for delete")
    
    # Check if patient exists
    patient = db.exec(
        select("Patient").where(
            and_(
                "Patient.id == patient_id",
                "Patient.clinic_id == current_tenant.id"
            )
        )
    ).first()
    
    if not patient:
        raise ValueError("Patient not found")
    
    # Soft delete patient
    await db.execute("""
        UPDATE patients SET
            archived = true,
            updated_at = $1
        WHERE id = $2
    """, datetime.utcnow(), patient_id)
    
    return uuid.UUID(patient_id)

async def create_appointment_from_sync(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Create appointment from sync event."""
    
    # Validate appointment data
    errors = SyncEventValidator.validate_appointment_data(payload)
    if errors:
        raise ValueError(f"Appointment validation errors: {', '.join(errors)}")
    
    # Create new appointment
    appointment_id = str(uuid.uuid4())
    await db.execute("""
        INSERT INTO appointments (
            id, clinic_id, patient_id, doctor_id, start_time, end_time,
            status, telemed_link, source, notes, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
    """,
    appointment_id,
    current_tenant.id,
    payload.get("patient_id"),
    payload.get("doctor_id"),
    payload.get("start_time"),
    payload.get("end_time"),
    payload.get("status", "scheduled"),
    payload.get("telemed_link"),
    payload.get("source", "sync"),
    payload.get("notes"),
    datetime.utcnow(),
    datetime.utcnow()
    )
    
    return uuid.UUID(appointment_id)

async def update_appointment_from_sync(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Update appointment from sync event."""
    
    appointment_id = payload.get("id")
    if not appointment_id:
        raise ValueError("Appointment ID is required for update")
    
    # Check if appointment exists
    appointment = db.exec(
        select("Appointment").where(
            and_(
                "Appointment.id == appointment_id",
                "Appointment.clinic_id == current_tenant.id"
            )
        )
    ).first()
    
    if not appointment:
        raise ValueError("Appointment not found")
    
    # Update appointment
    await db.execute("""
        UPDATE appointments SET
            start_time = COALESCE($1, start_time),
            end_time = COALESCE($2, end_time),
            status = COALESCE($3, status),
            telemed_link = COALESCE($4, telemed_link),
            notes = COALESCE($5, notes),
            updated_at = $6
        WHERE id = $7
    """,
    payload.get("start_time"),
    payload.get("end_time"),
    payload.get("status"),
    payload.get("telemed_link"),
    payload.get("notes"),
    datetime.utcnow(),
    appointment_id
    )
    
    return uuid.UUID(appointment_id)

async def delete_appointment_from_sync(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Delete appointment from sync event."""
    
    appointment_id = payload.get("id")
    if not appointment_id:
        raise ValueError("Appointment ID is required for delete")
    
    # Check if appointment exists
    appointment = db.exec(
        select("Appointment").where(
            and_(
                "Appointment.id == appointment_id",
                "Appointment.clinic_id == current_tenant.id"
            )
        )
    ).first()
    
    if not appointment:
        raise ValueError("Appointment not found")
    
    # Update appointment status to cancelled
    await db.execute("""
        UPDATE appointments SET
            status = 'cancelled',
            updated_at = $1
        WHERE id = $2
    """, datetime.utcnow(), appointment_id)
    
    return uuid.UUID(appointment_id)

async def create_medical_record_from_sync(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Create medical record from sync event."""
    
    # Validate medical record data
    errors = SyncEventValidator.validate_medical_record_data(payload)
    if errors:
        raise ValueError(f"Medical record validation errors: {', '.join(errors)}")
    
    # Create new medical record
    record_id = str(uuid.uuid4())
    await db.execute("""
        INSERT INTO medical_records (
            id, appointment_id, clinic_id, doctor_id, patient_id,
            record_type, anamnesis, physical_exam, diagnosis, icd_code,
            treatment_plan, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
    """,
    record_id,
    payload.get("appointment_id"),
    current_tenant.id,
    payload.get("doctor_id"),
    payload.get("patient_id"),
    payload.get("record_type", "encounter"),
    payload.get("anamnesis"),
    payload.get("physical_exam"),
    payload.get("diagnosis"),
    payload.get("icd_code"),
    payload.get("treatment_plan"),
    datetime.utcnow(),
    datetime.utcnow()
    )
    
    return uuid.UUID(record_id)

async def update_medical_record_from_sync(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Update medical record from sync event."""
    
    record_id = payload.get("id")
    if not record_id:
        raise ValueError("Medical record ID is required for update")
    
    # Check if medical record exists
    record = db.exec(
        select("MedicalRecord").where(
            and_(
                "MedicalRecord.id == record_id",
                "MedicalRecord.clinic_id == current_tenant.id"
            )
        )
    ).first()
    
    if not record:
        raise ValueError("Medical record not found")
    
    # Update medical record
    await db.execute("""
        UPDATE medical_records SET
            anamnesis = COALESCE($1, anamnesis),
            physical_exam = COALESCE($2, physical_exam),
            diagnosis = COALESCE($3, diagnosis),
            icd_code = COALESCE($4, icd_code),
            treatment_plan = COALESCE($5, treatment_plan),
            updated_at = $6
        WHERE id = $7
    """,
    payload.get("anamnesis"),
    payload.get("physical_exam"),
    payload.get("diagnosis"),
    payload.get("icd_code"),
    payload.get("treatment_plan"),
    datetime.utcnow(),
    record_id
    )
    
    return uuid.UUID(record_id)

async def delete_medical_record_from_sync(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    current_tenant: Dict[str, Any],
    db: Session
) -> uuid.UUID:
    """Delete medical record from sync event."""
    
    record_id = payload.get("id")
    if not record_id:
        raise ValueError("Medical record ID is required for delete")
    
    # Check if medical record exists
    record = db.exec(
        select("MedicalRecord").where(
            and_(
                "MedicalRecord.id == record_id",
                "MedicalRecord.clinic_id == current_tenant.id"
            )
        )
    ).first()
    
    if not record:
        raise ValueError("Medical record not found")
    
    # Soft delete medical record (set a flag or move to archive)
    await db.execute("""
        UPDATE medical_records SET
            updated_at = $1
        WHERE id = $2
    """, datetime.utcnow(), record_id)
    
    return uuid.UUID(record_id)

# Additional endpoints for sync management
@router.get("/events/status/{batch_id}")
async def get_sync_batch_status(
    batch_id: str,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get sync batch processing status."""
    
    batch = db.exec(
        select(SyncBatch).where(
            and_(
                SyncBatch.batch_id == batch_id,
                SyncBatch.clinic_id == current_tenant.id
            )
        )
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync batch not found"
        )
    
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "total_events": batch.total_events,
        "processed_events": batch.processed_events,
        "failed_events": batch.failed_events,
        "skipped_events": batch.skipped_events,
        "has_errors": batch.has_errors,
        "error_summary": batch.error_summary,
        "processing_started_at": batch.processing_started_at,
        "processing_completed_at": batch.processing_completed_at
    }

@router.get("/conflicts")
async def list_sync_conflicts(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """List sync conflicts for manual resolution."""
    
    statement = select(SyncConflict).where(SyncConflict.clinic_id == current_tenant.id)
    
    if status:
        statement = statement.where(SyncConflict.status == status)
    
    statement = statement.order_by(SyncConflict.created_at.desc()).offset(offset).limit(limit)
    
    conflicts = db.exec(statement).all()
    
    return [SyncConflictResponse.from_orm(conflict) for conflict in conflicts]

@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_sync_conflict(
    conflict_id: str,
    resolution_data: dict,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Resolve a sync conflict."""
    
    conflict = db.exec(
        select(SyncConflict).where(
            and_(
                SyncConflict.id == conflict_id,
                SyncConflict.clinic_id == current_tenant.id
            )
        )
    ).first()
    
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync conflict not found"
        )
    
    resolution = resolution_data.get("resolution")
    resolution_notes = resolution_data.get("resolution_notes")
    
    if not resolution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolution is required"
        )
    
    # Update conflict
    conflict.resolution = resolution
    conflict.resolved_by = current_user["id"]
    conflict.resolved_at = datetime.utcnow()
    conflict.resolution_notes = resolution_notes
    conflict.status = "resolved"
    conflict.updated_at = datetime.utcnow()
    
    db.add(conflict)
    db.commit()
    
    return {"message": "Conflict resolved successfully"}
