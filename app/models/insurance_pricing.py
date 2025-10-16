"""
Insurance Pricing Model
Automatic pricing based on insurance provider
"""

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid

class InsuranceProvider(SQLModel, table=True):
    """Insurance provider configuration with pricing"""
    
    __tablename__ = "insurance_providers"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, description="Insurance provider name")
    code: str = Field(unique=True, index=True, description="Insurance provider code")
    is_active: bool = Field(default=True, description="Whether provider is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat()
        }

class ServicePricing(SQLModel, table=True):
    """Service pricing by insurance provider"""
    
    __tablename__ = "service_pricing"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    insurance_provider_id: uuid.UUID = Field(foreign_key="insurance_providers.id")
    service_type: str = Field(description="Type of service (consultation, exam, procedure)")
    service_name: str = Field(description="Name of the service")
    base_price: float = Field(description="Base price for the service")
    insurance_price: float = Field(description="Price for this insurance provider")
    discount_percentage: Optional[float] = Field(default=None, description="Discount percentage")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat()
        }

class PricingRule(SQLModel, table=True):
    """Pricing rules for automatic calculation"""
    
    __tablename__ = "pricing_rules"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    insurance_provider_id: uuid.UUID = Field(foreign_key="insurance_providers.id")
    rule_type: str = Field(description="Type of rule (percentage, fixed, tier)")
    rule_value: float = Field(description="Rule value")
    min_amount: Optional[float] = Field(default=None, description="Minimum amount")
    max_amount: Optional[float] = Field(default=None, description="Maximum amount")
    service_type: Optional[str] = Field(default=None, description="Specific service type")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat()
        }
