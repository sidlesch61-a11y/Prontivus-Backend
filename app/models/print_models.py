"""
Models for print functionality and pricing rules.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
import uuid


class PrintLogBase(SQLModel):
    """Base print log model."""
    consultation_id: uuid.UUID = Field(foreign_key="consultations.id")
    document_type: str
    printed_by: uuid.UUID = Field(foreign_key="users.id")
    printer_name: Optional[str] = None
    pages_count: int = Field(default=1)
    status: str = Field(default="success")
    error_message: Optional[str] = None


class PrintLog(PrintLogBase, table=True):
    """Print log model for tracking document printing."""
    __tablename__ = "print_logs"
    
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    printed_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    consultation: Optional["Consultation"] = Relationship(back_populates="print_logs")
    printer: Optional["User"] = Relationship()


class PriceRuleBase(SQLModel):
    """Base price rule model."""
    convenio_id: Optional[uuid.UUID] = Field(default=None, foreign_key="insurance_providers.id")
    consulta_tipo: str
    valor: float
    is_active: bool = Field(default=True)


class PriceRule(PriceRuleBase, table=True):
    """Price rule model for consultation pricing."""
    __tablename__ = "price_rules"
    
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PrintRequest(SQLModel):
    """Print request model."""
    consultation_id: uuid.UUID
    document_type: str
    preview: bool = Field(default=False)
    printer_name: Optional[str] = None


class PrintResponse(SQLModel):
    """Print response model."""
    success: bool
    message: str
    print_id: Optional[uuid.UUID] = None
    preview_url: Optional[str] = None
