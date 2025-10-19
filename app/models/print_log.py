"""
Print log model for tracking document printing.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base_class import Base

class PrintLog(Base):
    """Model for tracking printed documents."""
    
    __tablename__ = "print_logs"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    consultation_id = Column(String, nullable=False, index=True)
    document_type = Column(String, nullable=False)  # receita_simples, receita_azul, atestado, etc.
    doctor_id = Column(String, nullable=False, index=True)
    output_type = Column(String, nullable=False)  # pdf, direct_print
    clinic_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Optional: Add relationships if needed
    # doctor = relationship("User", back_populates="print_logs")
    # clinic = relationship("Clinic", back_populates="print_logs")
