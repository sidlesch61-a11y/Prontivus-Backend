"""
Patient vitals model with height field.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
import uuid


class PatientVitalsBase(SQLModel):
    """Base patient vitals model."""
    patient_id: uuid.UUID = Field(foreign_key="patients.id")
    consultation_id: Optional[uuid.UUID] = Field(default=None, foreign_key="consultations.id")
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
    weight: Optional[float] = None
    height: Optional[float] = None  # Height in cm
    oxygen_saturation: Optional[int] = None
    respiratory_rate: Optional[int] = None
    bmi: Optional[float] = None  # Calculated BMI
    notes: Optional[str] = None


class PatientVitals(PatientVitalsBase, table=True):
    """Patient vitals model."""
    __tablename__ = "patient_vitals"
    
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    patient: Optional["Patient"] = Relationship(back_populates="vitals")
    consultation: Optional["Consultation"] = Relationship(back_populates="vitals")


class VitalsCreate(PatientVitalsBase):
    """Vitals creation model."""
    pass


class VitalsResponse(PatientVitalsBase):
    """Vitals response model."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
