"""
Pricing API for automatic consultation pricing based on insurance.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.db.session import get_db_session
from app.models.database import User
from app.api.v1.auth import get_current_user
from app.models.print_models import PriceRule, PriceRuleBase
from app.models.database import Patient, Appointment

router = APIRouter()


@router.post("/pricing/rules", response_model=PriceRule)
async def create_price_rule(
    rule: PriceRuleBase,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Create a new pricing rule."""
    db_rule = PriceRule.model_validate(rule)
    db.add(db_rule)
    await db.commit()
    await db.refresh(db_rule)
    return db_rule


@router.get("/pricing/rules", response_model=List[PriceRule])
async def get_price_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get all pricing rules."""
    rules = await db.exec(select(PriceRule).where(PriceRule.is_active == True)).all()
    return rules


@router.get("/pricing/calculate/{patient_id}")
async def calculate_consultation_price(
    patient_id: UUID,
    consultation_type: str = "consulta",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Calculate consultation price based on patient's insurance."""
    try:
        # Get patient data
        patient = await db.get(Patient, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        # Get patient's insurance provider
        insurance_provider = patient.insurance_provider or "Particular"
        
        # Get pricing rule for this insurance and consultation type
        rule = await db.exec(
            select(PriceRule)
            .where(PriceRule.consulta_tipo == consultation_type)
            .where(PriceRule.is_active == True)
            .where(
                (PriceRule.convenio_id.is_(None)) |  # General rule
                (PriceRule.convenio_id == patient.insurance_provider)  # Specific insurance rule
            )
            .order_by(PriceRule.convenio_id.desc())  # Prefer specific rules over general
        ).first()
        
        if rule:
            price = rule.valor
            rule_type = "specific" if rule.convenio_id else "general"
        else:
            # Default pricing based on consultation type
            default_prices = {
                "consulta": 150.00,
                "retorno": 100.00,
                "emergencia": 300.00,
                "telemedicina": 120.00
            }
            price = default_prices.get(consultation_type, 150.00)
            rule_type = "default"
        
        return {
            "patient_id": str(patient_id),
            "patient_name": patient.name,
            "insurance_provider": insurance_provider,
            "consultation_type": consultation_type,
            "calculated_price": price,
            "rule_type": rule_type,
            "currency": "BRL"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao calcular preço: {str(e)}"
        )


@router.post("/pricing/autoassign/{appointment_id}")
async def auto_assign_price(
    appointment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Automatically assign price to an appointment based on patient's insurance."""
    try:
        # Get appointment data
        appointment = await db.get(Appointment, appointment_id)
        if not appointment:
            raise HTTPException(status_code=404, detail="Agendamento não encontrado")
        
        # Get patient data
        patient = await db.get(Patient, appointment.patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        # Calculate price
        price_data = await calculate_consultation_price(
            patient.id, 
            "consulta", 
            current_user, 
            db
        )
        
        # Update appointment with calculated price
        appointment.price = price_data["calculated_price"]
        appointment.updated_at = datetime.now()
        
        db.add(appointment)
        await db.commit()
        
        return {
            "appointment_id": str(appointment_id),
            "assigned_price": price_data["calculated_price"],
            "insurance_provider": price_data["insurance_provider"],
            "message": "Preço atribuído automaticamente"
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atribuir preço: {str(e)}"
        )


@router.get("/pricing/insurance-providers")
async def get_insurance_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get list of insurance providers from patients."""
    try:
        providers = await db.exec(
            select(Patient.insurance_provider)
            .where(Patient.insurance_provider.is_not(None))
            .distinct()
        ).all()
        
        # Add "Particular" as default
        provider_list = ["Particular"] + [p for p in providers if p and p != "Particular"]
        
        return {
            "providers": provider_list,
            "total": len(provider_list)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar provedores: {str(e)}"
        )
