"""
Telemedicine service for business logic and WebRTC orchestration.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import uuid
import jwt
import secrets

from cryptography.fernet import Fernet
import httpx

from ..models.telemedicine import (
    TelemedSession, TelemedSessionLog, TelemedRecording,
    TelemedSessionStatus, TelemedSessionEvent, TelemedUserRole,
    WebRTCCredentials, SFUConfig, RecordingConfig,
    TelemedSessionValidator, TelemedRecordingManager
)

logger = logging.getLogger(__name__)

class TelemedService:
    """Service for telemedicine operations and business logic."""
    
    def __init__(self):
        self.jwt_secret = "telemed_secret_key"  # In production, use environment variable
        self.jwt_algorithm = "HS256"
        self.encryption_service = Fernet.generate_key()
    
    def generate_session_token(
        self,
        appointment_id: str,
        doctor_id: str,
        patient_id: str,
        clinic_id: str,
        session_id: str,
        expires_in: int = 3600
    ) -> str:
        """Generate JWT token for session access."""
        
        payload = {
            "appointment_id": appointment_id,
            "doctor_id": doctor_id,
            "patient_id": patient_id,
            "clinic_id": clinic_id,
            "session_id": session_id,
            "exp": datetime.utcnow() + timedelta(seconds=expires_in),
            "iat": datetime.utcnow(),
            "iss": "prontivus_telemed"
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        return token
    
    def validate_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT session token."""
        
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Session token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid session token")
            return None
    
    def generate_session_identifiers(self) -> Tuple[str, str]:
        """Generate unique session and room identifiers."""
        
        session_id = str(uuid.uuid4())
        room_id = f"room_{session_id[:8]}"
        
        return session_id, room_id
    
    def validate_session_access(
        self,
        session: TelemedSession,
        user_id: str,
        user_role: TelemedUserRole
    ) -> bool:
        """Validate user access to session."""
        
        # Check if user is doctor or patient for this session
        if user_role == TelemedUserRole.DOCTOR and str(session.doctor_id) == user_id:
            return True
        elif user_role == TelemedUserRole.PATIENT and str(session.patient_id) == user_id:
            return True
        elif user_role == TelemedUserRole.ADMIN:
            return True
        
        return False
    
    def calculate_session_duration(self, session: TelemedSession) -> Optional[int]:
        """Calculate session duration in seconds."""
        
        if session.actual_start and session.actual_end:
            duration = session.actual_end - session.actual_start
            return int(duration.total_seconds())
        
        return None
    
    def is_session_expired(self, session: TelemedSession) -> bool:
        """Check if session has expired."""
        
        if session.actual_end:
            return True
        
        if session.actual_start:
            max_duration = timedelta(minutes=session.max_duration_minutes)
            return datetime.utcnow() > session.actual_start + max_duration
        
        return datetime.utcnow() > session.scheduled_end
    
    def get_session_statistics(self, sessions: List[TelemedSession]) -> Dict[str, Any]:
        """Calculate session statistics."""
        
        total_sessions = len(sessions)
        completed_sessions = len([s for s in sessions if s.status == TelemedSessionStatus.ENDED])
        cancelled_sessions = len([s for s in sessions if s.status == TelemedSessionStatus.CANCELLED])
        
        # Calculate average duration
        durations = []
        for session in sessions:
            if session.actual_start and session.actual_end:
                duration = self.calculate_session_duration(session)
                if duration:
                    durations.append(duration)
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Calculate recording statistics
        recorded_sessions = len([s for s in sessions if s.recording_file_path])
        total_recording_size = sum([s.recording_file_size or 0 for s in sessions])
        
        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "cancelled_sessions": cancelled_sessions,
            "completion_rate": (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0,
            "average_duration_seconds": avg_duration,
            "recorded_sessions": recorded_sessions,
            "recording_rate": (recorded_sessions / total_sessions * 100) if total_sessions > 0 else 0,
            "total_recording_size_bytes": total_recording_size
        }

class WebRTCService:
    """Service for WebRTC operations and TURN server management."""
    
    def __init__(self):
        self.turn_server_url = "https://turn.example.com"  # Configure in production
        self.turn_username = "turn_user"
        self.turn_password = "turn_password"
        self.stun_servers = [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": "stun:stun1.l.google.com:19302"}
        ]
    
    async def generate_turn_credentials(
        self,
        session_id: str,
        ttl: int = 3600
    ) -> WebRTCCredentials:
        """Generate TURN server credentials."""
        
        try:
            # Generate ephemeral credentials
            username = f"{session_id}_{secrets.token_hex(8)}"
            password = secrets.token_urlsafe(32)
            
            # In production, this would call TURN server REST API
            # For now, we'll simulate the response
            
            ice_servers = self.get_ice_servers(
                WebRTCCredentials(
                    ice_servers=self.stun_servers,
                    turn_username=username,
                    turn_password=password,
                    turn_ttl=ttl
                )
            )
            
            return WebRTCCredentials(
                ice_servers=ice_servers,
                turn_username=username,
                turn_password=password,
                turn_ttl=ttl
            )
            
        except Exception as e:
            logger.error(f"Error generating TURN credentials: {str(e)}")
            raise
    
    def get_ice_servers(self, credentials: WebRTCCredentials) -> List[Dict[str, Any]]:
        """Get ICE servers configuration."""
        
        ice_servers = self.stun_servers.copy()
        
        # Add TURN servers
        ice_servers.extend([
            {
                "urls": f"turn:{self.turn_server_url}",
                "username": credentials.turn_username,
                "credential": credentials.turn_password
            },
            {
                "urls": f"turns:{self.turn_server_url}",
                "username": credentials.turn_username,
                "credential": credentials.turn_password
            }
        ])
        
        return ice_servers
    
    def validate_ice_configuration(self, ice_servers: List[Dict[str, Any]]) -> bool:
        """Validate ICE servers configuration."""
        
        required_fields = ["urls"]
        
        for server in ice_servers:
            if not all(field in server for field in required_fields):
                return False
            
            # Validate TURN server credentials
            if "turn:" in server["urls"] or "turns:" in server["urls"]:
                if "username" not in server or "credential" not in server:
                    return False
        
        return True
    
    def generate_peer_connection_config(
        self,
        ice_servers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate peer connection configuration."""
        
        return {
            "iceServers": ice_servers,
            "iceCandidatePoolSize": 10,
            "bundlePolicy": "max-bundle",
            "rtcpMuxPolicy": "require"
        }

class SFUService:
    """Service for SFU (Selective Forwarding Unit) operations."""
    
    def __init__(self):
        self.sfu_endpoint = "https://sfu.example.com"  # Configure in production
        self.api_key = "sfu_api_key"
        self.timeout = 30
    
    async def create_room(
        self,
        room_id: str,
        session_id: str,
        max_participants: int = 2,
        recording_enabled: bool = False
    ) -> SFUConfig:
        """Create SFU room."""
        
        try:
            # Prepare room configuration
            room_config = {
                "room_id": room_id,
                "session_id": session_id,
                "max_participants": max_participants,
                "recording_enabled": recording_enabled,
                "capabilities": {
                    "audio": True,
                    "video": True,
                    "screen_share": True,
                    "recording": recording_enabled
                }
            }
            
            # In production, this would call SFU REST API
            # For now, we'll simulate the response
            
            sfu_config = SFUConfig(
                endpoint=self.sfu_endpoint,
                api_key=self.api_key,
                room_id=room_id,
                session_id=session_id,
                capabilities=room_config["capabilities"]
            )
            
            logger.info(f"SFU room created: {room_id}")
            return sfu_config
            
        except Exception as e:
            logger.error(f"Error creating SFU room: {str(e)}")
            raise
    
    async def delete_room(self, room_id: str) -> bool:
        """Delete SFU room."""
        
        try:
            # In production, this would call SFU REST API
            logger.info(f"SFU room deleted: {room_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting SFU room: {str(e)}")
            return False
    
    async def get_room_status(self, room_id: str) -> Dict[str, Any]:
        """Get SFU room status."""
        
        try:
            # In production, this would call SFU REST API
            return {
                "room_id": room_id,
                "status": "active",
                "participants": 0,
                "recording": False
            }
            
        except Exception as e:
            logger.error(f"Error getting SFU room status: {str(e)}")
            return {"status": "error", "error": str(e)}

class RecordingService:
    """Service for telemedicine recording management."""
    
    def __init__(self):
        self.storage_provider = "s3"
        self.storage_bucket = "prontivus-recordings"
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
    
    async def start_recording(self, session: TelemedSession) -> bool:
        """Start recording for telemedicine session."""
        
        try:
            # Validate recording prerequisites
            if not session.allow_recording:
                logger.warning(f"Recording not allowed for session {session.id}")
                return False
            
            if not session.doctor_consent or not session.patient_consent:
                logger.warning(f"Consent not given for session {session.id}")
                return False
            
            # Generate recording filename
            filename = TelemedRecordingManager.generate_recording_filename(
                session.session_id,
                datetime.utcnow()
            )
            
            # In production, this would start SFU recording
            # For now, we'll simulate the process
            
            logger.info(f"Recording started for session {session.id}: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting recording: {str(e)}")
            return False
    
    async def finalize_recording(self, session: TelemedSession) -> 'RecordingResult':
        """Finalize recording for telemedicine session."""
        
        try:
            # Calculate recording duration
            duration_seconds = TelemedRecordingManager.calculate_recording_duration(
                session.actual_start,
                session.actual_end
            )
            
            # Generate recording filename
            filename = TelemedRecordingManager.generate_recording_filename(
                session.session_id,
                session.actual_start
            )
            
            # Simulate file processing
            file_size = duration_seconds * 100000  # Simulate 100KB per second
            
            # Encrypt recording if required
            if session.recording_encrypted:
                # In production, this would encrypt the file
                logger.info(f"Recording encrypted: {filename}")
            
            # Upload to storage
            storage_key = f"telemed/{session.clinic_id}/{session.id}/{filename}"
            
            logger.info(f"Recording finalized for session {session.id}: {storage_key}")
            
            return RecordingResult(
                success=True,
                file_path=storage_key,
                file_size=file_size,
                duration_seconds=duration_seconds,
                encrypted=session.recording_encrypted
            )
            
        except Exception as e:
            logger.error(f"Error finalizing recording: {str(e)}")
            return RecordingResult(
                success=False,
                error_message=str(e)
            )
    
    def encrypt_recording(self, file_path: str) -> str:
        """Encrypt recording file."""
        
        try:
            # In production, this would encrypt the actual file
            encrypted_path = f"{file_path}.encrypted"
            logger.info(f"Recording encrypted: {encrypted_path}")
            return encrypted_path
            
        except Exception as e:
            logger.error(f"Error encrypting recording: {str(e)}")
            raise
    
    def decrypt_recording(self, encrypted_path: str, output_path: str) -> bool:
        """Decrypt recording file."""
        
        try:
            # In production, this would decrypt the actual file
            logger.info(f"Recording decrypted: {encrypted_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error decrypting recording: {str(e)}")
            return False

class RecordingResult:
    """Result of recording operation."""
    
    def __init__(
        self,
        success: bool,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None,
        duration_seconds: Optional[int] = None,
        encrypted: bool = False,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.file_path = file_path
        self.file_size = file_size
        self.duration_seconds = duration_seconds
        self.encrypted = encrypted
        self.error_message = error_message

class TelemedAnalyticsService:
    """Service for telemedicine analytics and reporting."""
    
    def __init__(self):
        self.metrics_cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def calculate_session_metrics(self, sessions: List[TelemedSession]) -> Dict[str, Any]:
        """Calculate comprehensive session metrics."""
        
        metrics = {
            "total_sessions": len(sessions),
            "sessions_by_status": {},
            "sessions_by_hour": {},
            "average_duration": 0,
            "recording_stats": {
                "total_recorded": 0,
                "total_size_bytes": 0,
                "average_size_bytes": 0
            },
            "consent_stats": {
                "doctor_consent_rate": 0,
                "patient_consent_rate": 0,
                "both_consent_rate": 0
            }
        }
        
        # Calculate status distribution
        for session in sessions:
            status = session.status.value
            metrics["sessions_by_status"][status] = metrics["sessions_by_status"].get(status, 0) + 1
        
        # Calculate hourly distribution
        for session in sessions:
            hour = session.scheduled_start.hour
            metrics["sessions_by_hour"][hour] = metrics["sessions_by_hour"].get(hour, 0) + 1
        
        # Calculate duration metrics
        durations = []
        for session in sessions:
            if session.actual_start and session.actual_end:
                duration = (session.actual_end - session.actual_start).total_seconds()
                durations.append(duration)
        
        if durations:
            metrics["average_duration"] = sum(durations) / len(durations)
        
        # Calculate recording statistics
        recorded_sessions = [s for s in sessions if s.recording_file_path]
        metrics["recording_stats"]["total_recorded"] = len(recorded_sessions)
        
        if recorded_sessions:
            total_size = sum([s.recording_file_size or 0 for s in recorded_sessions])
            metrics["recording_stats"]["total_size_bytes"] = total_size
            metrics["recording_stats"]["average_size_bytes"] = total_size / len(recorded_sessions)
        
        # Calculate consent statistics
        doctor_consent_count = len([s for s in sessions if s.doctor_consent])
        patient_consent_count = len([s for s in sessions if s.patient_consent])
        both_consent_count = len([s for s in sessions if s.doctor_consent and s.patient_consent])
        
        if sessions:
            metrics["consent_stats"]["doctor_consent_rate"] = (doctor_consent_count / len(sessions)) * 100
            metrics["consent_stats"]["patient_consent_rate"] = (patient_consent_count / len(sessions)) * 100
            metrics["consent_stats"]["both_consent_rate"] = (both_consent_count / len(sessions)) * 100
        
        return metrics
    
    def generate_clinic_report(self, clinic_id: str, sessions: List[TelemedSession]) -> Dict[str, Any]:
        """Generate comprehensive clinic report."""
        
        metrics = self.calculate_session_metrics(sessions)
        
        report = {
            "clinic_id": clinic_id,
            "report_period": {
                "start": min([s.scheduled_start for s in sessions]) if sessions else None,
                "end": max([s.scheduled_end for s in sessions]) if sessions else None
            },
            "summary": metrics,
            "recommendations": self.generate_recommendations(metrics),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return report
    
    def generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on metrics."""
        
        recommendations = []
        
        # Duration recommendations
        if metrics["average_duration"] > 3600:  # More than 1 hour
            recommendations.append("Consider shorter session durations to improve efficiency")
        
        # Recording recommendations
        recording_rate = (metrics["recording_stats"]["total_recorded"] / metrics["total_sessions"]) * 100
        if recording_rate < 50:
            recommendations.append("Consider increasing recording adoption for better documentation")
        
        # Consent recommendations
        if metrics["consent_stats"]["both_consent_rate"] < 80:
            recommendations.append("Improve consent collection process to increase compliance")
        
        return recommendations
