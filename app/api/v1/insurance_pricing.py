"""
Insurance Pricing API
Automatic pricing calculation based on insurance provider
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Dict, Any
import uuid

from app.db.session import get_db_session
from app.core.auth import get_current_user
from app.models.insurance_pricing import InsuranceProvider, ServicePricing, PricingRule
from app.models.database import User

router = APIRouter(prefix="/insurance-pricing", tags=["Insurance Pricing"])

@router.get("/providers", response_model=List[dict])
async def get_insurance_providers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all insurance providers"""
    try:
        query = select(InsuranceProvider).where(InsuranceProvider.is_active == True).order_by(InsuranceProvider.name)
        result = await db.execute(query)
        providers = result.scalars().all()
        
        return [
            {
                "id": str(provider.id),
                "name": provider.name,
                "code": provider.code
            }
            for provider in providers
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching providers: {str(e)}")

@router.get("/pricing/{provider_id}", response_model=List[dict])
async def get_pricing_for_provider(
    provider_id: str,
    service_type: Optional[str] = Query(None, description="Filter by service type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get pricing for a specific insurance provider"""
    try:
        query = select(ServicePricing).where(
            and_(
                ServicePricing.insurance_provider_id == uuid.UUID(provider_id),
                ServicePricing.is_active == True
            )
        )
        
        if service_type:
            query = query.where(ServicePricing.service_type == service_type)
        
        query = query.order_by(ServicePricing.service_name)
        
        result = await db.execute(query)
        pricing = result.scalars().all()
        
        return [
            {
                "id": str(price.id),
                "service_type": price.service_type,
                "service_name": price.service_name,
                "base_price": price.base_price,
                "insurance_price": price.insurance_price,
                "discount_percentage": price.discount_percentage
            }
            for price in pricing
        ]
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid provider ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching pricing: {str(e)}")

@router.post("/calculate-price")
async def calculate_price(
    request_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Calculate price for a service based on insurance provider"""
    try:
        insurance_provider = request_data.get("insurance_provider", "Particular")
        service_type = request_data.get("service_type", "consultation")
        service_name = request_data.get("service_name", "Consulta Médica")
        base_price = request_data.get("base_price", 100.0)
        
        if insurance_provider == "Particular":
            return {
                "insurance_provider": "Particular",
                "service_type": service_type,
                "service_name": service_name,
                "base_price": base_price,
                "final_price": base_price,
                "discount_percentage": 0,
                "discount_amount": 0
            }
        
        # Get insurance provider
        provider_query = select(InsuranceProvider).where(
            and_(
                InsuranceProvider.name == insurance_provider,
                InsuranceProvider.is_active == True
            )
        )
        provider_result = await db.execute(provider_query)
        provider = provider_result.scalar_one_or_none()
        
        if not provider:
            # If provider not found, use base price
            return {
                "insurance_provider": insurance_provider,
                "service_type": service_type,
                "service_name": service_name,
                "base_price": base_price,
                "final_price": base_price,
                "discount_percentage": 0,
                "discount_amount": 0,
                "note": "Provider not found in pricing table"
            }
        
        # Get specific pricing for this service
        pricing_query = select(ServicePricing).where(
            and_(
                ServicePricing.insurance_provider_id == provider.id,
                ServicePricing.service_type == service_type,
                ServicePricing.service_name == service_name,
                ServicePricing.is_active == True
            )
        )
        pricing_result = await db.execute(pricing_query)
        pricing = pricing_result.scalar_one_or_none()
        
        if pricing:
            # Use specific pricing
            final_price = pricing.insurance_price
            discount_amount = pricing.base_price - pricing.insurance_price
            discount_percentage = (discount_amount / pricing.base_price) * 100 if pricing.base_price > 0 else 0
        else:
            # Apply general rules for this provider
            rules_query = select(PricingRule).where(
                and_(
                    PricingRule.insurance_provider_id == provider.id,
                    PricingRule.is_active == True,
                    PricingRule.service_type == service_type
                )
            )
            rules_result = await db.execute(rules_query)
            rules = rules_result.scalars().all()
            
            final_price = base_price
            discount_amount = 0
            discount_percentage = 0
            
            for rule in rules:
                if rule.rule_type == "percentage":
                    discount = base_price * (rule.rule_value / 100)
                    final_price = base_price - discount
                    discount_amount = discount
                    discount_percentage = rule.rule_value
                elif rule.rule_type == "fixed":
                    final_price = rule.rule_value
                    discount_amount = base_price - rule.rule_value
                    discount_percentage = (discount_amount / base_price) * 100 if base_price > 0 else 0
                elif rule.rule_type == "tier":
                    if rule.min_amount and base_price >= rule.min_amount:
                        if not rule.max_amount or base_price <= rule.max_amount:
                            discount = base_price * (rule.rule_value / 100)
                            final_price = base_price - discount
                            discount_amount = discount
                            discount_percentage = rule.rule_value
        
        return {
            "insurance_provider": insurance_provider,
            "service_type": service_type,
            "service_name": service_name,
            "base_price": base_price,
            "final_price": round(final_price, 2),
            "discount_percentage": round(discount_percentage, 2),
            "discount_amount": round(discount_amount, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating price: {str(e)}")

@router.get("/default-pricing", response_model=Dict[str, Any])
async def get_default_pricing():
    """Get default pricing structure for common services"""
    return {
        "consultation": {
            "base_price": 150.0,
            "services": {
                "Consulta Médica": 150.0,
                "Retorno": 100.0,
                "Urgência": 200.0
            }
        },
        "exam": {
            "base_price": 80.0,
            "services": {
                "Hemograma": 25.0,
                "Glicemia": 15.0,
                "Colesterol": 20.0,
                "Raio-X Tórax": 60.0,
                "Ultrassom": 120.0
            }
        },
        "procedure": {
            "base_price": 300.0,
            "services": {
                "Cirurgia Ambulatorial": 500.0,
                "Biópsia": 200.0,
                "Endoscopia": 400.0
            }
        }
    }

@router.post("/providers", response_model=dict)
async def create_insurance_provider(
    provider_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new insurance provider (admin only)"""
    try:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admins can create providers")
        
        provider = InsuranceProvider(
            name=provider_data["name"],
            code=provider_data["code"]
        )
        
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        
        return {
            "id": str(provider.id),
            "name": provider.name,
            "code": provider.code,
            "message": "Provider created successfully"
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating provider: {str(e)}")

@router.post("/pricing", response_model=dict)
async def create_service_pricing(
    pricing_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create service pricing for insurance provider (admin only)"""
    try:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admins can create pricing")
        
        pricing = ServicePricing(
            insurance_provider_id=uuid.UUID(pricing_data["insurance_provider_id"]),
            service_type=pricing_data["service_type"],
            service_name=pricing_data["service_name"],
            base_price=pricing_data["base_price"],
            insurance_price=pricing_data["insurance_price"],
            discount_percentage=pricing_data.get("discount_percentage")
        )
        
        db.add(pricing)
        await db.commit()
        await db.refresh(pricing)
        
        return {
            "id": str(pricing.id),
            "message": "Pricing created successfully"
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating pricing: {str(e)}")
