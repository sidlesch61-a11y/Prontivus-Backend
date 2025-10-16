#!/usr/bin/env python3
"""
Script to populate insurance pricing data
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.insurance_pricing import InsuranceProvider, ServicePricing, PricingRule
from app.core.config import settings

# Database URL
DATABASE_URL = settings.DATABASE_URL

async def populate_insurance_pricing():
    """Populate insurance pricing data"""
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Create insurance providers
            providers = [
                {"name": "Unimed", "code": "UNIMED"},
                {"name": "SUS", "code": "SUS"},
                {"name": "Bradesco Saúde", "code": "BRADESCO"},
                {"name": "Amil", "code": "AMIL"},
                {"name": "SulAmérica", "code": "SULAMERICA"},
                {"name": "NotreDame Intermédica", "code": "NOTREDAME"},
                {"name": "Particular", "code": "PARTICULAR"}
            ]
            
            created_providers = {}
            for provider_data in providers:
                provider = InsuranceProvider(**provider_data)
                session.add(provider)
                await session.flush()  # Get the ID
                created_providers[provider.name] = provider.id
            
            await session.commit()
            print("✅ Insurance providers created successfully")
            
            # Create service pricing for consultations
            consultation_services = [
                {"service_type": "consultation", "service_name": "Consulta Médica", "base_price": 150.0},
                {"service_type": "consultation", "service_name": "Retorno", "base_price": 100.0},
                {"service_type": "consultation", "service_name": "Urgência", "base_price": 200.0},
                {"service_type": "consultation", "service_name": "Telemedicina", "base_price": 120.0}
            ]
            
            # Pricing by provider
            provider_pricing = {
                "SUS": {"discount": 100, "fixed_price": 0},  # Free
                "Unimed": {"discount": 20, "fixed_price": None},  # 20% discount
                "Bradesco Saúde": {"discount": 15, "fixed_price": None},  # 15% discount
                "Amil": {"discount": 25, "fixed_price": None},  # 25% discount
                "SulAmérica": {"discount": 18, "fixed_price": None},  # 18% discount
                "NotreDame Intermédica": {"discount": 22, "fixed_price": None},  # 22% discount
                "Particular": {"discount": 0, "fixed_price": None}  # No discount
            }
            
            for service in consultation_services:
                for provider_name, provider_id in created_providers.items():
                    if provider_name in provider_pricing:
                        pricing_info = provider_pricing[provider_name]
                        
                        if pricing_info["fixed_price"] is not None:
                            insurance_price = pricing_info["fixed_price"]
                        else:
                            discount_amount = service["base_price"] * (pricing_info["discount"] / 100)
                            insurance_price = service["base_price"] - discount_amount
                        
                        pricing = ServicePricing(
                            insurance_provider_id=provider_id,
                            service_type=service["service_type"],
                            service_name=service["service_name"],
                            base_price=service["base_price"],
                            insurance_price=insurance_price,
                            discount_percentage=pricing_info["discount"]
                        )
                        session.add(pricing)
            
            # Create exam pricing
            exam_services = [
                {"service_type": "exam", "service_name": "Hemograma", "base_price": 25.0},
                {"service_type": "exam", "service_name": "Glicemia", "base_price": 15.0},
                {"service_type": "exam", "service_name": "Colesterol", "base_price": 20.0},
                {"service_type": "exam", "service_name": "Raio-X Tórax", "base_price": 60.0},
                {"service_type": "exam", "service_name": "Ultrassom", "base_price": 120.0},
                {"service_type": "exam", "service_name": "Eletrocardiograma", "base_price": 40.0}
            ]
            
            for service in exam_services:
                for provider_name, provider_id in created_providers.items():
                    if provider_name in provider_pricing:
                        pricing_info = provider_pricing[provider_name]
                        
                        if pricing_info["fixed_price"] is not None:
                            insurance_price = pricing_info["fixed_price"]
                        else:
                            discount_amount = service["base_price"] * (pricing_info["discount"] / 100)
                            insurance_price = service["base_price"] - discount_amount
                        
                        pricing = ServicePricing(
                            insurance_provider_id=provider_id,
                            service_type=service["service_type"],
                            service_name=service["service_name"],
                            base_price=service["base_price"],
                            insurance_price=insurance_price,
                            discount_percentage=pricing_info["discount"]
                        )
                        session.add(pricing)
            
            # Create general pricing rules
            for provider_name, provider_id in created_providers.items():
                if provider_name != "Particular" and provider_name != "SUS":
                    # General consultation discount rule
                    rule = PricingRule(
                        insurance_provider_id=provider_id,
                        rule_type="percentage",
                        rule_value=provider_pricing[provider_name]["discount"],
                        service_type="consultation"
                    )
                    session.add(rule)
                    
                    # General exam discount rule (slightly less discount)
                    exam_discount = max(0, provider_pricing[provider_name]["discount"] - 5)
                    rule = PricingRule(
                        insurance_provider_id=provider_id,
                        rule_type="percentage",
                        rule_value=exam_discount,
                        service_type="exam"
                    )
                    session.add(rule)
            
            await session.commit()
            print("✅ Service pricing created successfully")
            print(f"📊 Created pricing for {len(providers)} providers and {len(consultation_services + exam_services)} services")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error populating insurance pricing: {e}")
            raise
        finally:
            await engine.dispose()

if __name__ == "__main__":
    print("🚀 Starting insurance pricing population...")
    asyncio.run(populate_insurance_pricing())
    print("✅ Insurance pricing population completed!")
