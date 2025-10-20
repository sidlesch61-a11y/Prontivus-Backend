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
from app.core.auth import get_current_user
from app.models.database import Prescription as PrescriptionDB, Patient, User
from app.schemas import PrescriptionCreate, PrescriptionUpdate, PrescriptionResponse
from pydantic import BaseModel

router = APIRouter(tags=["Prescriptions"])

@router.get("/test")
async def test_prescriptions():
    """Test endpoint to verify router is working."""
    return {"message": "Prescriptions router is working", "status": "ok"}

@router.get("/list")
async def list_prescriptions_with_list(
    search: Optional[str] = Query(None, description="Search by medication or patient name"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List prescriptions with /list endpoint for frontend compatibility."""
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
        
        # Convert to simple dict format for frontend compatibility
        prescription_list = []
        for prescription in prescriptions:
            prescription_list.append({
                "id": str(prescription.id),
                "record_id": str(prescription.record_id) if prescription.record_id else None,
                "clinic_id": str(prescription.clinic_id),
                "medication_name": prescription.medication_name,
                "dosage": prescription.dosage,
                "frequency": prescription.frequency,
                "duration": prescription.duration,
                "notes": prescription.notes,
                "created_at": prescription.created_at.isoformat() if prescription.created_at else None,
                "updated_at": prescription.updated_at.isoformat() if prescription.updated_at else None
            })
        
        return {
            "items": prescription_list,
            "total": len(prescription_list),
            "page": page,
            "size": size,
            "pages": 1  # Simplified for now
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list prescriptions: {str(e)}"
        )


@router.post("/", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_prescription(
    prescription_data: dict,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new basic prescription."""
    try:
        # Extract patient_id from dict
        patient_id = prescription_data.get('patient_id')
        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id is required"
            )
        
        # Verify patient exists
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
        
        # Create prescription(s) - support both single and multiple medications
        created_prescriptions = []
        prescription_ids = []
        
        # Check if this has medications list (new format)
        if 'medications' in prescription_data and prescription_data['medications']:
            # New format: array of medications
            # Use RAW SQL to insert WITHOUT record_id field (DB constraint workaround)
            from sqlalchemy import text
            import uuid as uuid_module
            
            for medication in prescription_data['medications']:
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
                        "medication_name": medication.get('medication_name', medication.get('name', '')),
                        "dosage": medication.get('dosage'),
                        "frequency": medication.get('frequency') or "",
                        "duration": medication.get('duration') or "",
                        "notes": prescription_data.get('notes') or "",
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
                    "medication_name": prescription_data.get('medication_name', ''),
                    "dosage": prescription_data.get('dosage'),
                    "frequency": prescription_data.get('frequency') or "",
                    "duration": prescription_data.get('duration') or "",
                    "notes": prescription_data.get('notes') or "",
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
        response = PrescriptionResponse(
            id=first_prescription.id,
            clinic_id=first_prescription.clinic_id,
            record_id=first_prescription.record_id,
            medication_name=first_prescription.medication_name,
            dosage=first_prescription.dosage,
            frequency=first_prescription.frequency,
            duration=first_prescription.duration,
            notes=first_prescription.notes,
            created_at=first_prescription.created_at,
            patient_id=str(patient.id),
            patient_name=patient.name,
            doctor_name=current_user.name
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create prescription: {str(e)}"
        )


@router.get("/")
async def list_prescriptions(
    search: Optional[str] = Query(None, description="Search by medication or patient name"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_user),
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
    current_user = Depends(get_current_user),
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
    current_user = Depends(get_current_user),
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
    current_user = Depends(get_current_user),
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

