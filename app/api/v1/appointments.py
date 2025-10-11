"""
Appointments API endpoints with concurrency control.
"""

from typing import List, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, text, cast, String
from sqlalchemy.exc import IntegrityError

from app.core.auth import get_current_user, require_appointments_read, require_appointments_write
from app.db.session import get_db_transaction, get_db_session
from app.models import Appointment, Patient, User, AuditLog
from app.schemas import AppointmentCreate, AppointmentUpdate, AppointmentResponse, PaginationParams, PaginatedResponse

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def list_appointments(
    day: Optional[date] = Query(None, description="Filter by specific day"),
    doctor_id: Optional[str] = Query(None, description="Filter by doctor ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_appointments_read),
    db: AsyncSession = Depends(get_db_transaction)
):
    """List appointments with filters and pagination."""
    query = select(Appointment).where(Appointment.clinic_id == current_user.clinic_id)
    
    # Apply filters
    if day:
        start_of_day = datetime.combine(day, datetime.min.time())
        end_of_day = datetime.combine(day, datetime.max.time())
        query = query.where(
            and_(
                Appointment.start_time >= start_of_day,
                Appointment.start_time <= end_of_day
            )
        )
    
    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
    
    if status:
        query = query.where(Appointment.status == status)
    
    # Get total count
    count_query = select(func.count(Appointment.id)).where(Appointment.clinic_id == current_user.clinic_id)
    if day:
        start_of_day = datetime.combine(day, datetime.min.time())
        end_of_day = datetime.combine(day, datetime.max.time())
        count_query = count_query.where(
            and_(
                Appointment.start_time >= start_of_day,
                Appointment.start_time <= end_of_day
            )
        )
    if doctor_id:
        count_query = count_query.where(Appointment.doctor_id == doctor_id)
    if status:
        count_query = count_query.where(Appointment.status == status)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Appointment.start_time)
    
    result = await db.execute(query)
    appointments = result.scalars().all()
    
    # Get related data
    appointment_responses = []
    for appointment in appointments:
        # Get patient name
        patient_result = await db.execute(
            select(Patient.name).where(Patient.id == appointment.patient_id)
        )
        patient_name = patient_result.scalar()
        
        # Get doctor name
        doctor_result = await db.execute(
            select(User.name).where(User.id == appointment.doctor_id)
        )
        doctor_name = doctor_result.scalar()
        
        appointment_data = AppointmentResponse.from_orm(appointment)
        appointment_data.patient_name = patient_name
        appointment_data.doctor_name = doctor_name
        appointment_responses.append(appointment_data)
    
    return PaginatedResponse(
        items=appointment_responses,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    appointment_data: AppointmentCreate,
    current_user = Depends(require_appointments_write),
    db: AsyncSession = Depends(get_db_transaction)
):
    """Create a new appointment with concurrency control."""
    
    # Use PostgreSQL advisory lock to prevent double-booking
    # Lock based on doctor_id and appointment time
    lock_id = hash(f"{appointment_data.doctor_id}_{appointment_data.start_time.date()}")
    
    lock_acquired = False
    try:
        # Acquire advisory lock
        await db.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": abs(lock_id) % (2**63)})
        lock_acquired = True
        
        # Check for overlapping appointments
        # Cast status to String to avoid ENUM type mismatch with PostgreSQL
        overlap_query = select(func.count(Appointment.id)).where(
            and_(
                Appointment.doctor_id == appointment_data.doctor_id,
                Appointment.clinic_id == current_user.clinic_id,
                cast(Appointment.status, String).in_(["scheduled", "checked_in", "in_progress"]),
                Appointment.start_time < appointment_data.end_time,
                Appointment.end_time > appointment_data.start_time
            )
        )
        
        overlap_result = await db.execute(overlap_query)
        overlap_count = overlap_result.scalar()
        
        if overlap_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Appointment time conflicts with existing appointment"
            )
        
        # Verify patient exists and belongs to clinic
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == appointment_data.patient_id,
                Patient.clinic_id == current_user.clinic_id
            )
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
        
        # Verify doctor exists and belongs to clinic
        doctor_result = await db.execute(
            select(User).where(
                User.id == appointment_data.doctor_id,
                User.clinic_id == current_user.clinic_id,
                User.role.in_(["doctor", "admin", "superadmin"])
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )
        
        # Create appointment
        appointment = Appointment(
            clinic_id=current_user.clinic_id,
            **appointment_data.dict()
        )
        db.add(appointment)
        await db.flush()  # Get appointment ID
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="appointment_created",
            entity="appointment",
            entity_id=appointment.id,
            details={
                "patient_id": str(appointment.patient_id),
                "doctor_id": str(appointment.doctor_id),
                "start_time": appointment.start_time.isoformat(),
                "end_time": appointment.end_time.isoformat()
            }
        )
        db.add(audit_log)
        
        await db.commit()
        
        # Get related data for response
        appointment_response = AppointmentResponse.from_orm(appointment)
        appointment_response.patient_name = patient.name
        appointment_response.doctor_name = doctor.name
        
        return appointment_response
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        print(f"Error creating appointment: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create appointment: {str(e)}"
        )
    finally:
        # Release advisory lock only if it was acquired
        if lock_acquired:
            try:
                await db.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": abs(lock_id) % (2**63)})
            except Exception:
                pass  # Ignore unlock errors


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: str,
    current_user = Depends(require_appointments_read),
    db: AsyncSession = Depends(get_db_transaction)
):
    """Get appointment by ID."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == current_user.clinic_id
        )
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Get related data
    patient_result = await db.execute(
        select(Patient.name).where(Patient.id == appointment.patient_id)
    )
    patient_name = patient_result.scalar()
    
    doctor_result = await db.execute(
        select(User.name).where(User.id == appointment.doctor_id)
    )
    doctor_name = doctor_result.scalar()
    
    appointment_response = AppointmentResponse.from_orm(appointment)
    appointment_response.patient_name = patient_name
    appointment_response.doctor_name = doctor_name
    
    return appointment_response


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: str,
    update_data: AppointmentUpdate,
    current_user = Depends(require_appointments_write),
    db: AsyncSession = Depends(get_db_transaction)
):
    """Update appointment."""
    # Get appointment
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == current_user.clinic_id
        )
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(appointment, field, value)
    
    await db.commit()
    await db.refresh(appointment)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="appointment_updated",
        entity="appointment",
        entity_id=appointment.id,
        details={"updated_fields": list(update_dict.keys())}
    )
    db.add(audit_log)
    await db.commit()
    
    # Get related data for response
    patient_result = await db.execute(
        select(Patient.name).where(Patient.id == appointment.patient_id)
    )
    patient_name = patient_result.scalar()
    
    doctor_result = await db.execute(
        select(User.name).where(User.id == appointment.doctor_id)
    )
    doctor_name = doctor_result.scalar()
    
    appointment_response = AppointmentResponse.from_orm(appointment)
    appointment_response.patient_name = patient_name
    appointment_response.doctor_name = doctor_name
    
    return appointment_response


@router.delete("/{appointment_id}")
async def delete_appointment(
    appointment_id: str,
    current_user = Depends(require_appointments_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete appointment."""
    # Get appointment
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == current_user.clinic_id
        )
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Create audit log before deletion
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="appointment_deleted",
        entity="appointment",
        entity_id=appointment.id,
        details={
            "patient_id": str(appointment.patient_id),
            "doctor_id": str(appointment.doctor_id),
            "start_time": appointment.start_time.isoformat(),
            "status": appointment.status
        }
    )
    db.add(audit_log)
    
    # Delete appointment
    await db.delete(appointment)
    await db.commit()
    
    return {"message": "Appointment deleted successfully"}


@router.post("/{appointment_id}/check-in")
async def check_in_appointment(
    appointment_id: str,
    current_user = Depends(require_appointments_write),
    db: AsyncSession = Depends(get_db_transaction)
):
    """Check in patient for appointment."""
    # Get appointment
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == current_user.clinic_id
        )
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    if appointment.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment is not in scheduled status"
        )
    
    # Update status
    appointment.status = "checked_in"
    await db.commit()
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="appointment_checked_in",
        entity="appointment",
        entity_id=appointment.id,
        details={"previous_status": "scheduled"}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "Patient checked in successfully"}


@router.post("/{appointment_id}/complete")
async def complete_appointment(
    appointment_id: str,
    current_user = Depends(require_appointments_write),
    db: AsyncSession = Depends(get_db_transaction)
):
    """Complete appointment."""
    # Get appointment
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == current_user.clinic_id
        )
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    if appointment.status not in ["checked_in", "in_progress"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment is not in progress"
        )
    
    # Update status
    appointment.status = "completed"
    await db.commit()
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="appointment_completed",
        entity="appointment",
        entity_id=appointment.id,
        details={"previous_status": appointment.status}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "Appointment completed successfully"}
