"""
Webhooks API endpoints for external integrations.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.security import security
from app.db.session import get_db_session
from app.models import Invoice, AuditLog
from app.schemas import WebhookRequest

router = APIRouter()


@router.post("/payments")
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """Handle payment webhooks with idempotency."""
    # Get webhook data
    body = await request.body()
    headers = dict(request.headers)
    
    # Extract idempotency key
    idempotency_key = headers.get("x-idempotency-key")
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing idempotency key"
        )
    
    # Check if webhook was already processed
    # TODO: Implement idempotency check using idempotency_key
    
    # Parse webhook data (this would be provider-specific)
    try:
        webhook_data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    # Process webhook based on provider
    provider = headers.get("x-webhook-provider", "unknown")
    
    if provider == "paypal":
        await process_paypal_webhook(webhook_data, db)
    elif provider == "stripe":
        await process_stripe_webhook(webhook_data, db)
    else:
        # Generic webhook processing
        await process_generic_webhook(webhook_data, db)
    
    return {"status": "processed"}


async def process_paypal_webhook(
    webhook_data: Dict[str, Any], db: AsyncSession
):
    """Process PayPal webhook."""
    event_type = webhook_data.get("event_type")
    
    if event_type == "PAYMENT.SALE.COMPLETED":
        # Payment completed
        resource = webhook_data.get("resource", {})
        invoice_id = resource.get("custom")  # Assuming invoice ID is in custom field
        
        if invoice_id:
            # Update invoice status
            result = await db.execute(
                select(Invoice).where(Invoice.id == invoice_id)
            )
            invoice = result.scalar_one_or_none()
            
            if invoice:
                invoice.status = "paid"
                invoice.paid_at = datetime.utcnow()
                invoice.metadata = {
                    **invoice.metadata,
                    "paypal_transaction_id": resource.get("id"),
                    "webhook_data": webhook_data
                }
                
                await db.commit()
                
                # Create audit log
                audit_log = AuditLog(
                    clinic_id=invoice.clinic_id,
                    action="payment_completed",
                    entity="invoice",
                    entity_id=invoice.id,
                    details={
                        "provider": "paypal",
                        "transaction_id": resource.get("id"),
                        "amount": float(resource.get("amount", {}).get("total", 0))
                    }
                )
                db.add(audit_log)
                await db.commit()


async def process_stripe_webhook(
    webhook_data: Dict[str, Any], db: AsyncSession
):
    """Process Stripe webhook."""
    event_type = webhook_data.get("type")
    
    if event_type == "payment_intent.succeeded":
        # Payment succeeded
        payment_intent = webhook_data.get("data", {}).get("object", {})
        invoice_id = payment_intent.get("metadata", {}).get("invoice_id")
        
        if invoice_id:
            # Update invoice status
            result = await db.execute(
                select(Invoice).where(Invoice.id == invoice_id)
            )
            invoice = result.scalar_one_or_none()
            
            if invoice:
                invoice.status = "paid"
                invoice.paid_at = datetime.utcnow()
                invoice.metadata = {
                    **invoice.metadata,
                    "stripe_payment_intent_id": payment_intent.get("id"),
                    "webhook_data": webhook_data
                }
                
                await db.commit()
                
                # Create audit log
                audit_log = AuditLog(
                    clinic_id=invoice.clinic_id,
                    action="payment_completed",
                    entity="invoice",
                    entity_id=invoice.id,
                    details={
                        "provider": "stripe",
                        "payment_intent_id": payment_intent.get("id"),
                        "amount": float(payment_intent.get("amount", 0)) / 100  # Stripe uses cents
                    }
                )
                db.add(audit_log)
                await db.commit()


async def process_generic_webhook(
    webhook_data: Dict[str, Any], db: AsyncSession
):
    """Process generic webhook."""
    # Log webhook for manual processing
    audit_log = AuditLog(
        action="webhook_received",
        entity="webhook",
        details={
            "provider": "generic",
            "data": webhook_data
        }
    )
    db.add(audit_log)
    await db.commit()


@router.post("/tiss")
async def tiss_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """Handle TISS webhooks."""
    # Get webhook data
    body = await request.body()
    headers = dict(request.headers)
    
    # Parse webhook data
    try:
        webhook_data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    # Process TISS webhook
    guide_number = webhook_data.get("guide_number")
    status = webhook_data.get("status")
    
    if guide_number and status:
        # Update TISS guide status
        # TODO: Implement TISS guide update logic
        
        # Create audit log
        audit_log = AuditLog(
            action="tiss_webhook_received",
            entity="tiss_guide",
            details={
                "guide_number": guide_number,
                "status": status,
                "webhook_data": webhook_data
            }
        )
        db.add(audit_log)
        await db.commit()
    
    return {"status": "processed"}
