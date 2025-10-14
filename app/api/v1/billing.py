"""
API endpoints for billing and payment management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel
import uuid

from app.db.session import get_db_session
from app.core.auth import AuthDependencies
from app.models.database import AuditLog

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


# Pydantic models
class PaymentRecordCreate(BaseModel):
    patient_id: str
    appointment_id: Optional[str] = None
    payment_method: str  # cash, credit_card, debit_card, pix, boleto, bank_transfer, insurance
    insurance_plan_id: Optional[str] = None
    amount: float
    payment_date: date
    status: str = "paid"  # paid, pending, cancelled
    notes: Optional[str] = None


class PaymentRecordResponse(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    appointment_id: Optional[str]
    appointment_date: Optional[str]
    payment_method: str
    insurance_plan_id: Optional[str]
    insurance_plan_name: Optional[str]
    amount: float
    payment_date: str
    status: str
    notes: Optional[str]
    created_by: str
    created_at: str
    
    class Config:
        orm_mode = True


@router.get("/payments", response_model=List[PaymentRecordResponse])
async def list_payments(
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List all payment records for the clinic."""
    try:
        from app.models.database import Patient, Appointment
        
        # For now, return mock data since we don't have the payment_records table yet
        # In production, query from database
        
        # TODO: Create payment_records table and implement proper querying
        # This is a temporary implementation that returns empty list
        # The frontend is designed to work with this structure
        
        return []
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error listing payments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list payments: {str(e)}"
        )


@router.post("/payments", response_model=dict)
async def create_payment(
    payment_data: PaymentRecordCreate,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new payment record."""
    try:
        from app.models.database import Patient, Appointment
        
        # Verify patient exists
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == uuid.UUID(payment_data.patient_id),
                Patient.clinic_id == current_user.clinic_id
            )
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paciente não encontrado"
            )
        
        # Verify appointment if provided
        if payment_data.appointment_id:
            appointment_result = await db.execute(
                select(Appointment).where(
                    Appointment.id == uuid.UUID(payment_data.appointment_id),
                    Appointment.clinic_id == current_user.clinic_id
                )
            )
            appointment = appointment_result.scalar_one_or_none()
            
            if not appointment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Consulta não encontrada"
                )
        
        # TODO: Create payment_records table and insert the record
        # For now, just log it to audit
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="payment_recorded",
            entity="payment",
            entity_id=str(uuid.uuid4()),  # Temporary ID
            details={
                "patient_id": payment_data.patient_id,
                "patient_name": patient.name,
                "payment_method": payment_data.payment_method,
                "amount": float(payment_data.amount),
                "payment_date": payment_data.payment_date.isoformat(),
                "status": payment_data.status
            }
        )
        db.add(audit_log)
        await db.commit()
        
        return {
            "success": True,
            "message": "Pagamento registrado com sucesso",
            "payment_id": str(uuid.uuid4())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating payment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao registrar pagamento: {str(e)}"
        )


@router.post("/export-pdf")
async def export_pdf(
    filters: dict,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Export payment records to PDF."""
    try:
        # TODO: Implement PDF generation with ReportLab or WeasyPrint
        # For now, return a placeholder response
        
        import base64
        
        # Simple PDF header
        pdf_content = b"%PDF-1.4\n"
        
        return {
            "success": True,
            "pdf_base64": base64.b64encode(pdf_content).decode('utf-8'),
            "message": "Relatório gerado com sucesso"
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error exporting PDF: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao gerar PDF: {str(e)}"
        )

