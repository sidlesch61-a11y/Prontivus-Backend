"""
Medical records API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.auth import get_current_user, require_medical_records_read, require_medical_records_write
from app.db.session import get_db_session
from app.models import MedicalRecord, Appointment, Patient, User, AuditLog
from app.schemas import MedicalRecordCreate, MedicalRecordUpdate, MedicalRecordResponse, PaginationParams, PaginatedResponse

router = APIRouter()


@router.get("/", response_model=dict)
async def list_medical_records():
    """Simple root endpoint to test if routing works."""
    return {"message": "Root medical records endpoint is working", "status": "ok"}


@router.get("/list", response_model=PaginatedResponse)
async def list_medical_records_list(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    doctor_id: Optional[str] = Query(None, description="Filter by doctor ID"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_medical_records_read),
    db: AsyncSession = Depends(get_db_session)
):
    """List medical records with filters and pagination at /list path."""
    query = select(MedicalRecord).where(MedicalRecord.clinic_id == current_user.clinic_id)
    
    # Apply filters
    if patient_id:
        query = query.where(MedicalRecord.patient_id == patient_id)
    
    if doctor_id:
        query = query.where(MedicalRecord.doctor_id == doctor_id)
    
    # Get total count
    count_query = select(MedicalRecord).where(MedicalRecord.clinic_id == current_user.clinic_id)
    if patient_id:
        count_query = count_query.where(MedicalRecord.patient_id == patient_id)
    if doctor_id:
        count_query = count_query.where(MedicalRecord.doctor_id == doctor_id)
    
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(MedicalRecord.created_at.desc())
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    # Get related data
    record_responses = []
    for record in records:
        # Get patient name
        patient_result = await db.execute(
            select(Patient.name).where(Patient.id == record.patient_id)
        )
        patient_name = patient_result.scalar()
        
        # Get doctor name
        doctor_result = await db.execute(
            select(User.name).where(User.id == record.doctor_id)
        )
        doctor_name = doctor_result.scalar()
        
        record_data = MedicalRecordResponse.model_validate(record)
        record_data.patient_name = patient_name
        record_data.doctor_name = doctor_name
        record_responses.append(record_data)
    
    return PaginatedResponse(
        items=record_responses,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.post("/create", response_model=MedicalRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_medical_record(
    record_data: MedicalRecordCreate,
    current_user = Depends(require_medical_records_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new medical record."""
    try:
        # Verify patient exists and belongs to clinic
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == record_data.patient_id,
                Patient.clinic_id == current_user.clinic_id
            )
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
        
        # Verify appointment if provided
        if record_data.appointment_id:
            appointment_result = await db.execute(
                select(Appointment).where(
                    Appointment.id == record_data.appointment_id,
                    Appointment.clinic_id == current_user.clinic_id
                )
            )
            appointment = appointment_result.scalar_one_or_none()
            
            if not appointment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Appointment not found"
                )
        
        # Create medical record
        record = MedicalRecord(
            clinic_id=current_user.clinic_id,
            doctor_id=current_user.id,
            **record_data.dict()
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="medical_record_created",
            entity="medical_record",
            entity_id=record.id,
            details={
                "appointment_id": str(record.appointment_id) if record.appointment_id else None,
                "patient_id": str(record.patient_id)
            }
        )
        db.add(audit_log)
        await db.commit()
        
        # Get related data for response
        record_response = MedicalRecordResponse.model_validate(record)
        record_response.patient_name = patient.name
        record_response.doctor_name = current_user.name
        
        return record_response
    
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        print(f"Error creating medical record: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create medical record: {str(e)}"
        )


@router.get("/{record_id}", response_model=MedicalRecordResponse)
async def get_medical_record(
    record_id: str,
    current_user = Depends(require_medical_records_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Get medical record by ID."""
    result = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.id == record_id,
            MedicalRecord.clinic_id == current_user.clinic_id
        )
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical record not found"
        )
    
    # Get related data
    patient_result = await db.execute(
        select(Patient.name).where(Patient.id == record.patient_id)
    )
    patient_name = patient_result.scalar()
    
    doctor_result = await db.execute(
        select(User.name).where(User.id == record.doctor_id)
    )
    doctor_name = doctor_result.scalar()
    
    record_response = MedicalRecordResponse.model_validate(record)
    record_response.patient_name = patient_name
    record_response.doctor_name = doctor_name
    
    return record_response


@router.patch("/{record_id}", response_model=MedicalRecordResponse)
async def update_medical_record(
    record_id: str,
    update_data: MedicalRecordUpdate,
    current_user = Depends(require_medical_records_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Update medical record."""
    # Get record
    result = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.id == record_id,
            MedicalRecord.clinic_id == current_user.clinic_id
        )
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical record not found"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(record, field, value)
    
    await db.commit()
    await db.refresh(record)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="medical_record_updated",
        entity="medical_record",
        entity_id=record.id,
        details={"updated_fields": list(update_dict.keys())}
    )
    db.add(audit_log)
    await db.commit()
    
    # Get related data for response
    patient_result = await db.execute(
        select(Patient.name).where(Patient.id == record.patient_id)
    )
    patient_name = patient_result.scalar()
    
    doctor_result = await db.execute(
        select(User.name).where(User.id == record.doctor_id)
    )
    doctor_name = doctor_result.scalar()
    
    record_response = MedicalRecordResponse.model_validate(record)
    record_response.patient_name = patient_name
    record_response.doctor_name = doctor_name
    
    return record_response


@router.get("/patient/{patient_id}", response_model=List[MedicalRecordResponse])
async def get_patient_records(
    patient_id: str,
    current_user = Depends(require_medical_records_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all medical records for a patient."""
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
            detail="Patient not found"
        )
    
    # Get records
    result = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.patient_id == patient_id,
            MedicalRecord.clinic_id == current_user.clinic_id
        ).order_by(MedicalRecord.created_at.desc())
    )
    records = result.scalars().all()
    
    # Get related data
    record_responses = []
    for record in records:
        doctor_result = await db.execute(
            select(User.name).where(User.id == record.doctor_id)
        )
        doctor_name = doctor_result.scalar()
        
        record_data = MedicalRecordResponse.model_validate(record)
        record_data.patient_name = patient.name
        record_data.doctor_name = doctor_name
        record_responses.append(record_data)
    
    return record_responses


@router.delete("/{record_id}")
async def delete_medical_record(
    record_id: str,
    current_user = Depends(require_medical_records_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete medical record."""
    # Get record
    result = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.id == record_id,
            MedicalRecord.clinic_id == current_user.clinic_id
        )
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical record not found"
        )
    
    # Create audit log before deletion
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="medical_record_deleted",
        entity="medical_record",
        entity_id=record.id,
        details={
            "patient_id": str(record.patient_id),
            "diagnosis": record.diagnosis,
            "icd_code": record.icd_code
        }
    )
    db.add(audit_log)
    
    # Delete record
    await db.delete(record)
    await db.commit()
    
    return {"message": "Medical record deleted successfully"}
