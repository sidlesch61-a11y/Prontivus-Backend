"""
Payment API Endpoints
Handles PIX, Boleto, PayPal, and other payment methods
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.db.session import get_db_session
from app.core.auth import AuthDependencies
from app.models.database import Invoice, AuditLog
from app.services.payment_integrations import payment_service

router = APIRouter(tags=["Payments"])


class PIXPaymentRequest(BaseModel):
    """Request to create PIX payment."""
    invoice_id: str
    payer_email: str
    payer_name: str
    payer_cpf: str


class PIXPaymentResponse(BaseModel):
    """PIX payment response."""
    payment_id: str
    qr_code: str
    qr_code_text: str
    expires_at: datetime
    status: str
    provider: str


class BoletoPaymentRequest(BaseModel):
    """Request to create Boleto payment."""
    invoice_id: str
    payer_name: str
    payer_cpf: str
    payer_address: Dict[str, str]
    due_date: datetime


class BoletoPaymentResponse(BaseModel):
    """Boleto payment response."""
    boleto_id: str
    barcode: str
    digitable_line: str
    pdf_url: str
    due_date: datetime
    status: str


class PayPalPaymentRequest(BaseModel):
    """Request to create PayPal payment."""
    invoice_id: str
    return_url: str
    cancel_url: str


class PayPalPaymentResponse(BaseModel):
    """PayPal payment response."""
    payment_id: str
    approval_url: str
    status: str


@router.post("/pix/create", response_model=PIXPaymentResponse)
async def create_pix_payment(
    payment_request: PIXPaymentRequest,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a PIX payment for an invoice.
    
    Generates a QR code and PIX copy-paste code that the patient can use to pay.
    """
    # Get invoice
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == uuid.UUID(payment_request.invoice_id),
            Invoice.clinic_id == current_user.clinic_id
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    if invoice.status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice already paid"
        )
    
    # Create PIX payment
    try:
        payer_info = {
            "email": payment_request.payer_email,
            "name": payment_request.payer_name,
            "cpf": payment_request.payer_cpf
        }
        
        payment_data = await payment_service.create_pix_payment(
            invoice_id=payment_request.invoice_id,
            amount=float(invoice.amount),
            description=f"Invoice #{invoice.id}",
            payer_info=payer_info
        )
        
        # Update invoice with payment ID
        if invoice.payment_metadata is None:
            invoice.payment_metadata = {}
        
        invoice.payment_metadata["pix"] = {
            "payment_id": payment_data["payment_id"],
            "provider": payment_data["provider"],
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": payment_data["expires_at"].isoformat() if isinstance(payment_data["expires_at"], datetime) else payment_data["expires_at"]
        }
        invoice.method = "pix"
        
        await db.commit()
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="pix_payment_created",
            entity="invoice",
            entity_id=invoice.id,
            details={
                "payment_id": payment_data["payment_id"],
                "amount": float(invoice.amount),
                "provider": payment_data["provider"]
            }
        )
        db.add(audit_log)
        await db.commit()
        
        return PIXPaymentResponse(**payment_data)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create PIX payment: {str(e)}"
        )


@router.post("/boleto/create", response_model=BoletoPaymentResponse)
async def create_boleto_payment(
    payment_request: BoletoPaymentRequest,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a Boleto (bank slip) payment for an invoice.
    
    Generates a barcode and digitable line that can be used at banks or lottery shops.
    """
    # Get invoice
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == uuid.UUID(payment_request.invoice_id),
            Invoice.clinic_id == current_user.clinic_id
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    if invoice.status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice already paid"
        )
    
    # Create Boleto
    try:
        payer_info = {
            "name": payment_request.payer_name,
            "cpf": payment_request.payer_cpf,
            "address": payment_request.payer_address
        }
        
        boleto_data = await payment_service.create_boleto(
            invoice_id=payment_request.invoice_id,
            amount=float(invoice.amount),
            description=f"Invoice #{invoice.id}",
            payer_info=payer_info,
            due_date=payment_request.due_date
        )
        
        # Update invoice
        if invoice.payment_metadata is None:
            invoice.payment_metadata = {}
        
        invoice.payment_metadata["boleto"] = {
            "boleto_id": boleto_data["boleto_id"],
            "created_at": datetime.utcnow().isoformat(),
            "due_date": boleto_data["due_date"].isoformat() if isinstance(boleto_data["due_date"], datetime) else boleto_data["due_date"]
        }
        invoice.method = "bank_transfer"
        invoice.due_date = payment_request.due_date.date()
        
        await db.commit()
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="boleto_payment_created",
            entity="invoice",
            entity_id=invoice.id,
            details={
                "boleto_id": boleto_data["boleto_id"],
                "amount": float(invoice.amount),
                "due_date": str(payment_request.due_date.date())
            }
        )
        db.add(audit_log)
        await db.commit()
        
        return BoletoPaymentResponse(**boleto_data)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Boleto: {str(e)}"
        )


@router.post("/paypal/create", response_model=PayPalPaymentResponse)
async def create_paypal_payment(
    payment_request: PayPalPaymentRequest,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a PayPal payment for an invoice.
    
    Returns an approval URL where the user should be redirected to complete payment.
    """
    # Get invoice
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == uuid.UUID(payment_request.invoice_id),
            Invoice.clinic_id == current_user.clinic_id
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    if invoice.status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice already paid"
        )
    
    # Create PayPal payment
    try:
        payment_data = await payment_service.create_paypal_payment(
            invoice_id=payment_request.invoice_id,
            amount=float(invoice.amount),
            description=f"Invoice #{invoice.id}",
            return_url=payment_request.return_url,
            cancel_url=payment_request.cancel_url
        )
        
        # Update invoice
        if invoice.payment_metadata is None:
            invoice.payment_metadata = {}
        
        invoice.payment_metadata["paypal"] = {
            "payment_id": payment_data["payment_id"],
            "created_at": datetime.utcnow().isoformat()
        }
        invoice.method = "card"  # PayPal uses card internally
        
        await db.commit()
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="paypal_payment_created",
            entity="invoice",
            entity_id=invoice.id,
            details={
                "payment_id": payment_data["payment_id"],
                "amount": float(invoice.amount)
            }
        )
        db.add(audit_log)
        await db.commit()
        
        return PayPalPaymentResponse(**payment_data)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create PayPal payment: {str(e)}"
        )


@router.get("/{payment_id}/status")
async def check_payment_status(
    payment_id: str,
    provider: str,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Check payment status with the payment provider.
    
    Useful for polling payment status or manual verification.
    """
    try:
        status_data = await payment_service.check_payment_status(payment_id, provider)
        
        return {
            "payment_id": payment_id,
            "provider": provider,
            **status_data
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check payment status: {str(e)}"
        )

