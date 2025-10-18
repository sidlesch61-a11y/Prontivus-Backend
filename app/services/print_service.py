"""
Print service for handling direct printing and logging.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from app.models import User


class PrintService:
    """Service for handling print operations and logging."""
    
    async def log_print_action(
        self,
        db: AsyncSession,
        document_type: str,
        consultation_id: str,
        doctor_id: str,
        output_type: str,
        success: bool,
        error_message: Optional[str] = None
    ):
        """Log print action to database."""
        try:
            # Create print log entry
            print_log = {
                "id": str(uuid.uuid4()),
                "document_type": document_type,
                "consultation_id": consultation_id,
                "doctor_id": doctor_id,
                "output_type": output_type,
                "success": success,
                "error_message": error_message,
                "created_at": datetime.now(),
                "clinic_id": None  # Will be set based on doctor's clinic
            }
            
            # Get doctor's clinic_id
            doctor_result = await db.execute(
                select(User.clinic_id).where(User.id == doctor_id)
            )
            clinic_id = doctor_result.scalar_one_or_none()
            
            if clinic_id:
                print_log["clinic_id"] = clinic_id
                
                # Insert print log (assuming print_logs table exists)
                # This would require creating the print_logs table
                # For now, we'll just log to console
                print(f"Print Log: {print_log}")
            
        except Exception as e:
            print(f"Error logging print action: {e}")
    
    async def print_direct(
        self,
        document_type: str,
        consultation,
        patient,
        doctor,
        clinic
    ) -> bool:
        """Send document directly to printer."""
        try:
            # This would integrate with actual printer drivers
            # For now, we'll simulate the print operation
            
            print(f"Printing {document_type} for consultation {consultation.id}")
            print(f"Patient: {patient.name}")
            print(f"Doctor: {doctor.name}")
            print(f"Clinic: {clinic.name}")
            
            # Simulate print success
            return True
            
        except Exception as e:
            print(f"Error printing document: {e}")
            return False
    
    async def print_consolidated_direct(
        self,
        consultation,
        patient,
        doctor,
        clinic
    ) -> bool:
        """Send consolidated documents directly to printer."""
        try:
            # This would integrate with actual printer drivers
            # For now, we'll simulate the print operation
            
            print(f"Printing consolidated documents for consultation {consultation.id}")
            print(f"Patient: {patient.name}")
            print(f"Doctor: {doctor.name}")
            print(f"Clinic: {clinic.name}")
            
            # Simulate print success
            return True
            
        except Exception as e:
            print(f"Error printing consolidated documents: {e}")
            return False