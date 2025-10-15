"""
API endpoints for consultation management (vitals, attachments, queue, notes).
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
import os
import aiofiles

from app.db.session import get_db_session
from app.core.auth import get_current_user
from app.models.consultation_extended import (
    Vitals, VitalsCreate, VitalsResponse,
    Attachment, AttachmentCreate, AttachmentResponse,
    QueueStatus, QueueStatusResponse,
    ConsultationNotes, ConsultationNotesUpdate,
    VoiceNote, VoiceNoteCreate
)
from app.models.database import User, Patient, Appointment

router = APIRouter(prefix="/consultation-management", tags=["Consultation Management"])

# ============================================================================
# VITALS ENDPOINTS
# ============================================================================

@router.post("/vitals", response_model=VitalsResponse)
async def create_vitals(
    vitals_data: VitalsCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create or update vitals for a consultation."""
    try:
        # Check if vitals already exist for this consultation
        stmt = select(Vitals).where(Vitals.consultation_id == vitals_data.consultation_id)
        result = await db.execute(stmt)
        existing_vitals = result.scalar_one_or_none()
        
        if existing_vitals:
            # Update existing vitals
            for key, value in vitals_data.dict(exclude_unset=True).items():
                if key not in ['consultation_id', 'patient_id']:
                    setattr(existing_vitals, key, value)
            existing_vitals.updated_at = datetime.now()
            existing_vitals.recorded_by = current_user.id
            existing_vitals.recorded_at = datetime.now()
            await db.commit()
            await db.refresh(existing_vitals)
            return existing_vitals
        else:
            # Create new vitals
            new_vitals = Vitals(
                **vitals_data.dict(),
                recorded_by=current_user.id,
                recorded_at=datetime.now()
            )
            db.add(new_vitals)
            await db.commit()
            await db.refresh(new_vitals)
            return new_vitals
            
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating vitals: {str(e)}")


@router.get("/vitals/{consultation_id}", response_model=VitalsResponse)
async def get_vitals(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get vitals for a consultation."""
    stmt = select(Vitals).where(Vitals.consultation_id == consultation_id)
    result = await db.execute(stmt)
    vitals = result.scalar_one_or_none()
    
    if not vitals:
        raise HTTPException(status_code=404, detail="Vitals not found")
    
    return vitals


# ============================================================================
# ATTACHMENTS ENDPOINTS
# ============================================================================

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads/attachments")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/attachments/upload", response_model=AttachmentResponse)
async def upload_attachment(
    file: UploadFile = File(...),
    consultation_id: str = Form(...),
    patient_id: str = Form(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Upload an attachment for a consultation."""
    try:
        # Validate file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="File type not allowed")
        
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        
        # Create attachment record
        attachment = Attachment(
            consultation_id=uuid.UUID(consultation_id),
            patient_id=uuid.UUID(patient_id),
            file_name=file.filename,
            file_type=file.content_type,
            file_size=len(content),
            file_url=f"/uploads/attachments/{unique_filename}",
            description=description,
            category=category,
            uploaded_by=current_user.id
        )
        
        db.add(attachment)
        await db.commit()
        await db.refresh(attachment)
        
        return attachment
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error uploading attachment: {str(e)}")


@router.get("/attachments/{consultation_id}", response_model=List[AttachmentResponse])
async def get_attachments(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all attachments for a consultation."""
    stmt = select(Attachment).where(Attachment.consultation_id == consultation_id).order_by(Attachment.uploaded_at.desc())
    result = await db.execute(stmt)
    attachments = result.scalars().all()
    
    return attachments


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete an attachment."""
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Delete file from disk
    try:
        file_path = os.path.join(".", attachment.file_url.lstrip("/"))
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error deleting file: {e}")
    
    # Delete record
    await db.delete(attachment)
    await db.commit()
    
    return {"message": "Attachment deleted successfully"}


# ============================================================================
# QUEUE MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/queue", response_model=List[QueueStatusResponse])
async def get_queue(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get patient queue for current doctor.
    Automatically creates queue entries for today's appointments if they don't exist.
    """
    try:
        # Get today's date range
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # FIRST: Auto-sync appointments to queue
        # Get today's appointments for this doctor that don't have queue entries
        appointments_without_queue = await db.execute(
            select(Appointment, Patient).join(
                Patient, Appointment.patient_id == Patient.id
            ).where(
                and_(
                    Appointment.doctor_id == current_user.id,
                    Appointment.start_time >= today_start,
                    Appointment.start_time < today_end,
                    Appointment.status.in_(['scheduled', 'confirmed', 'checked_in', 'in_progress'])
                )
            )
        )
        appointments_rows = appointments_without_queue.all()
        
        # Create queue entries for appointments without them
        for appointment, patient in appointments_rows:
            # Check if queue entry exists
            existing_queue = await db.execute(
                select(QueueStatus).where(QueueStatus.appointment_id == appointment.id)
            )
            if not existing_queue.scalar_one_or_none():
                # Create queue entry
                queue_entry = QueueStatus(
                    appointment_id=appointment.id,
                    patient_id=appointment.patient_id,
                    doctor_id=appointment.doctor_id,
                    clinic_id=appointment.clinic_id,
                    status="waiting",
                    priority=0
                )
                db.add(queue_entry)
        
        await db.commit()
        
        # NOW: Get the queue
        stmt = select(QueueStatus, Patient, Appointment).join(
            Patient, QueueStatus.patient_id == Patient.id
        ).join(
            Appointment, QueueStatus.appointment_id == Appointment.id
        ).where(
            and_(
                QueueStatus.doctor_id == current_user.id,
                Appointment.start_time >= today_start,
                Appointment.start_time < today_end
            )
        )
        
        if status:
            stmt = stmt.where(QueueStatus.status == status)
        
        stmt = stmt.order_by(QueueStatus.priority.desc(), QueueStatus.created_at.asc())
        
        result = await db.execute(stmt)
        rows = result.all()
        
        # Build response
        queue_list = []
        for queue_status, patient, appointment in rows:
            queue_item = QueueStatusResponse(
                id=queue_status.id,
                appointment_id=queue_status.appointment_id,
                patient_id=queue_status.patient_id,
                doctor_id=queue_status.doctor_id,
                status=queue_status.status,
                priority=queue_status.priority,
                notes=queue_status.notes,
                patient_name=patient.name,
                patient_age=calculate_age(patient.birthdate) if patient.birthdate else None,
                appointment_time=appointment.start_time,
                called_at=queue_status.called_at,
                started_at=queue_status.started_at,
                completed_at=queue_status.completed_at
            )
            queue_list.append(queue_item)
        
        return queue_list
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error fetching queue: {str(e)}")


@router.post("/queue/call/{patient_id}")
async def call_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Call a patient from the queue."""
    try:
        # Find queue entry - get the first waiting entry for this patient
        stmt = select(QueueStatus).where(
            and_(
                QueueStatus.patient_id == patient_id,
                QueueStatus.doctor_id == current_user.id,
                QueueStatus.status == "waiting"
            )
        ).order_by(QueueStatus.priority.desc(), QueueStatus.created_at.asc()).limit(1)
        result = await db.execute(stmt)
        queue_entry = result.scalar_one_or_none()
        
        if not queue_entry:
            raise HTTPException(status_code=404, detail="Patient not in queue")
        
        # Update status
        queue_entry.status = "in_progress"
        queue_entry.called_at = datetime.now()
        queue_entry.started_at = datetime.now()
        queue_entry.updated_at = datetime.now()
        
        await db.commit()
        await db.refresh(queue_entry)
        
        # TODO: Trigger WebSocket broadcast for reception
        # await broadcast_queue_update(queue_entry)
        
        return {"message": "Patient called successfully", "queue_id": str(queue_entry.id)}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error calling patient: {str(e)}")


@router.post("/queue/finalize/{consultation_id}")
async def finalize_consultation(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Finalize a consultation and update queue status."""
    try:
        # Get consultation to find appointment_id
        from app.models.database import Consultation
        
        stmt = select(Consultation).where(Consultation.id == consultation_id)
        result = await db.execute(stmt)
        consultation = result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")
        
        # Update queue status
        stmt = select(QueueStatus).where(
            and_(
                QueueStatus.appointment_id == consultation.appointment_id,
                QueueStatus.doctor_id == current_user.id
            )
        )
        result = await db.execute(stmt)
        queue_entry = result.scalar_one_or_none()
        
        if queue_entry:
            queue_entry.status = "completed"
            queue_entry.completed_at = datetime.now()
            queue_entry.updated_at = datetime.now()
        
        # Update consultation timestamp
        consultation.updated_at = datetime.now()
        
        # Also update appointment status so reservation list reflects changes
        try:
            from app.models.database import Appointment
            appt_stmt = select(Appointment).where(Appointment.id == consultation.appointment_id)
            appt_result = await db.execute(appt_stmt)
            appointment = appt_result.scalar_one_or_none()
            if appointment:
                appointment.status = "attended"
                appointment.updated_at = datetime.now()
        except Exception:
            # Do not block finalization if appointment update fails
            pass

        await db.commit()
        
        # Get next patient in queue
        stmt = select(QueueStatus).where(
            and_(
                QueueStatus.doctor_id == current_user.id,
                QueueStatus.status == "waiting"
            )
        ).order_by(QueueStatus.priority.desc(), QueueStatus.created_at.asc()).limit(1)
        
        result = await db.execute(stmt)
        next_patient = result.scalar_one_or_none()
        
        return {
            "message": "Consultation finalized successfully",
            "next_patient_id": str(next_patient.patient_id) if next_patient else None
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error finalizing consultation: {str(e)}")


@router.post("/queue/return/{consultation_id}")
async def return_patient_to_waiting(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Return a patient to waiting state without completing the consultation."""
    try:
        from app.models.database import Consultation

        # Load consultation to get appointment_id
        stmt = select(Consultation).where(Consultation.id == consultation_id)
        result = await db.execute(stmt)
        consultation = result.scalar_one_or_none()

        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")

        # Find queue entry for this appointment/doctor
        stmt = select(QueueStatus).where(
            and_(
                QueueStatus.appointment_id == consultation.appointment_id,
                QueueStatus.doctor_id == current_user.id
            )
        )
        result = await db.execute(stmt)
        queue_entry = result.scalar_one_or_none()

        if not queue_entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        # Set back to waiting, clear in-progress timestamps
        queue_entry.status = "waiting"
        queue_entry.updated_at = datetime.now()
        queue_entry.called_at = None
        queue_entry.started_at = None

        await db.commit()

        return {"message": "Patient returned to waiting queue"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error returning patient to queue: {str(e)}")


# ============================================================================
# CONSULTATION NOTES ENDPOINTS
# ============================================================================

@router.post("/notes/{consultation_id}")
async def update_consultation_notes(
    consultation_id: uuid.UUID,
    notes_data: ConsultationNotesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update consultation notes (auto-save)."""
    try:
        # Check if notes exist
        stmt = select(ConsultationNotes).where(ConsultationNotes.consultation_id == consultation_id)
        result = await db.execute(stmt)
        existing_notes = result.scalar_one_or_none()
        
        if existing_notes:
            # Update existing notes
            for key, value in notes_data.dict(exclude_unset=True).items():
                if value is not None:
                    setattr(existing_notes, key, value)
            existing_notes.updated_at = datetime.now()
            existing_notes.auto_saved_at = datetime.now()
            await db.commit()
            await db.refresh(existing_notes)
            return existing_notes
        else:
            # Create new notes
            new_notes = ConsultationNotes(
                consultation_id=consultation_id,
                **notes_data.dict(exclude_unset=True),
                auto_saved_at=datetime.now()
            )
            db.add(new_notes)
            await db.commit()
            await db.refresh(new_notes)
            return new_notes
            
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating notes: {str(e)}")


@router.get("/notes/{consultation_id}")
async def get_consultation_notes(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get consultation notes."""
    stmt = select(ConsultationNotes).where(ConsultationNotes.consultation_id == consultation_id)
    result = await db.execute(stmt)
    notes = result.scalar_one_or_none()
    
    if not notes:
        # Return empty notes if none exist
        return ConsultationNotes(consultation_id=consultation_id)
    
    return notes


# ============================================================================
# VOICE NOTES ENDPOINTS
# ============================================================================

@router.post("/voice-notes/upload")
async def upload_voice_note(
    audio_file: UploadFile = File(...),
    consultation_id: str = Form(...),
    note_type: str = Form("anamnese"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Upload a voice note for transcription."""
    try:
        # Save audio file
        audio_dir = os.getenv("UPLOAD_DIR", "./uploads/voice_notes")
        os.makedirs(audio_dir, exist_ok=True)
        
        file_ext = os.path.splitext(audio_file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(audio_dir, unique_filename)
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await audio_file.read()
            await out_file.write(content)
        
        # Create voice note record
        voice_note = VoiceNote(
            consultation_id=uuid.UUID(consultation_id),
            recorded_by=current_user.id,
            audio_url=f"/uploads/voice_notes/{unique_filename}",
            duration_seconds=0,  # TODO: Calculate from audio file
            note_type=note_type
        )
        
        db.add(voice_note)
        await db.commit()
        await db.refresh(voice_note)
        
        # TODO: Trigger async transcription task
        # await transcribe_audio_task.delay(voice_note.id)
        
        return {"message": "Voice note uploaded successfully", "voice_note_id": str(voice_note.id)}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error uploading voice note: {str(e)}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_age(birthdate) -> int:
    """Calculate age from birthdate."""
    if not birthdate:
        return None
    today = datetime.now().date()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

