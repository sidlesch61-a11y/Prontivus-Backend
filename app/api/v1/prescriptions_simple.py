"""
Simple Prescriptions API for basic CRUD operations
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import uuid
from datetime import datetime

from app.db.session import get_db_session
from app.core.auth import get_current_user
from app.models.database import Prescription as PrescriptionDB, Patient, User
from pydantic import BaseModel

router = APIRouter(tags=["Prescriptions"])

class PrescriptionResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    medication_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class PrescriptionCreate(BaseModel):
    patient_id: str
    medication_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None

@router.get("/", response_model=List[PrescriptionResponse])
async def list_prescriptions(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List prescriptions with optional search and pagination."""
    try:
        query = select(PrescriptionDB).where(PrescriptionDB.clinic_id == current_user.clinic_id)
        
        if search:
            query = query.where(PrescriptionDB.medication_name.ilike(f"%{search}%"))
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size).order_by(PrescriptionDB.created_at.desc())
        
        result = await db.execute(query)
        prescriptions = result.scalars().all()
        
        return [
            PrescriptionResponse(
                id=str(prescription.id),
                patient_id=str(prescription.patient_id),
                doctor_id=str(prescription.doctor_id),
                medication_name=prescription.medication_name,
                dosage=prescription.dosage,
                frequency=prescription.frequency,
                duration=prescription.duration,
                notes=prescription.notes,
                created_at=prescription.created_at,
                updated_at=prescription.updated_at
            )
            for prescription in prescriptions
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing prescriptions: {str(e)}"
        )

@router.post("/", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_prescription(
    prescription_data: PrescriptionCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new prescription."""
    try:
        # Verify patient exists
        patient_result = await db.execute(
            select(Patient).where(Patient.id == prescription_data.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
        
        # Create prescription
        prescription = PrescriptionDB(
            id=uuid.uuid4(),
            clinic_id=current_user.clinic_id,
            patient_id=prescription_data.patient_id,
            doctor_id=current_user.id,
            medication_name=prescription_data.medication_name,
            dosage=prescription_data.dosage,
            frequency=prescription_data.frequency,
            duration=prescription_data.duration,
            notes=prescription_data.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(prescription)
        await db.commit()
        await db.refresh(prescription)
        
        return PrescriptionResponse(
            id=str(prescription.id),
            patient_id=str(prescription.patient_id),
            doctor_id=str(prescription.doctor_id),
            medication_name=prescription.medication_name,
            dosage=prescription.dosage,
            frequency=prescription.frequency,
            duration=prescription.duration,
            notes=prescription.notes,
            created_at=prescription.created_at,
            updated_at=prescription.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating prescription: {str(e)}"
        )

@router.get("/{prescription_id}", response_model=PrescriptionResponse)
async def get_prescription(
    prescription_id: str,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get a specific prescription by ID."""
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
        
        return PrescriptionResponse(
            id=str(prescription.id),
            patient_id=str(prescription.patient_id),
            doctor_id=str(prescription.doctor_id),
            medication_name=prescription.medication_name,
            dosage=prescription.dosage,
            frequency=prescription.frequency,
            duration=prescription.duration,
            notes=prescription.notes,
            created_at=prescription.created_at,
            updated_at=prescription.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving prescription: {str(e)}"
        )
