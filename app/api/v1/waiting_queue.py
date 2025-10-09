"""
API endpoints for waiting queue system with atomic consultation finalization.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select, and_, func
from typing import List, Optional, Dict, Any
import uuid
import json
import logging
import asyncio
from datetime import datetime, timedelta

from ..models.waiting_queue import (
    WaitingQueue, WaitingQueueLog,
    WaitingQueueStatus, WaitingQueuePriority,
    WaitingQueueEnqueueRequest, WaitingQueueEnqueueResponse,
    WaitingQueueDequeueRequest, WaitingQueueDequeueResponse,
    ConsultationFinalizeRequest, ConsultationFinalizeResponse,
    WaitingQueueListResponse, WaitingQueueLogResponse,
    PatientCalledEvent, PatientRemovedEvent, QueueUpdateEvent,
    WaitingQueueManager, QueueAnalytics
)
from ..core.auth import get_current_user, get_current_tenant
from ..db.session import get_db
from ..services.websocket_service import WebSocketService
from ..services.queue_service import QueueService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/waiting_queue", tags=["waiting_queue"])

# WebSocket connection manager
websocket_service = WebSocketService()

@router.post("/enqueue", response_model=WaitingQueueEnqueueResponse)
async def enqueue_patient(
    request_data: WaitingQueueEnqueueRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Add a patient to the waiting queue."""
    
    try:
        # Validate appointment exists and belongs to clinic
        appointment = db.exec(
            select("Appointment").where(
                and_(
                    "Appointment.id == request_data.appointment_id",
                    "Appointment.clinic_id == current_tenant.id"
                )
            )
        ).first()
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        # Check if patient is already in queue
        existing_queue = db.exec(
            select(WaitingQueue).where(
                and_(
                    WaitingQueue.appointment_id == request_data.appointment_id,
                    WaitingQueue.status.in_([
                        WaitingQueueStatus.WAITING,
                        WaitingQueueStatus.CALLED,
                        WaitingQueueStatus.IN_CONSULTATION
                    ])
                )
            )
        ).first()
        
        if existing_queue:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Patient is already in the waiting queue"
            )
        
        # Calculate position in queue
        queue_service = QueueService()
        position = await queue_service.calculate_queue_position(
            current_tenant.id,
            appointment.doctor_id,
            request_data.priority
        )
        
        # Calculate estimated wait time
        estimated_wait_time = WaitingQueueManager.estimate_wait_time(position)
        estimated_call_time = WaitingQueueManager.calculate_call_time(estimated_wait_time)
        
        # Create queue entry
        queue_entry = WaitingQueue(
            clinic_id=current_tenant.id,
            appointment_id=request_data.appointment_id,
            patient_id=request_data.patient_id,
            doctor_id=appointment.doctor_id,
            position=position,
            status=WaitingQueueStatus.WAITING,
            priority=request_data.priority,
            estimated_wait_time_minutes=estimated_wait_time,
            estimated_call_time=estimated_call_time,
            notes=request_data.notes,
            queue_meta={
                "enqueued_by": current_user.id,
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            }
        )
        
        db.add(queue_entry)
        db.commit()
        db.refresh(queue_entry)
        
        # Log enqueue event
        log = WaitingQueueLog(
            queue_id=queue_entry.id,
            clinic_id=current_tenant.id,
            event="enqueued",
            user_id=current_user.id,
            user_role="receptionist",
            meta={
                "position": position,
                "priority": request_data.priority.value,
                "estimated_wait_time": estimated_wait_time
            },
            message=f"Patient enqueued at position {position}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(log)
        db.commit()
        
        # Broadcast queue update
        await websocket_service.broadcast_queue_update(
            current_tenant.id,
            appointment.doctor_id
        )
        
        logger.info(f"Patient enqueued: {queue_entry.id} at position {position}")
        
        return WaitingQueueEnqueueResponse.from_orm(queue_entry)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enqueuing patient: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue patient"
        )

@router.post("/dequeue/{queue_id}", response_model=WaitingQueueDequeueResponse)
async def dequeue_patient(
    queue_id: uuid.UUID,
    request_data: WaitingQueueDequeueRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Remove a patient from the waiting queue."""
    
    try:
        # Get queue entry
        queue_entry = db.exec(
            select(WaitingQueue).where(
                and_(
                    WaitingQueue.id == queue_id,
                    WaitingQueue.clinic_id == current_tenant.id
                )
            )
        ).first()
        
        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queue entry not found"
            )
        
        # Validate status
        if queue_entry.status not in [WaitingQueueStatus.WAITING, WaitingQueueStatus.CALLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot dequeue patient with status: {queue_entry.status}"
            )
        
        # Update status
        old_status = queue_entry.status
        queue_entry.status = WaitingQueueStatus.CANCELLED
        queue_entry.updated_at = datetime.utcnow()
        
        # Update queue metadata
        if not queue_entry.queue_meta:
            queue_entry.queue_meta = {}
        
        queue_entry.queue_meta.update({
            "dequeued_by": current_user.id,
            "dequeued_at": datetime.utcnow().isoformat(),
            "dequeue_reason": request_data.reason,
            "dequeue_notes": request_data.notes
        })
        
        db.add(queue_entry)
        
        # Log dequeue event
        log = WaitingQueueLog(
            queue_id=queue_entry.id,
            clinic_id=current_tenant.id,
            event="dequeued",
            user_id=current_user.id,
            user_role="receptionist",
            meta={
                "old_status": old_status,
                "reason": request_data.reason,
                "notes": request_data.notes
            },
            message=f"Patient dequeued from position {queue_entry.position}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(log)
        
        # Recalculate positions for remaining patients
        queue_service = QueueService()
        await queue_service.recalculate_positions(
            current_tenant.id,
            queue_entry.doctor_id
        )
        
        db.commit()
        
        # Broadcast patient removed event
        await websocket_service.broadcast_patient_removed(
            queue_entry,
            request_data.reason or "Manual removal"
        )
        
        # Broadcast queue update
        await websocket_service.broadcast_queue_update(
            current_tenant.id,
            queue_entry.doctor_id
        )
        
        logger.info(f"Patient dequeued: {queue_entry.id}")
        
        return WaitingQueueDequeueResponse(
            queue_id=queue_entry.id,
            patient_id=queue_entry.patient_id,
            position=queue_entry.position,
            status=queue_entry.status,
            message="Patient successfully removed from queue"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dequeuing patient: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dequeue patient"
        )

@router.post("/consultations/{consultation_id}/finalize", response_model=ConsultationFinalizeResponse)
async def finalize_consultation(
    consultation_id: uuid.UUID,
    request_data: ConsultationFinalizeRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Atomically finalize consultation and call next patient."""
    
    try:
        # Start transaction with advisory lock
        async with db.begin():
            # Get consultation/appointment
            appointment = db.exec(
                select("Appointment").where(
                    and_(
                        "Appointment.id == consultation_id",
                        "Appointment.clinic_id == current_tenant.id"
                    )
                )
            ).first()
            
            if not appointment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Consultation not found"
                )
            
            # Use advisory lock to prevent race conditions
            lock_key = f"doctor_{appointment.doctor_id}_queue"
            await db.execute(f"SELECT pg_advisory_xact_lock(hashtext('{lock_key}'))")
            
            # 1. Set appointment status to completed
            appointment.status = "completed"
            appointment.updated_at = datetime.utcnow()
            db.add(appointment)
            
            # 2. Update medical record if exists
            medical_record = db.exec(
                select("MedicalRecord").where(
                    "MedicalRecord.appointment_id == consultation_id"
                )
            ).first()
            
            if medical_record:
                medical_record.finalized = True
                medical_record.finalized_at = datetime.utcnow()
                medical_record.finalized_by = current_user.id
                if request_data.consultation_notes:
                    medical_record.notes = request_data.consultation_notes
                db.add(medical_record)
            
            # 3. Update current queue entry status to completed
            current_queue_entry = db.exec(
                select(WaitingQueue).where(
                    and_(
                        WaitingQueue.appointment_id == consultation_id,
                        WaitingQueue.status == WaitingQueueStatus.IN_CONSULTATION
                    )
                )
            ).first()
            
            if current_queue_entry:
                current_queue_entry.status = WaitingQueueStatus.COMPLETED
                current_queue_entry.consultation_ended_at = datetime.utcnow()
                current_queue_entry.updated_at = datetime.utcnow()
                db.add(current_queue_entry)
            
            # 4. Find and call next patient
            next_patient = None
            next_queue_entry = db.exec(
                select(WaitingQueue).where(
                    and_(
                        WaitingQueue.clinic_id == current_tenant.id,
                        WaitingQueue.doctor_id == appointment.doctor_id,
                        WaitingQueue.status == WaitingQueueStatus.WAITING
                    )
                ).order_by(WaitingQueue.position.asc())
            ).first()
            
            if next_queue_entry:
                # Update next patient status
                next_queue_entry.status = WaitingQueueStatus.CALLED
                next_queue_entry.called_at = datetime.utcnow()
                next_queue_entry.updated_at = datetime.utcnow()
                db.add(next_queue_entry)
                
                # Get patient details
                patient = db.exec(
                    select("Patient").where("Patient.id == next_queue_entry.patient_id")
                ).first()
                
                doctor = db.exec(
                    select("User").where("User.id == appointment.doctor_id")
                ).first()
                
                next_patient = {
                    "queue_id": str(next_queue_entry.id),
                    "appointment_id": str(next_queue_entry.appointment_id),
                    "patient_id": str(next_queue_entry.patient_id),
                    "patient_name": patient.name if patient else "Unknown",
                    "patient_phone": patient.phone if patient else None,
                    "doctor_id": str(appointment.doctor_id),
                    "doctor_name": doctor.name if doctor else "Unknown",
                    "position": next_queue_entry.position,
                    "priority": next_queue_entry.priority.value,
                    "called_at": next_queue_entry.called_at.isoformat(),
                    "estimated_consultation_start": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
                }
                
                # Log patient called event
                called_log = WaitingQueueLog(
                    queue_id=next_queue_entry.id,
                    clinic_id=current_tenant.id,
                    event="called",
                    user_id=current_user.id,
                    user_role="doctor",
                    meta={
                        "position": next_queue_entry.position,
                        "priority": next_queue_entry.priority.value,
                        "finalized_consultation_id": str(consultation_id)
                    },
                    message=f"Next patient called at position {next_queue_entry.position}",
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent")
                )
                db.add(called_log)
            
            # Log consultation finalization
            finalize_log = WaitingQueueLog(
                queue_id=current_queue_entry.id if current_queue_entry else None,
                clinic_id=current_tenant.id,
                event="consultation_finalized",
                user_id=current_user.id,
                user_role="doctor",
                meta={
                    "consultation_id": str(consultation_id),
                    "next_patient_called": next_patient is not None,
                    "consultation_notes": request_data.consultation_notes,
                    "follow_up_recommended": request_data.next_appointment_recommended
                },
                message="Consultation finalized and next patient called",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )
            db.add(finalize_log)
            
            # Commit transaction
            db.commit()
        
        # Broadcast events after transaction
        if next_patient:
            await websocket_service.broadcast_patient_called(next_patient)
        
        await websocket_service.broadcast_queue_update(
            current_tenant.id,
            appointment.doctor_id
        )
        
        logger.info(f"Consultation finalized: {consultation_id}, next patient called: {next_patient is not None}")
        
        return ConsultationFinalizeResponse(
            consultation_id=consultation_id,
            appointment_id=consultation_id,
            status="completed",
            next_patient=next_patient,
            message="Consultation finalized successfully" + (" and next patient called" if next_patient else ""),
            finalized_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finalizing consultation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to finalize consultation"
        )

@router.get("/", response_model=List[WaitingQueueListResponse])
async def list_waiting_queue(
    doctor_id: Optional[uuid.UUID] = None,
    status: Optional[WaitingQueueStatus] = None,
    priority: Optional[WaitingQueuePriority] = None,
    limit: int = 100,
    offset: int = 0,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """List waiting queue entries with optional filters."""
    
    statement = select(WaitingQueue).where(WaitingQueue.clinic_id == current_tenant.id)
    
    if doctor_id:
        statement = statement.where(WaitingQueue.doctor_id == doctor_id)
    
    if status:
        statement = statement.where(WaitingQueue.status == status)
    
    if priority:
        statement = statement.where(WaitingQueue.priority == priority)
    
    statement = statement.order_by(WaitingQueue.position.asc()).offset(offset).limit(limit)
    
    queue_entries = db.exec(statement).all()
    
    # Enrich with patient and appointment details
    result = []
    for entry in queue_entries:
        # Get patient details
        patient = db.exec(
            select("Patient").where("Patient.id == entry.patient_id")
        ).first()
        
        # Get appointment details
        appointment = db.exec(
            select("Appointment").where("Appointment.id == entry.appointment_id")
        ).first()
        
        entry_dict = entry.dict()
        entry_dict.update({
            "patient_name": patient.name if patient else None,
            "patient_phone": patient.phone if patient else None,
            "appointment_time": appointment.start_time if appointment else None,
            "appointment_type": appointment.appointment_type if appointment else None
        })
        
        result.append(WaitingQueueListResponse(**entry_dict))
    
    return result

@router.get("/{queue_id}/logs", response_model=List[WaitingQueueLogResponse])
async def get_queue_logs(
    queue_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get logs for a specific queue entry."""
    
    # Verify queue entry exists and belongs to clinic
    queue_entry = db.exec(
        select(WaitingQueue).where(
            and_(
                WaitingQueue.id == queue_id,
                WaitingQueue.clinic_id == current_tenant.id
            )
        )
    ).first()
    
    if not queue_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found"
        )
    
    # Get logs
    logs = db.exec(
        select(WaitingQueueLog).where(
            WaitingQueueLog.queue_id == queue_id
        ).order_by(WaitingQueueLog.created_at.desc()).offset(offset).limit(limit)
    ).all()
    
    return [WaitingQueueLogResponse.from_orm(log) for log in logs]

@router.get("/analytics")
async def get_queue_analytics(
    doctor_id: Optional[uuid.UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get queue analytics and metrics."""
    
    # Build query
    statement = select(WaitingQueue).where(WaitingQueue.clinic_id == current_tenant.id)
    
    if doctor_id:
        statement = statement.where(WaitingQueue.doctor_id == doctor_id)
    
    if start_date:
        statement = statement.where(WaitingQueue.enqueued_at >= start_date)
    
    if end_date:
        statement = statement.where(WaitingQueue.enqueued_at <= end_date)
    
    queue_entries = db.exec(statement).all()
    
    # Generate analytics
    analytics = QueueAnalytics.generate_queue_report(current_tenant.id, queue_entries)
    
    return analytics

# WebSocket endpoint for real-time updates
@router.websocket("/ws/{clinic_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    clinic_id: uuid.UUID,
    doctor_id: Optional[uuid.UUID] = None
):
    """WebSocket endpoint for real-time queue updates."""
    
    await websocket_service.connect(websocket, clinic_id, doctor_id)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_service.disconnect(websocket, clinic_id, doctor_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        websocket_service.disconnect(websocket, clinic_id, doctor_id)
