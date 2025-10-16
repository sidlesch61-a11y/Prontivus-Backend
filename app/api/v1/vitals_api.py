"""
Vitals API for patient vital signs with height field.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.db.session import get_db_session
from app.models.database import User
from app.api.v1.auth import get_current_user
from app.models.vitals import PatientVitals, VitalsCreate, VitalsResponse

router = APIRouter()


@router.post("/vitals", response_model=VitalsResponse)
async def create_vitals(
    vitals: VitalsCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Create or update patient vitals."""
    try:
        # Calculate BMI if both weight and height are provided
        bmi = None
        if vitals.weight and vitals.height:
            height_m = vitals.height / 100  # Convert cm to meters
            bmi = round(vitals.weight / (height_m ** 2), 1)
        
        # Create vitals record
        db_vitals = PatientVitals(
            **vitals.model_dump(),
            bmi=bmi
        )
        
        db.add(db_vitals)
        await db.commit()
        await db.refresh(db_vitals)
        
        return VitalsResponse(
            **db_vitals.model_dump(),
            id=db_vitals.id,
            created_at=db_vitals.created_at,
            updated_at=db_vitals.updated_at
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar dados vitais: {str(e)}"
        )


@router.get("/vitals/patient/{patient_id}", response_model=List[VitalsResponse])
async def get_patient_vitals(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get all vitals for a specific patient."""
    try:
        vitals = await db.exec(
            select(PatientVitals)
            .where(PatientVitals.patient_id == patient_id)
            .order_by(PatientVitals.created_at.desc())
        ).all()
        
        return [
            VitalsResponse(
                **vital.model_dump(),
                id=vital.id,
                created_at=vital.created_at,
                updated_at=vital.updated_at
            )
            for vital in vitals
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar dados vitais: {str(e)}"
        )


@router.get("/vitals/consultation/{consultation_id}", response_model=Optional[VitalsResponse])
async def get_consultation_vitals(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get vitals for a specific consultation."""
    try:
        vital = await db.exec(
            select(PatientVitals)
            .where(PatientVitals.consultation_id == consultation_id)
            .order_by(PatientVitals.created_at.desc())
            .limit(1)
        ).first()
        
        if not vital:
            return None
        
        return VitalsResponse(
            **vital.model_dump(),
            id=vital.id,
            created_at=vital.created_at,
            updated_at=vital.updated_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar dados vitais da consulta: {str(e)}"
        )


@router.put("/vitals/{vitals_id}", response_model=VitalsResponse)
async def update_vitals(
    vitals_id: UUID,
    vitals_update: VitalsCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Update existing vitals record."""
    try:
        # Get existing vitals
        existing_vitals = await db.get(PatientVitals, vitals_id)
        if not existing_vitals:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dados vitais não encontrados"
            )
        
        # Update fields
        for field, value in vitals_update.model_dump(exclude_unset=True).items():
            setattr(existing_vitals, field, value)
        
        # Recalculate BMI
        if existing_vitals.weight and existing_vitals.height:
            height_m = existing_vitals.height / 100
            existing_vitals.bmi = round(existing_vitals.weight / (height_m ** 2), 1)
        else:
            existing_vitals.bmi = None
        
        existing_vitals.updated_at = datetime.now()
        
        db.add(existing_vitals)
        await db.commit()
        await db.refresh(existing_vitals)
        
        return VitalsResponse(
            **existing_vitals.model_dump(),
            id=existing_vitals.id,
            created_at=existing_vitals.created_at,
            updated_at=existing_vitals.updated_at
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar dados vitais: {str(e)}"
        )


@router.delete("/vitals/{vitals_id}")
async def delete_vitals(
    vitals_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Delete vitals record."""
    try:
        vitals = await db.get(PatientVitals, vitals_id)
        if not vitals:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dados vitais não encontrados"
            )
        
        await db.delete(vitals)
        await db.commit()
        
        return {"message": "Dados vitais excluídos com sucesso"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao excluir dados vitais: {str(e)}"
        )


@router.get("/vitals/bmi-calculator")
async def calculate_bmi(
    weight: float,
    height: float,
    current_user: User = Depends(get_current_user)
):
    """Calculate BMI from weight and height."""
    try:
        if height <= 0 or weight <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Peso e altura devem ser valores positivos"
            )
        
        height_m = height / 100  # Convert cm to meters
        bmi = round(weight / (height_m ** 2), 1)
        
        # BMI categories
        if bmi < 18.5:
            category = "Abaixo do peso"
        elif bmi < 25:
            category = "Peso normal"
        elif bmi < 30:
            category = "Sobrepeso"
        else:
            category = "Obesidade"
        
        return {
            "bmi": bmi,
            "category": category,
            "weight": weight,
            "height": height
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao calcular IMC: {str(e)}"
        )
