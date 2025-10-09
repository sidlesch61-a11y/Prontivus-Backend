"""
Patients API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.auth import get_current_user, require_patients_read, require_patients_write
from app.db.session import get_db_session
from app.models import Patient, AuditLog
from app.schemas import PatientCreate, PatientUpdate, PatientResponse, PaginationParams, PaginatedResponse

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def list_patients(
    search: Optional[str] = Query(None, description="Search by name or CPF"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """List patients with pagination and search."""
    query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
    
    # Add search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Patient.name.ilike(search_term),
                Patient.cpf.ilike(search_term)
            )
        )
    
    # Get total count
    count_query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            or_(
                Patient.name.ilike(search_term),
                Patient.cpf.ilike(search_term)
            )
        )
    
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    result = await db.execute(query)
    patients = result.scalars().all()
    
    return PaginatedResponse(
        items=[PatientResponse.from_orm(patient) for patient in patients],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: PatientCreate,
    current_user = Depends(require_patients_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new patient."""
    # Check if CPF already exists in clinic
    result = await db.execute(
        select(Patient).where(
            Patient.clinic_id == current_user.clinic_id,
            Patient.cpf == patient_data.cpf
        )
    )
    existing_patient = result.scalar_one_or_none()
    
    if existing_patient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient with this CPF already exists"
        )
    
    # Create patient
    patient = Patient(
        clinic_id=current_user.clinic_id,
        **patient_data.dict()
    )
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="patient_created",
        entity="patient",
        entity_id=patient.id,
        details={"patient_name": patient.name, "cpf": patient.cpf}
    )
    db.add(audit_log)
    await db.commit()
    
    return PatientResponse.from_orm(patient)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Get patient by ID."""
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id
        )
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return PatientResponse.from_orm(patient)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: str,
    update_data: PatientUpdate,
    current_user = Depends(require_patients_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Update patient information."""
    # Get patient
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id
        )
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(patient, field, value)
    
    await db.commit()
    await db.refresh(patient)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="patient_updated",
        entity="patient",
        entity_id=patient.id,
        details={"updated_fields": list(update_dict.keys())}
    )
    db.add(audit_log)
    await db.commit()
    
    return PatientResponse.from_orm(patient)


@router.delete("/{patient_id}")
async def delete_patient(
    patient_id: str,
    current_user = Depends(require_patients_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete patient."""
    # Get patient
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id
        )
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="patient_deleted",
        entity="patient",
        entity_id=patient.id,
        details={"patient_name": patient.name, "cpf": patient.cpf}
    )
    db.add(audit_log)
    
    # Delete patient
    await db.delete(patient)
    await db.commit()
    
    return {"message": "Patient deleted successfully"}
