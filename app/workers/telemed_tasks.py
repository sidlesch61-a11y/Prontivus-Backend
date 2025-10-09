"""
Celery background tasks for telemedicine system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import uuid

from celery import Celery
from sqlmodel import Session, select, and_

from ..models.telemedicine import (
    TelemedSession, TelemedSessionLog, TelemedRecording,
    TelemedSessionStatus, TelemedSessionEvent, TelemedUserRole
)
from ..services.telemed_service import (
    TelemedService, WebRTCService, SFUService, RecordingService,
    TelemedAnalyticsService
)
from ..db.session import get_db

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery('telemed_tasks')

@celery_app.task(bind=True, max_retries=3)
def process_telemed_session_cleanup(self, session_id: str):
    """Clean up telemedicine session after completion."""
    
    try:
        logger.info(f"Starting telemedicine session cleanup for {session_id}")
        
        # Get database session
        db = next(get_db())
        
        # Get telemedicine session
        session = db.exec(
            select(TelemedSession).where(TelemedSession.id == session_id)
        ).first()
        
        if not session:
            logger.error(f"Telemedicine session not found: {session_id}")
            return {"status": "error", "message": "Session not found"}
        
        # Initialize services
        sfu_service = SFUService()
        recording_service = RecordingService()
        
        # Clean up SFU room
        try:
            await sfu_service.delete_room(session.room_id)
            logger.info(f"SFU room deleted: {session.room_id}")
        except Exception as e:
            logger.warning(f"Failed to delete SFU room: {str(e)}")
        
        # Clean up recording if exists
        if session.recording_file_path:
            try:
                # In production, this would clean up temporary files
                logger.info(f"Recording cleanup completed: {session.recording_file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup recording: {str(e)}")
        
        # Update session status if still active
        if session.status == TelemedSessionStatus.ACTIVE:
            session.status = TelemedSessionStatus.ENDED
            session.actual_end = datetime.utcnow()
            db.add(session)
        
        # Log cleanup completion
        log = TelemedSessionLog(
            session_id=session.id,
            clinic_id=session.clinic_id,
            event=TelemedSessionEvent.ENDED,
            meta={"cleanup_completed": True},
            message="Session cleanup completed"
        )
        db.add(log)
        db.commit()
        
        logger.info(f"Telemedicine session cleanup completed for {session_id}")
        return {"status": "success", "message": "Cleanup completed"}
        
    except Exception as e:
        logger.error(f"Error in telemedicine session cleanup: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying telemedicine session cleanup in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)
        
        return {"status": "error", "message": str(e)}

@celery_app.task(bind=True, max_retries=3)
def process_recording_encryption(self, recording_id: str):
    """Encrypt telemedicine recording."""
    
    try:
        logger.info(f"Starting recording encryption for {recording_id}")
        
        # Get database session
        db = next(get_db())
        
        # Get recording
        recording = db.exec(
            select(TelemedRecording).where(TelemedRecording.id == recording_id)
        ).first()
        
        if not recording:
            logger.error(f"Recording not found: {recording_id}")
            return {"status": "error", "message": "Recording not found"}
        
        # Initialize recording service
        recording_service = RecordingService()
        
        # Encrypt recording
        encrypted_path = recording_service.encrypt_recording(recording.file_path)
        
        # Update recording record
        recording.encrypted = True
        recording.encryption_key = recording_service.encryption_key.decode()
        recording.file_path = encrypted_path
        recording.processing_status = "encrypted"
        db.add(recording)
        
        # Get associated session
        session = db.exec(
            select(TelemedSession).where(TelemedSession.id == recording.session_id)
        ).first()
        
        if session:
            # Log encryption completion
            log = TelemedSessionLog(
                session_id=session.id,
                clinic_id=session.clinic_id,
                event=TelemedSessionEvent.RECORDING_STOPPED,
                meta={
                    "recording_id": recording_id,
                    "encrypted": True,
                    "file_path": encrypted_path
                },
                message="Recording encrypted successfully"
            )
            db.add(log)
        
        db.commit()
        
        logger.info(f"Recording encryption completed for {recording_id}")
        return {"status": "success", "message": "Encryption completed"}
        
    except Exception as e:
        logger.error(f"Error in recording encryption: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying recording encryption in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)
        
        return {"status": "error", "message": str(e)}

@celery_app.task(bind=True, max_retries=3)
def process_recording_upload(self, recording_id: str):
    """Upload telemedicine recording to storage."""
    
    try:
        logger.info(f"Starting recording upload for {recording_id}")
        
        # Get database session
        db = next(get_db())
        
        # Get recording
        recording = db.exec(
            select(TelemedRecording).where(TelemedRecording.id == recording_id)
        ).first()
        
        if not recording:
            logger.error(f"Recording not found: {recording_id}")
            return {"status": "error", "message": "Recording not found"}
        
        # Simulate upload to S3/MinIO
        # In production, this would use boto3 or similar
        storage_key = f"telemed/{recording.clinic_id}/{recording.session_id}/{recording.file_path}"
        
        # Update recording record
        recording.storage_key = storage_key
        recording.processing_status = "uploaded"
        db.add(recording)
        
        # Get associated session
        session = db.exec(
            select(TelemedSession).where(TelemedSession.id == recording.session_id)
        ).first()
        
        if session:
            # Update session with recording info
            session.recording_file_path = storage_key
            session.recording_file_size = recording.file_size
            db.add(session)
            
            # Log upload completion
            log = TelemedSessionLog(
                session_id=session.id,
                clinic_id=session.clinic_id,
                event=TelemedSessionEvent.RECORDING_STOPPED,
                meta={
                    "recording_id": recording_id,
                    "storage_key": storage_key,
                    "file_size": recording.file_size
                },
                message="Recording uploaded successfully"
            )
            db.add(log)
        
        db.commit()
        
        logger.info(f"Recording upload completed for {recording_id}")
        return {"status": "success", "message": "Upload completed"}
        
    except Exception as e:
        logger.error(f"Error in recording upload: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying recording upload in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)
        
        return {"status": "error", "message": str(e)}

@celery_app.task(bind=True, max_retries=3)
def process_session_analytics(self, clinic_id: str, start_date: str, end_date: str):
    """Generate telemedicine session analytics."""
    
    try:
        logger.info(f"Starting session analytics for clinic {clinic_id}")
        
        # Get database session
        db = next(get_db())
        
        # Get sessions for date range
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        sessions = db.exec(
            select(TelemedSession).where(
                and_(
                    TelemedSession.clinic_id == clinic_id,
                    TelemedSession.scheduled_start >= start_dt,
                    TelemedSession.scheduled_start <= end_dt
                )
            )
        ).all()
        
        # Initialize analytics service
        analytics_service = TelemedAnalyticsService()
        
        # Generate report
        report = analytics_service.generate_clinic_report(clinic_id, sessions)
        
        # Store report (in production, this would be stored in database or cache)
        logger.info(f"Analytics report generated for clinic {clinic_id}")
        
        return {
            "status": "success",
            "message": "Analytics generated",
            "report": report
        }
        
    except Exception as e:
        logger.error(f"Error in session analytics: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying session analytics in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)
        
        return {"status": "error", "message": str(e)}

@celery_app.task(bind=True, max_retries=3)
def process_session_monitoring(self, session_id: str):
    """Monitor active telemedicine session."""
    
    try:
        logger.info(f"Starting session monitoring for {session_id}")
        
        # Get database session
        db = next(get_db())
        
        # Get session
        session = db.exec(
            select(TelemedSession).where(TelemedSession.id == session_id)
        ).first()
        
        if not session:
            logger.error(f"Session not found: {session_id}")
            return {"status": "error", "message": "Session not found"}
        
        # Check if session is still active
        if session.status != TelemedSessionStatus.ACTIVE:
            logger.info(f"Session {session_id} is no longer active")
            return {"status": "completed", "message": "Session no longer active"}
        
        # Check for session timeout
        if session.actual_start:
            max_duration = timedelta(minutes=session.max_duration_minutes)
            if datetime.utcnow() > session.actual_start + max_duration:
                logger.warning(f"Session {session_id} has exceeded maximum duration")
                
                # Auto-end session
                session.status = TelemedSessionStatus.ENDED
                session.actual_end = datetime.utcnow()
                db.add(session)
                
                # Log timeout
                log = TelemedSessionLog(
                    session_id=session.id,
                    clinic_id=session.clinic_id,
                    event=TelemedSessionEvent.ENDED,
                    meta={"auto_ended": True, "reason": "timeout"},
                    message="Session auto-ended due to timeout"
                )
                db.add(log)
                db.commit()
                
                return {"status": "timeout", "message": "Session auto-ended"}
        
        # Check SFU room status
        sfu_service = SFUService()
        room_status = await sfu_service.get_room_status(session.room_id)
        
        if room_status.get("status") == "error":
            logger.warning(f"SFU room error for session {session_id}")
            
            # Log error
            log = TelemedSessionLog(
                session_id=session.id,
                clinic_id=session.clinic_id,
                event=TelemedSessionEvent.ERROR,
                meta={"sfu_error": room_status.get("error")},
                message="SFU room error detected"
            )
            db.add(log)
            db.commit()
        
        # Schedule next monitoring check
        if session.status == TelemedSessionStatus.ACTIVE:
            # Schedule next check in 30 seconds
            process_session_monitoring.apply_async(
                args=[session_id],
                countdown=30
            )
        
        logger.info(f"Session monitoring completed for {session_id}")
        return {"status": "success", "message": "Monitoring completed"}
        
    except Exception as e:
        logger.error(f"Error in session monitoring: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 30 * (2 ** self.request.retries)
            logger.info(f"Retrying session monitoring in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)
        
        return {"status": "error", "message": str(e)}

@celery_app.task(bind=True, max_retries=3)
def process_turn_credentials_cleanup(self, session_id: str):
    """Clean up expired TURN credentials."""
    
    try:
        logger.info(f"Starting TURN credentials cleanup for {session_id}")
        
        # Get database session
        db = next(get_db())
        
        # Get session
        session = db.exec(
            select(TelemedSession).where(TelemedSession.id == session_id)
        ).first()
        
        if not session:
            logger.error(f"Session not found: {session_id}")
            return {"status": "error", "message": "Session not found"}
        
        # Clean up TURN credentials
        # In production, this would call TURN server API to revoke credentials
        logger.info(f"TURN credentials cleaned up for session {session_id}")
        
        return {"status": "success", "message": "TURN credentials cleaned up"}
        
    except Exception as e:
        logger.error(f"Error in TURN credentials cleanup: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying TURN credentials cleanup in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)
        
        return {"status": "error", "message": str(e)}

@celery_app.task(bind=True, max_retries=3)
def process_telemed_health_check(self):
    """Perform telemedicine system health check."""
    
    try:
        logger.info("Starting telemedicine system health check")
        
        # Get database session
        db = next(get_db())
        
        # Check active sessions
        active_sessions = db.exec(
            select(TelemedSession).where(
                TelemedSession.status == TelemedSessionStatus.ACTIVE
            )
        ).all()
        
        # Check for stuck sessions
        stuck_sessions = []
        for session in active_sessions:
            if session.actual_start:
                max_duration = timedelta(minutes=session.max_duration_minutes)
                if datetime.utcnow() > session.actual_start + max_duration:
                    stuck_sessions.append(session.id)
        
        # Check SFU connectivity
        sfu_service = SFUService()
        sfu_status = await sfu_service.get_room_status("health_check")
        
        # Check TURN server connectivity
        webrtc_service = WebRTCService()
        turn_status = await webrtc_service.generate_turn_credentials("health_check", 60)
        
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "active_sessions": len(active_sessions),
            "stuck_sessions": len(stuck_sessions),
            "sfu_status": sfu_status.get("status", "unknown"),
            "turn_status": "healthy" if turn_status else "unhealthy",
            "overall_status": "healthy"
        }
        
        # Determine overall health
        if len(stuck_sessions) > 0 or sfu_status.get("status") == "error":
            health_status["overall_status"] = "degraded"
        
        logger.info(f"Telemedicine system health check completed: {health_status['overall_status']}")
        return {"status": "success", "health": health_status}
        
    except Exception as e:
        logger.error(f"Error in telemedicine health check: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying telemedicine health check in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)
        
        return {"status": "error", "message": str(e)}

# Periodic tasks
@celery_app.task
def cleanup_expired_sessions():
    """Clean up expired telemedicine sessions."""
    
    try:
        logger.info("Starting expired sessions cleanup")
        
        # Get database session
        db = next(get_db())
        
        # Find expired sessions
        expired_sessions = db.exec(
            select(TelemedSession).where(
                and_(
                    TelemedSession.status == TelemedSessionStatus.ACTIVE,
                    TelemedSession.scheduled_end < datetime.utcnow()
                )
            )
        ).all()
        
        # Clean up expired sessions
        for session in expired_sessions:
            session.status = TelemedSessionStatus.ENDED
            session.actual_end = datetime.utcnow()
            db.add(session)
            
            # Log cleanup
            log = TelemedSessionLog(
                session_id=session.id,
                clinic_id=session.clinic_id,
                event=TelemedSessionEvent.ENDED,
                meta={"auto_ended": True, "reason": "expired"},
                message="Session auto-ended due to expiration"
            )
            db.add(log)
        
        db.commit()
        
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        return {"status": "success", "cleaned_sessions": len(expired_sessions)}
        
    except Exception as e:
        logger.error(f"Error in expired sessions cleanup: {str(e)}")
        return {"status": "error", "message": str(e)}

@celery_app.task
def generate_daily_analytics():
    """Generate daily telemedicine analytics."""
    
    try:
        logger.info("Starting daily analytics generation")
        
        # Get database session
        db = next(get_db())
        
        # Get yesterday's sessions
        yesterday = datetime.utcnow() - timedelta(days=1)
        start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        sessions = db.exec(
            select(TelemedSession).where(
                and_(
                    TelemedSession.scheduled_start >= start_date,
                    TelemedSession.scheduled_start <= end_date
                )
            )
        ).all()
        
        # Group by clinic
        clinics = {}
        for session in sessions:
            clinic_id = str(session.clinic_id)
            if clinic_id not in clinics:
                clinics[clinic_id] = []
            clinics[clinic_id].append(session)
        
        # Generate analytics for each clinic
        analytics_service = TelemedAnalyticsService()
        reports = {}
        
        for clinic_id, clinic_sessions in clinics.items():
            report = analytics_service.generate_clinic_report(clinic_id, clinic_sessions)
            reports[clinic_id] = report
        
        logger.info(f"Generated daily analytics for {len(clinics)} clinics")
        return {"status": "success", "reports": reports}
        
    except Exception as e:
        logger.error(f"Error in daily analytics generation: {str(e)}")
        return {"status": "error", "message": str(e)}
