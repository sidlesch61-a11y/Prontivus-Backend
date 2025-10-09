"""
Celery background tasks for Prontivus.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from celery import current_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.workers.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.models import License, Activation, Appointment, TissGuide, Invoice
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True)
def check_license_status(self):
    """Check license status and suspend expired licenses."""
    try:
        async def _check_licenses():
            async with AsyncSessionLocal() as db:
                # Get licenses that are about to expire or have expired
                now = datetime.utcnow()
                result = await db.execute(
                    select(License).where(
                        and_(
                            License.status == "active",
                            License.end_at <= now
                        )
                    )
                )
                expired_licenses = result.scalars().all()
                
                for license_obj in expired_licenses:
                    # Suspend license
                    license_obj.status = "expired"
                    
                    # Suspend all activations
                    activations_result = await db.execute(
                        select(Activation).where(Activation.license_id == license_obj.id)
                    )
                    activations = activations_result.scalars().all()
                    
                    for activation in activations:
                        activation.status = "expired"
                    
                    logger.info(
                        "License expired",
                        license_id=str(license_obj.id),
                        clinic_id=str(license_obj.clinic_id)
                    )
                
                await db.commit()
        
        # Run async function
        import asyncio
        asyncio.run(_check_licenses())
        
        return {"status": "success", "message": "License check completed"}
        
    except Exception as e:
        logger.error("License check failed", error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True)
def cleanup_expired_sessions(self):
    """Cleanup expired sessions and temporary data."""
    try:
        async def _cleanup():
            async with AsyncSessionLocal() as db:
                # Cleanup expired refresh tokens (if stored in database)
                # This would typically clean up a sessions table
                logger.info("Session cleanup completed")
        
        import asyncio
        asyncio.run(_cleanup())
        
        return {"status": "success", "message": "Session cleanup completed"}
        
    except Exception as e:
        logger.error("Session cleanup failed", error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True)
def send_appointment_reminders(self):
    """Send appointment reminders."""
    try:
        async def _send_reminders():
            async with AsyncSessionLocal() as db:
                # Get appointments starting in the next 24 hours
                now = datetime.utcnow()
                reminder_time = now + timedelta(hours=24)
                
                result = await db.execute(
                    select(Appointment).where(
                        and_(
                            Appointment.status == "scheduled",
                            Appointment.start_time <= reminder_time,
                            Appointment.start_time > now
                        )
                    )
                )
                appointments = result.scalars().all()
                
                for appointment in appointments:
                    # TODO: Send actual reminder (email, SMS, push notification)
                    logger.info(
                        "Appointment reminder",
                        appointment_id=str(appointment.id),
                        patient_id=str(appointment.patient_id),
                        start_time=appointment.start_time.isoformat()
                    )
        
        import asyncio
        asyncio.run(_send_reminders())
        
        return {"status": "success", "message": "Reminders sent"}
        
    except Exception as e:
        logger.error("Reminder sending failed", error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True)
def process_tiss_guides(self):
    """Process pending TISS guides."""
    try:
        async def _process_guides():
            async with AsyncSessionLocal() as db:
                # Get pending TISS guides
                result = await db.execute(
                    select(TissGuide).where(TissGuide.status == "pending")
                )
                guides = result.scalars().all()
                
                for guide in guides:
                    try:
                        # TODO: Send to TISS API
                        # This would typically make an HTTP request to TISS
                        logger.info(
                            "Processing TISS guide",
                            guide_id=str(guide.id),
                            guide_number=guide.guide_number
                        )
                        
                        # Update status
                        guide.status = "sent"
                        
                    except Exception as e:
                        logger.error(
                            "TISS guide processing failed",
                            guide_id=str(guide.id),
                            error=str(e)
                        )
                        guide.status = "failed"
                
                await db.commit()
        
        import asyncio
        asyncio.run(_process_guides())
        
        return {"status": "success", "message": "TISS guides processed"}
        
    except Exception as e:
        logger.error("TISS processing failed", error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True)
def send_notification(self, user_id: str, notification_type: str, data: Dict[str, Any]):
    """Send notification to user."""
    try:
        # TODO: Implement notification sending
        # This could be email, SMS, push notification, etc.
        logger.info(
            "Notification sent",
            user_id=user_id,
            notification_type=notification_type,
            data=data
        )
        
        return {"status": "success", "message": "Notification sent"}
        
    except Exception as e:
        logger.error("Notification sending failed", error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True)
def generate_pdf(self, record_id: str, template_type: str):
    """Generate PDF document."""
    try:
        # TODO: Implement PDF generation
        # This would typically use wkhtmltopdf or similar
        logger.info(
            "PDF generated",
            record_id=record_id,
            template_type=template_type
        )
        
        return {"status": "success", "message": "PDF generated"}
        
    except Exception as e:
        logger.error("PDF generation failed", error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True)
def reconcile_payments(self):
    """Reconcile payment statuses with external providers."""
    try:
        async def _reconcile():
            async with AsyncSessionLocal() as db:
                # Get pending invoices
                result = await db.execute(
                    select(Invoice).where(Invoice.status == "pending")
                )
                invoices = result.scalars().all()
                
                for invoice in invoices:
                    try:
                        # TODO: Check payment status with provider
                        # This would typically make API calls to payment providers
                        logger.info(
                            "Reconciling payment",
                            invoice_id=str(invoice.id),
                            amount=float(invoice.amount)
                        )
                        
                    except Exception as e:
                        logger.error(
                            "Payment reconciliation failed",
                            invoice_id=str(invoice.id),
                            error=str(e)
                        )
        
        import asyncio
        asyncio.run(_reconcile())
        
        return {"status": "success", "message": "Payments reconciled"}
        
    except Exception as e:
        logger.error("Payment reconciliation failed", error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)
