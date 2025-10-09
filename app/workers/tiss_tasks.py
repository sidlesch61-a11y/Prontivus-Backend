"""
Celery worker tasks for TISS job processing.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import uuid

from celery import Celery
from sqlmodel import Session, select, and_

from ..db.session import get_db_session
from ..models.tiss import (
    TISSProvider, TISSJob, TISSLog, TISSEthicalLock,
    TISSJobStatus, TISSLogLevel, TISSEthicalLockType
)
from ..services.tiss_service import TISSService
from ..core.security import security

logger = logging.getLogger(__name__)

# Celery app instance
celery_app = Celery('tiss_worker')

# Configure Celery
celery_app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=True
)

@celery_app.task(bind=True, max_retries=3)
def process_tiss_job_task(self, job_id: str):
    """Process a TISS job."""
    
    job_uuid = uuid.UUID(job_id)
    tiss_service = TISSService()
    
    try:
        # Get database session
        with get_db_session() as db:
            # Get job with provider
            job = db.exec(
                select(TISSJob)
                .where(TISSJob.id == job_uuid)
                .options(selectinload(TISSJob.provider))
            ).first()
            
            if not job:
                logger.error(f"TISS job not found: {job_id}")
                return {"status": "error", "message": "Job not found"}
            
            # Check if job is already being processed
            if job.status == TISSJobStatus.PROCESSING:
                logger.warning(f"TISS job already being processed: {job_id}")
                return {"status": "warning", "message": "Job already being processed"}
            
            # Check if job should be processed
            if job.status not in [TISSJobStatus.PENDING, TISSJobStatus.FAILED]:
                logger.warning(f"TISS job not in processable state: {job_id}, status: {job.status}")
                return {"status": "warning", "message": f"Job not processable, status: {job.status}"}
            
            # Check provider status
            if not job.provider or job.provider.status != "active":
                logger.error(f"TISS provider not active: {job.provider_id}")
                
                # Update job status
                job.status = TISSJobStatus.FAILED
                job.last_error = "Provider not active"
                job.last_error_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                db.add(job)
                
                # Log error
                log = tiss_service.create_audit_log(
                    clinic_id=job.clinic_id,
                    provider_id=job.provider_id,
                    job_id=job.id,
                    level=TISSLogLevel.ERROR,
                    message="Provider not active",
                    operation="process_job",
                    details={"provider_id": str(job.provider_id)}
                )
                db.add(log)
                db.commit()
                
                return {"status": "error", "message": "Provider not active"}
            
            # Update job status to processing
            job.status = TISSJobStatus.PROCESSING
            job.attempts += 1
            job.processed_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            db.add(job)
            
            # Log processing start
            log = tiss_service.create_audit_log(
                clinic_id=job.clinic_id,
                provider_id=job.provider_id,
                job_id=job.id,
                level=TISSLogLevel.INFO,
                message=f"TISS job processing started (attempt {job.attempts})",
                operation="process_job",
                details={"attempt": job.attempts}
            )
            db.add(log)
            db.commit()
            
            # Create TISS payload
            payload = tiss_service.create_tiss_payload(job)
            
            # Validate payload
            validation_errors = tiss_service.validate_tiss_payload(payload)
            if validation_errors:
                logger.error(f"TISS payload validation failed: {validation_errors}")
                
                job.status = TISSJobStatus.FAILED
                job.last_error = f"Payload validation failed: {', '.join(validation_errors)}"
                job.last_error_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                db.add(job)
                
                # Log validation error
                log = tiss_service.create_audit_log(
                    clinic_id=job.clinic_id,
                    provider_id=job.provider_id,
                    job_id=job.id,
                    level=TISSLogLevel.ERROR,
                    message="Payload validation failed",
                    operation="process_job",
                    details={"errors": validation_errors},
                    request_data=payload
                )
                db.add(log)
                db.commit()
                
                return {"status": "error", "message": f"Validation failed: {', '.join(validation_errors)}"}
            
            # Send payload to provider
            start_time = datetime.utcnow()
            import asyncio
            success, error_message, response_data = asyncio.run(tiss_service.send_tiss_payload(
                provider=job.provider,
                job=job,
                payload=payload
            ))
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if success:
                # Success - parse response
                parsed_response = tiss_service.parse_tiss_response(response_data or {})
                
                # Update job status based on response
                if parsed_response["status"] in ["aceita", "aceito", "accepted"]:
                    job.status = TISSJobStatus.ACCEPTED
                elif parsed_response["status"] in ["rejeitada", "rejeitado", "rejected"]:
                    job.status = TISSJobStatus.REJECTED
                else:
                    job.status = TISSJobStatus.SENT
                
                job.response_data = parsed_response
                job.completed_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                db.add(job)
                
                # Log success
                log = tiss_service.create_audit_log(
                    clinic_id=job.clinic_id,
                    provider_id=job.provider_id,
                    job_id=job.id,
                    level=TISSLogLevel.INFO,
                    message=f"TISS job processed successfully: {parsed_response['status']}",
                    operation="process_job",
                    details=parsed_response,
                    request_data=payload,
                    response_data=response_data,
                    response_time_ms=int(response_time)
                )
                db.add(log)
                db.commit()
                
                logger.info(f"TISS job processed successfully: {job_id}")
                return {"status": "success", "message": "Job processed successfully"}
                
            else:
                # Error - check if should retry
                if tiss_service.should_retry(job.attempts, job.max_attempts):
                    # Schedule retry
                    next_retry = tiss_service.calculate_next_retry(job.attempts, job.provider.retry_delay_seconds)
                    
                    job.status = TISSJobStatus.PENDING
                    job.last_error = error_message
                    job.last_error_at = datetime.utcnow()
                    job.next_retry_at = next_retry
                    job.updated_at = datetime.utcnow()
                    db.add(job)
                    
                    # Log retry
                    log = tiss_service.create_audit_log(
                        clinic_id=job.clinic_id,
                        provider_id=job.provider_id,
                        job_id=job.id,
                        level=TISSLogLevel.WARNING,
                        message=f"TISS job failed, will retry: {error_message}",
                        operation="process_job",
                        details={
                            "attempt": job.attempts,
                            "max_attempts": job.max_attempts,
                            "next_retry_at": next_retry.isoformat()
                        },
                        request_data=payload
                    )
                    db.add(log)
                    db.commit()
                    
                    # Schedule retry
                    process_tiss_job_task.apply_async(
                        args=[job_id],
                        eta=next_retry,
                        retry=True
                    )
                    
                    logger.warning(f"TISS job failed, retry scheduled: {job_id}")
                    return {"status": "retry", "message": f"Job failed, retry scheduled: {error_message}"}
                    
                else:
                    # Max retries exceeded
                    job.status = TISSJobStatus.FAILED
                    job.last_error = f"Max retries exceeded: {error_message}"
                    job.last_error_at = datetime.utcnow()
                    job.updated_at = datetime.utcnow()
                    db.add(job)
                    
                    # Log failure
                    log = tiss_service.create_audit_log(
                        clinic_id=job.clinic_id,
                        provider_id=job.provider_id,
                        job_id=job.id,
                        level=TISSLogLevel.ERROR,
                        message=f"TISS job failed after max retries: {error_message}",
                        operation="process_job",
                        details={
                            "attempt": job.attempts,
                            "max_attempts": job.max_attempts
                        },
                        request_data=payload
                    )
                    db.add(log)
                    db.commit()
                    
                    logger.error(f"TISS job failed after max retries: {job_id}")
                    return {"status": "failed", "message": f"Job failed after max retries: {error_message}"}
                    
    except Exception as e:
        logger.error(f"Unexpected error processing TISS job {job_id}: {str(e)}")
        
        try:
            # Try to update job status
            with get_db_session() as db:
                job = db.exec(select(TISSJob).where(TISSJob.id == job_uuid)).first()
                if job:
                    job.status = TISSJobStatus.FAILED
                    job.last_error = f"Unexpected error: {str(e)}"
                    job.last_error_at = datetime.utcnow()
                    job.updated_at = datetime.utcnow()
                    db.add(job)
                    
                    # Log error
                    log = tiss_service.create_audit_log(
                        clinic_id=job.clinic_id,
                        provider_id=job.provider_id,
                        job_id=job.id,
                        level=TISSLogLevel.ERROR,
                        message=f"Unexpected error processing job: {str(e)}",
                        operation="process_job"
                    )
                    db.add(log)
                    db.commit()
        except Exception as db_error:
            logger.error(f"Error updating job status: {str(db_error)}")
        
        # Retry the task if it's not the final attempt
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}

@celery_app.task
def process_pending_tiss_jobs():
    """Process all pending TISS jobs."""
    
    try:
        with get_db_session() as db:
            # Get pending jobs
            pending_jobs = db.exec(
                select(TISSJob)
                .where(
                    and_(
                        TISSJob.status == TISSJobStatus.PENDING,
                        TISSJob.next_retry_at <= datetime.utcnow()
                    )
                )
                .options(selectinload(TISSJob.provider))
                .limit(10)  # Process up to 10 jobs at a time
            ).all()
            
            processed_count = 0
            for job in pending_jobs:
                try:
                    # Queue job for processing
                    process_tiss_job_task.delay(str(job.id))
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Error queuing job {job.id}: {str(e)}")
            
            logger.info(f"Queued {processed_count} pending TISS jobs for processing")
            return {"status": "success", "processed_count": processed_count}
            
    except Exception as e:
        logger.error(f"Error processing pending TISS jobs: {str(e)}")
        return {"status": "error", "message": str(e)}

@celery_app.task
def cleanup_old_tiss_logs(days_to_keep: int = 90):
    """Clean up old TISS logs."""
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with get_db_session() as db:
            # Delete old logs
            result = db.exec(
                select(TISSLog).where(TISSLog.created_at < cutoff_date)
            ).all()
            
            deleted_count = 0
            for log in result:
                db.delete(log)
                deleted_count += 1
            
            db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old TISS logs")
            return {"status": "success", "deleted_count": deleted_count}
            
    except Exception as e:
        logger.error(f"Error cleaning up TISS logs: {str(e)}")
        return {"status": "error", "message": str(e)}

@celery_app.task
def monitor_tiss_provider_health():
    """Monitor TISS provider health."""
    
    try:
        with get_db_session() as db:
            # Get active providers
            providers = db.exec(
                select(TISSProvider).where(TISSProvider.status == "active")
            ).all()
            
            tiss_service = TISSService()
            
            for provider in providers:
                try:
                    # Test connection
                    import asyncio
                    test_result = asyncio.run(tiss_service.test_connection(
                        endpoint_url=provider.endpoint_url,
                        username=provider.username,
                        password=security.decrypt_field(provider.password_encrypted),
                        timeout=provider.timeout_seconds
                    ))
                    
                    # Update provider status
                    if test_result.success:
                        provider.last_successful_request = datetime.utcnow()
                        provider.status = "active"
                    else:
                        provider.status = "inactive"
                    
                    provider.last_test_result = test_result.dict()
                    provider.last_tested_at = datetime.utcnow()
                    db.add(provider)
                    
                    # Log health check
                    log = tiss_service.create_audit_log(
                        clinic_id=provider.clinic_id,
                        provider_id=provider.id,
                        level=TISSLogLevel.INFO if test_result.success else TISSLogLevel.WARNING,
                        message=f"Provider health check: {'success' if test_result.success else 'failed'}",
                        operation="health_check",
                        details=test_result.dict()
                    )
                    db.add(log)
                    
                except Exception as e:
                    logger.error(f"Error checking provider {provider.id} health: {str(e)}")
            
            db.commit()
            logger.info(f"Completed health check for {len(providers)} TISS providers")
            return {"status": "success", "providers_checked": len(providers)}
            
    except Exception as e:
        logger.error(f"Error monitoring TISS provider health: {str(e)}")
        return {"status": "error", "message": str(e)}

# Periodic tasks configuration
celery_app.conf.beat_schedule = {
    'process-pending-tiss-jobs': {
        'task': 'app.workers.tiss_tasks.process_pending_tiss_jobs',
        'schedule': 60.0,  # Every minute
    },
    'monitor-tiss-provider-health': {
        'task': 'app.workers.tiss_tasks.monitor_tiss_provider_health',
        'schedule': 300.0,  # Every 5 minutes
    },
    'cleanup-old-tiss-logs': {
        'task': 'app.workers.tiss_tasks.cleanup_old_tiss_logs',
        'schedule': 86400.0,  # Daily
    },
}
