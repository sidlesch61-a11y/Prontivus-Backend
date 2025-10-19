"""
Basic Prescription API for simple CRUD operations
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Optional
import uuid
from datetime import datetime

from app.db.session import get_db_session
from app.core.auth import AuthDependencies
from app.models.database import Prescription as PrescriptionDB, Patient, User
from app.schemas import PrescriptionCreate, PrescriptionUpdate, PrescriptionResponse
from pydantic import BaseModel

router = APIRouter(tags=["Prescriptions"])


@router.post("/", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_prescription(
    prescription_data: PrescriptionCreate,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new basic prescription."""
    try:
        # Verify patient exists
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == prescription_data.patient_id,
                Patient.clinic_id == current_user.clinic_id
            )
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
        
        # Create prescription(s) - support both single and multiple medications
        created_prescriptions = []
        prescription_ids = []
        
        # Check if this has medications list (new format)
        if hasattr(prescription_data, 'medications') and prescription_data.medications:
            # New format: array of medications
            # Use RAW SQL to insert WITHOUT record_id field (DB constraint workaround)
            from sqlalchemy import text
            import uuid as uuid_module
            
            for medication in prescription_data.medications:
                prescription_id = uuid_module.uuid4()
                now = datetime.now()
                
                # Use raw SQL - only insert columns that exist and are needed
                await db.execute(
                    text("""
                        INSERT INTO prescriptions 
                        (id, medication_name, dosage, frequency, duration, notes, clinic_id, created_at, updated_at)
                        VALUES 
                        (:id, :medication_name, :dosage, :frequency, :duration, :notes, :clinic_id, :created_at, :updated_at)
                    """),
                    {
                        "id": str(prescription_id),
                        "medication_name": medication.medication_name,
                        "dosage": medication.dosage,
                        "frequency": medication.frequency or "",
                        "duration": medication.duration or "",
                        "notes": prescription_data.notes or "",
                        "clinic_id": str(current_user.clinic_id),
                        "created_at": now,
                        "updated_at": now
                    }
                )
                prescription_ids.append(prescription_id)
        else:
            # Old format: single medication (also use raw SQL)
            from sqlalchemy import text
            import uuid as uuid_module
            
            prescription_id = uuid_module.uuid4()
            now = datetime.now()
            
            await db.execute(
                text("""
                    INSERT INTO prescriptions 
                    (id, medication_name, dosage, frequency, duration, notes, clinic_id, created_at, updated_at)
                    VALUES 
                    (:id, :medication_name, :dosage, :frequency, :duration, :notes, :clinic_id, :created_at, :updated_at)
                """),
                {
                    "id": str(prescription_id),
                    "medication_name": prescription_data.medication_name,
                    "dosage": prescription_data.dosage,
                    "frequency": prescription_data.frequency or "",
                    "duration": prescription_data.duration or "",
                    "notes": prescription_data.notes or "",
                    "clinic_id": str(current_user.clinic_id),
                    "created_at": now,
                    "updated_at": now
                }
            )
            prescription_ids.append(prescription_id)
        
        await db.commit()
        
        # Fetch the created prescription(s) to return
        result = await db.execute(
            select(PrescriptionDB).where(PrescriptionDB.id == prescription_ids[0])
        )
        first_prescription = result.scalar_one()
        
        # Return response
        response = PrescriptionResponse.model_validate(first_prescription)
        response.patient_name = patient.name
        response.doctor_name = current_user.name
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create prescription: {str(e)}"
        )


@router.get("/", response_model=List[PrescriptionResponse])
async def list_prescriptions(
    search: Optional[str] = Query(None, description="Search by medication or patient name"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List prescriptions with optional filters."""
    try:
        query = select(PrescriptionDB).where(PrescriptionDB.clinic_id == current_user.clinic_id)
        
        if patient_id:
            query = query.where(PrescriptionDB.record_id == patient_id)
        
        if search:
            query = query.where(
                or_(
                    PrescriptionDB.medication_name.ilike(f"%{search}%"),
                    PrescriptionDB.notes.ilike(f"%{search}%")
                )
            )
        
        query = query.order_by(PrescriptionDB.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)
        
        result = await db.execute(query)
        prescriptions = result.scalars().all()
        
        # Get patient names
        response_list = []
        for prescription in prescriptions:
            response = PrescriptionResponse.model_validate(prescription)
            
            # Get patient name if record_id exists
            if prescription.record_id:
                from app.models.database import MedicalRecord
                record_result = await db.execute(
                    select(MedicalRecord).where(MedicalRecord.id == prescription.record_id)
                )
                record = record_result.scalar_one_or_none()
                
                if record and record.patient_id:
                    patient_result = await db.execute(
                        select(Patient).where(Patient.id == record.patient_id)
                    )
                    patient = patient_result.scalar_one_or_none()
                    if patient:
                        response.patient_name = patient.name
                        response.patient_id = str(patient.id)
            
            response_list.append(response)
        
        return response_list
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list prescriptions: {str(e)}"
        )


@router.get("/{prescription_id}", response_model=PrescriptionResponse)
async def get_prescription(
    prescription_id: str,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get a prescription by ID."""
    try:
        result = await db.execute(
            select(PrescriptionDB).where(
                PrescriptionDB.id == prescription_id,
                PrescriptionDB.clinic_id == current_user.clinic_id
            )
        )
        prescription = result.scalar_one_or_none()
        
        if not prescription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prescription not found"
            )
        
        response = PrescriptionResponse.model_validate(prescription)
        
        # Get patient name
        if prescription.record_id:
            from app.models.database import MedicalRecord
            record_result = await db.execute(
                select(MedicalRecord).where(MedicalRecord.id == prescription.record_id)
            )
            record = record_result.scalar_one_or_none()
            
            if record and record.patient_id:
                patient_result = await db.execute(
                    select(Patient).where(Patient.id == record.patient_id)
                )
                patient = patient_result.scalar_one_or_none()
                if patient:
                    response.patient_name = patient.name
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prescription: {str(e)}"
        )


@router.patch("/{prescription_id}", response_model=PrescriptionResponse)
async def update_prescription(
    prescription_id: str,
    update_data: PrescriptionUpdate,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update a prescription."""
    try:
        result = await db.execute(
            select(PrescriptionDB).where(
                PrescriptionDB.id == prescription_id,
                PrescriptionDB.clinic_id == current_user.clinic_id
            )
        )
        prescription = result.scalar_one_or_none()
        
        if not prescription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prescription not found"
            )
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(prescription, field, value)
        
        await db.commit()
        await db.refresh(prescription)
        
        response = PrescriptionResponse.model_validate(prescription)
        
        # Get patient name
        if prescription.record_id:
            from app.models.database import MedicalRecord
            record_result = await db.execute(
                select(MedicalRecord).where(MedicalRecord.id == prescription.record_id)
            )
            record = record_result.scalar_one_or_none()
            
            if record and record.patient_id:
                patient_result = await db.execute(
                    select(Patient).where(Patient.id == record.patient_id)
                )
                patient = patient_result.scalar_one_or_none()
                if patient:
                    response.patient_name = patient.name
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update prescription: {str(e)}"
        )


@router.delete("/{prescription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prescription(
    prescription_id: str,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a prescription."""
    try:
        result = await db.execute(
            select(PrescriptionDB).where(
                PrescriptionDB.id == prescription_id,
                PrescriptionDB.clinic_id == current_user.clinic_id
            )
        )
        prescription = result.scalar_one_or_none()
        
        if not prescription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prescription not found"
            )
        
        await db.delete(prescription)
        await db.commit()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete prescription: {str(e)}"
        )

