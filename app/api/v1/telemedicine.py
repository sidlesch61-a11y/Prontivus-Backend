"""
API endpoints for native telemedicine system with WebRTC orchestration.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, and_
from typing import List, Optional
import uuid
import json
import logging
from datetime import datetime, timedelta

from ..models.telemedicine import (
    TelemedSession, TelemedSessionLog, TelemedRecording,
    TelemedSessionCreateRequest, TelemedSessionResponse, TelemedJoinRequest,
    TelemedJoinResponse, TelemedConsentRequest, TelemedConsentResponse,
    TelemedSessionEndRequest, TelemedSessionEndResponse, TelemedSessionLogResponse,
    TelemedSessionStatus, TelemedSessionEvent, TelemedUserRole,
    WebRTCCredentials, SFUConfig, RecordingConfig,
    TelemedSessionValidator, TelemedRecordingManager
)
from ..core.auth import get_current_user, get_current_tenant
from ..db.session import get_db
from ..services.telemed_service import TelemedService
from ..services.webrtc_service import WebRTCService
from ..services.sfu_service import SFUService
from ..services.recording_service import RecordingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/telemed", tags=["telemedicine"])

@router.post("/sessions/create", response_model=TelemedSessionResponse)
async def create_telemed_session(
    session_data: TelemedSessionCreateRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Create a new telemedicine session."""
    
    try:
        # Validate session time window
        if not TelemedSessionValidator.validate_session_time_window(
            session_data.scheduled_start, session_data.scheduled_end
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session time window is invalid"
            )
        
        # Validate session duration
        if not TelemedSessionValidator.validate_session_duration(
            session_data.scheduled_start, session_data.scheduled_end,
            session_data.max_duration_minutes
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session duration exceeds maximum allowed duration"
            )
        
        # Get appointment details
        appointment = db.exec(
            select("Appointment").where(
                and_(
                    "Appointment.id == session_data.appointment_id",
                    "Appointment.clinic_id == current_tenant.id"
                )
            )
        ).first()
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        # Initialize services
        telemed_service = TelemedService()
        webrtc_service = WebRTCService()
        sfu_service = SFUService()
        
        # Generate session identifiers
        session_id = str(uuid.uuid4())
        room_id = f"room_{session_data.appointment_id}_{session_id[:8]}"
        
        # Generate JWT link token
        link_token = webrtc_service.generate_session_token(
            appointment_id=str(session_data.appointment_id),
            doctor_id=str(session_data.doctor_id),
            patient_id=str(appointment.patient_id),
            clinic_id=str(current_tenant.id),
            session_id=session_id,
            expires_in=3600  # 1 hour
        )
        
        # Create SFU room
        sfu_config = await sfu_service.create_room(
            room_id=room_id,
            session_id=session_id,
            max_participants=2,
            recording_enabled=session_data.allow_recording
        )
        
        # Generate TURN credentials
        turn_credentials = await webrtc_service.generate_turn_credentials(
            session_id=session_id,
            ttl=3600
        )
        
        # Create session record
        session = TelemedSession(
            clinic_id=current_tenant.id,
            appointment_id=session_data.appointment_id,
            doctor_id=session_data.doctor_id,
            patient_id=appointment.patient_id,
            link_token=link_token,
            session_id=session_id,
            room_id=room_id,
            allow_recording=session_data.allow_recording,
            recording_encrypted=True,
            max_duration_minutes=session_data.max_duration_minutes,
            scheduled_start=session_data.scheduled_start,
            scheduled_end=session_data.scheduled_end,
            status=TelemedSessionStatus.SCHEDULED,
            sfu_config=sfu_config.dict(),
            turn_credentials=turn_credentials.dict(),
            session_meta={
                "created_by": current_user.id,
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            }
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Log session creation
        log = TelemedSessionLog(
            session_id=session.id,
            clinic_id=current_tenant.id,
            event=TelemedSessionEvent.CREATED,
            user_id=current_user.id,
            user_role=TelemedUserRole.DOCTOR,
            meta={
                "allow_recording": session_data.allow_recording,
                "max_duration_minutes": session_data.max_duration_minutes,
                "sfu_config": sfu_config.dict()
            },
            message="Telemedicine session created",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(log)
        db.commit()
        
        logger.info(f"Telemedicine session created: {session.id} by user {current_user.id}")
        
        return TelemedSessionResponse.from_orm(session)
        
    except Exception as e:
        logger.error(f"Error creating telemedicine session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create telemedicine session"
        )

@router.get("/sessions/{link_token}/join", response_model=TelemedJoinResponse)
async def join_telemed_session(
    link_token: str,
    join_request: TelemedJoinRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Join a telemedicine session using link token."""
    
    try:
        # Validate JWT token
        webrtc_service = WebRTCService()
        token_payload = webrtc_service.validate_session_token(link_token)
        
        if not token_payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token"
            )
        
        # Get session
        session = db.exec(
            select(TelemedSession).where(TelemedSession.link_token == link_token)
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Validate session status
        if session.status != TelemedSessionStatus.SCHEDULED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session is not available for joining. Status: {session.status}"
            )
        
        # Validate time window
        now = datetime.utcnow()
        if not (session.scheduled_start <= now <= session.scheduled_end):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session is outside the allowed time window"
            )
        
        # Update session status to active if first join
        if session.status == TelemedSessionStatus.SCHEDULED:
            session.status = TelemedSessionStatus.ACTIVE
            session.actual_start = now
            db.add(session)
        
        # Generate fresh TURN credentials
        turn_credentials = await webrtc_service.generate_turn_credentials(
            session_id=session.session_id,
            ttl=1800  # 30 minutes
        )
        
        # Get ICE servers configuration
        ice_servers = webrtc_service.get_ice_servers(turn_credentials)
        
        # Prepare session configuration
        session_config = {
            "session_id": session.session_id,
            "room_id": session.room_id,
            "max_duration_minutes": session.max_duration_minutes,
            "allow_recording": session.allow_recording,
            "recording_encrypted": session.recording_encrypted,
            "user_role": join_request.user_role,
            "expires_at": (now + timedelta(minutes=session.max_duration_minutes)).isoformat()
        }
        
        # Log join event
        log = TelemedSessionLog(
            session_id=session.id,
            clinic_id=session.clinic_id,
            event=TelemedSessionEvent.JOINED,
            user_role=join_request.user_role,
            meta={
                "user_role": join_request.user_role,
                "session_config": session_config
            },
            message=f"User joined session as {join_request.user_role}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(log)
        db.commit()
        
        logger.info(f"User joined telemedicine session: {session.id} as {join_request.user_role}")
        
        return TelemedJoinResponse(
            session_id=session.session_id,
            room_id=session.room_id,
            sfu_endpoint=session.sfu_config.get("endpoint"),
            turn_credentials=turn_credentials.dict(),
            ice_servers=ice_servers,
            session_config=session_config,
            expires_at=now + timedelta(minutes=session.max_duration_minutes)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error joining telemedicine session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join telemedicine session"
        )

@router.post("/sessions/{session_id}/consent", response_model=TelemedConsentResponse)
async def manage_telemed_consent(
    session_id: uuid.UUID,
    consent_data: TelemedConsentRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Manage consent for telemedicine session recording."""
    
    try:
        # Get session
        session = db.exec(
            select(TelemedSession).where(
                and_(
                    TelemedSession.id == session_id,
                    TelemedSession.clinic_id == current_tenant.id
                )
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Validate session status
        if session.status != TelemedSessionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session is not active"
            )
        
        # Update consent based on user role
        if current_user.id == session.doctor_id:
            session.doctor_consent = consent_data.consent
        elif current_user.id == session.patient_id:
            session.patient_consent = consent_data.consent
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not authorized to give consent for this session"
            )
        
        # Update consent timestamp if both consents are given
        if session.doctor_consent and session.patient_consent:
            session.consent_timestamp = datetime.utcnow()
        
        db.add(session)
        
        # Log consent event
        event = TelemedSessionEvent.CONSENT_GIVEN if consent_data.consent else TelemedSessionEvent.CONSENT_DENIED
        log = TelemedSessionLog(
            session_id=session.id,
            clinic_id=current_tenant.id,
            event=event,
            user_id=current_user.id,
            user_role=TelemedUserRole.DOCTOR if current_user.id == session.doctor_id else TelemedUserRole.PATIENT,
            meta={
                "consent": consent_data.consent,
                "consent_type": consent_data.consent_type,
                "doctor_consent": session.doctor_consent,
                "patient_consent": session.patient_consent
            },
            message=f"Consent {'given' if consent_data.consent else 'denied'} for {consent_data.consent_type}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(log)
        
        # Start recording if consent is given and recording is allowed
        if consent_data.consent and session.allow_recording and session.doctor_consent and session.patient_consent:
            recording_service = RecordingService()
            await recording_service.start_recording(session)
            
            # Log recording start
            recording_log = TelemedSessionLog(
                session_id=session.id,
                clinic_id=current_tenant.id,
                event=TelemedSessionEvent.RECORDING_STARTED,
                user_id=current_user.id,
                meta={"recording_enabled": True},
                message="Recording started",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )
            db.add(recording_log)
        
        db.commit()
        
        logger.info(f"Consent {'given' if consent_data.consent else 'denied'} for session {session.id} by user {current_user.id}")
        
        return TelemedConsentResponse(
            session_id=session.id,
            user_id=current_user.id,
            consent=consent_data.consent,
            consent_type=consent_data.consent_type,
            timestamp=datetime.utcnow(),
            message=f"Consent {'given' if consent_data.consent else 'denied'} successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error managing telemedicine consent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to manage consent"
        )

@router.post("/sessions/{session_id}/end", response_model=TelemedSessionEndResponse)
async def end_telemed_session(
    session_id: uuid.UUID,
    end_data: TelemedSessionEndRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """End a telemedicine session."""
    
    try:
        # Get session
        session = db.exec(
            select(TelemedSession).where(
                and_(
                    TelemedSession.id == session_id,
                    TelemedSession.clinic_id == current_tenant.id
                )
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Validate session status
        if session.status not in [TelemedSessionStatus.ACTIVE, TelemedSessionStatus.SCHEDULED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session is not active"
            )
        
        # Update session status
        session.status = TelemedSessionStatus.ENDED
        session.actual_end = datetime.utcnow()
        
        # Calculate session duration
        duration_seconds = None
        if session.actual_start:
            duration_seconds = TelemedRecordingManager.calculate_recording_duration(
                session.actual_start, session.actual_end
            )
            session.recording_duration_seconds = duration_seconds
        
        # Finalize recording if it was active
        recording_file_path = None
        if session.allow_recording and session.doctor_consent and session.patient_consent:
            recording_service = RecordingService()
            recording_result = await recording_service.finalize_recording(session)
            
            if recording_result.success:
                session.recording_file_path = recording_result.file_path
                session.recording_file_size = recording_result.file_size
                recording_file_path = recording_result.file_path
                
                # Log recording completion
                recording_log = TelemedSessionLog(
                    session_id=session.id,
                    clinic_id=current_tenant.id,
                    event=TelemedSessionEvent.RECORDING_STOPPED,
                    user_id=current_user.id,
                    meta={
                        "file_path": recording_result.file_path,
                        "file_size": recording_result.file_size,
                        "duration_seconds": duration_seconds
                    },
                    message="Recording finalized successfully",
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent")
                )
                db.add(recording_log)
            else:
                # Log recording failure
                recording_log = TelemedSessionLog(
                    session_id=session.id,
                    clinic_id=current_tenant.id,
                    event=TelemedSessionEvent.RECORDING_FAILED,
                    user_id=current_user.id,
                    meta={"error": recording_result.error_message},
                    message=f"Recording failed: {recording_result.error_message}",
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent")
                )
                db.add(recording_log)
        
        # Update session metadata
        if not session.session_meta:
            session.session_meta = {}
        
        session.session_meta.update({
            "ended_by": current_user.id,
            "end_reason": end_data.reason,
            "end_notes": end_data.notes,
            "duration_seconds": duration_seconds
        })
        
        db.add(session)
        
        # Log session end
        log = TelemedSessionLog(
            session_id=session.id,
            clinic_id=current_tenant.id,
            event=TelemedSessionEvent.ENDED,
            user_id=current_user.id,
            meta={
                "reason": end_data.reason,
                "notes": end_data.notes,
                "duration_seconds": duration_seconds,
                "recording_file_path": recording_file_path
            },
            message="Session ended",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(log)
        db.commit()
        
        logger.info(f"Telemedicine session ended: {session.id} by user {current_user.id}")
        
        return TelemedSessionEndResponse(
            session_id=session.id,
            status=TelemedSessionStatus.ENDED,
            duration_seconds=duration_seconds,
            recording_file_path=recording_file_path,
            message="Session ended successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending telemedicine session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end session"
        )

@router.get("/sessions/{session_id}/logs", response_model=List[TelemedSessionLogResponse])
async def get_telemed_session_logs(
    session_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get logs for a specific telemedicine session."""
    
    # Verify session exists and belongs to clinic
    session = db.exec(
        select(TelemedSession).where(
            and_(
                TelemedSession.id == session_id,
                TelemedSession.clinic_id == current_tenant.id
            )
        )
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Get logs
    logs = db.exec(
        select(TelemedSessionLog).where(
            TelemedSessionLog.session_id == session_id
        ).order_by(TelemedSessionLog.created_at.desc()).offset(offset).limit(limit)
    ).all()
    
    return [TelemedSessionLogResponse.from_orm(log) for log in logs]

@router.get("/sessions", response_model=List[TelemedSessionResponse])
async def list_telemed_sessions(
    status: Optional[TelemedSessionStatus] = None,
    doctor_id: Optional[uuid.UUID] = None,
    patient_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    offset: int = 0,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """List telemedicine sessions with optional filters."""
    
    statement = select(TelemedSession).where(TelemedSession.clinic_id == current_tenant.id)
    
    if status:
        statement = statement.where(TelemedSession.status == status)
    
    if doctor_id:
        statement = statement.where(TelemedSession.doctor_id == doctor_id)
    
    if patient_id:
        statement = statement.where(TelemedSession.patient_id == patient_id)
    
    statement = statement.order_by(TelemedSession.created_at.desc()).offset(offset).limit(limit)
    
    sessions = db.exec(statement).all()
    
    return [TelemedSessionResponse.from_orm(session) for session in sessions]

@router.get("/sessions/{session_id}", response_model=TelemedSessionResponse)
async def get_telemed_session(
    session_id: uuid.UUID,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get telemedicine session by ID."""
    
    session = db.exec(
        select(TelemedSession).where(
            and_(
                TelemedSession.id == session_id,
                TelemedSession.clinic_id == current_tenant.id
            )
        )
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return TelemedSessionResponse.from_orm(session)
