"""
Standardized Exam Database Model
Internal database with standardized exams (name + TUSS code)
"""

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid

class StandardExam(SQLModel, table=True):
    """Standardized exam with TUSS code for internal database"""
    
    __tablename__ = "standard_exams"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True, description="Exam name")
    tuss_code: str = Field(index=True, description="TUSS code")
    category: str = Field(description="Exam category (e.g., 'Laboratory', 'Imaging', 'Cardiology')")
    description: Optional[str] = Field(default=None, description="Exam description")
    preparation_instructions: Optional[str] = Field(default=None, description="Patient preparation instructions")
    normal_values: Optional[str] = Field(default=None, description="Normal reference values")
    is_active: bool = Field(default=True, description="Whether exam is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat()
        }

class ExamCategory(SQLModel, table=True):
    """Exam categories for organization"""
    
    __tablename__ = "exam_categories"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, description="Category name")
    description: Optional[str] = Field(default=None, description="Category description")
    color: Optional[str] = Field(default="#3B82F6", description="Category color for UI")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat()
        }
