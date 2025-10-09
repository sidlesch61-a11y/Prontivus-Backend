"""
Database models for ethical locks and anti-collision mechanisms.
"""

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
import uuid

class LockType(str, Enum):
    """Types of ethical locks."""
    MEDICAL_RECORD_EDIT = "medical_record_edit"
    SADT_SUBMISSION = "sadt_submission"
    TUSS_SUBMISSION = "tuss_submission"
    CID_DIAGNOSIS = "cid_diagnosis"
    PRESCRIPTION_EDIT = "prescription_edit"
    APPOINTMENT_EDIT = "appointment_edit"

class LockStatus(str, Enum):
    """Lock status enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"
    RELEASED = "released"
    FORCE_UNLOCKED = "force_unlocked"

class CollisionType(str, Enum):
    """Types of collisions detected."""
    DUPLICATE_SUBMISSION = "duplicate_submission"
    CID_CONFLICT = "cid_conflict"
    EXAM_CONFLICT = "exam_conflict"
    MEDICATION_CONFLICT = "medication_conflict"
    SCHEDULE_CONFLICT = "schedule_conflict"

class EthicalLock(SQLModel, table=True):
    """Ethical lock model for preventing concurrent edits and conflicts."""
    
    __tablename__ = "ethical_locks"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Lock identification
    lock_type: LockType = Field(description="Type of lock")
    resource_id: uuid.UUID = Field(description="ID of the locked resource")
    resource_type: str = Field(description="Type of resource (medical_record, appointment, etc.)")
    
    # Lock ownership
    locked_by: uuid.UUID = Field(foreign_key="users.id", description="User who acquired the lock")
    locked_at: datetime = Field(default_factory=datetime.utcnow, description="When lock was acquired")
    lock_expires_at: datetime = Field(description="When lock expires")
    
    # Lock management
    status: LockStatus = Field(default=LockStatus.ACTIVE, description="Current lock status")
    heartbeat_at: Optional[datetime] = Field(default=None, description="Last heartbeat timestamp")
    released_at: Optional[datetime] = Field(default=None, description="When lock was released")
    
    # Lock metadata
    lock_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    reason: Optional[str] = Field(default=None, description="Reason for acquiring lock")
    
    # Force unlock (admin only)
    force_unlocked_by: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None)
    force_unlocked_at: Optional[datetime] = Field(default=None)
    force_unlock_reason: Optional[str] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    locked_by_user: Optional["User"] = Relationship(foreign_keys=[locked_by])
    force_unlocked_by_user: Optional["User"] = Relationship(foreign_keys=[force_unlocked_by])

class CollisionDetection(SQLModel, table=True):
    """Collision detection model for tracking conflicts."""
    
    __tablename__ = "collision_detections"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Collision identification
    collision_type: CollisionType = Field(description="Type of collision detected")
    resource_id: uuid.UUID = Field(description="ID of the resource with collision")
    resource_type: str = Field(description="Type of resource")
    
    # Collision details
    conflicting_resource_id: Optional[uuid.UUID] = Field(default=None, description="ID of conflicting resource")
    conflicting_resource_type: Optional[str] = Field(default=None, description="Type of conflicting resource")
    
    # Detection metadata
    detection_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    severity: str = Field(default="medium", description="Severity of collision (low, medium, high, critical)")
    
    # Resolution
    status: str = Field(default="detected", description="Status (detected, reviewed, resolved, ignored)")
    resolved_by: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None)
    resolved_at: Optional[datetime] = Field(default=None)
    resolution_notes: Optional[str] = Field(default=None)
    
    # Manual review
    requires_manual_review: bool = Field(default=False, description="Whether manual review is required")
    reviewed_by: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None)
    reviewed_at: Optional[datetime] = Field(default=None)
    review_notes: Optional[str] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    resolved_by_user: Optional["User"] = Relationship(foreign_keys=[resolved_by])
    reviewed_by_user: Optional["User"] = Relationship(foreign_keys=[reviewed_by])

class LockAuditLog(SQLModel, table=True):
    """Audit log for ethical lock operations."""
    
    __tablename__ = "lock_audit_logs"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    lock_id: Optional[uuid.UUID] = Field(foreign_key="ethical_locks.id", default=None)
    
    # Operation details
    operation: str = Field(description="Operation performed (acquire, release, heartbeat, force_unlock)")
    user_id: uuid.UUID = Field(foreign_key="users.id", description="User who performed operation")
    user_role: str = Field(description="Role of user")
    
    # Operation metadata
    operation_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    success: bool = Field(description="Whether operation was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if operation failed")
    
    # Technical details
    ip_address: Optional[str] = Field(default=None, description="IP address of user")
    user_agent: Optional[str] = Field(default=None, description="User agent string")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    lock: Optional["EthicalLock"] = Relationship()
    user: Optional["User"] = Relationship()

# Pydantic schemas for API
class LockRequest(SQLModel):
    """Request schema for acquiring a lock."""
    resource_id: uuid.UUID = Field(description="ID of resource to lock")
    resource_type: str = Field(description="Type of resource")
    lock_type: LockType = Field(description="Type of lock")
    reason: Optional[str] = Field(default=None, description="Reason for acquiring lock")
    ttl_minutes: int = Field(default=15, description="Lock TTL in minutes")

class LockResponse(SQLModel):
    """Response schema for lock operations."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    lock_type: LockType
    resource_id: uuid.UUID
    resource_type: str
    locked_by: uuid.UUID
    locked_at: datetime
    lock_expires_at: datetime
    status: LockStatus
    heartbeat_at: Optional[datetime] = None
    lock_meta: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None

class HeartbeatRequest(SQLModel):
    """Request schema for lock heartbeat."""
    lock_id: uuid.UUID = Field(description="ID of lock to extend")
    extend_minutes: int = Field(default=15, description="Minutes to extend lock")

class HeartbeatResponse(SQLModel):
    """Response schema for heartbeat operations."""
    lock_id: uuid.UUID
    new_expires_at: datetime
    status: str
    message: str

class UnlockRequest(SQLModel):
    """Request schema for releasing a lock."""
    lock_id: uuid.UUID = Field(description="ID of lock to release")
    reason: Optional[str] = Field(default=None, description="Reason for releasing lock")

class ForceUnlockRequest(SQLModel):
    """Request schema for force unlocking (admin only)."""
    lock_id: uuid.UUID = Field(description="ID of lock to force unlock")
    reason: str = Field(description="Reason for force unlock")
    notify_user: bool = Field(default=True, description="Whether to notify the locked user")

class CollisionDetectionResponse(SQLModel):
    """Response schema for collision detection."""
    id: uuid.UUID
    collision_type: CollisionType
    resource_id: uuid.UUID
    resource_type: str
    conflicting_resource_id: Optional[uuid.UUID] = None
    conflicting_resource_type: Optional[str] = None
    severity: str
    status: str
    requires_manual_review: bool
    detection_meta: Optional[Dict[str, Any]] = None
    created_at: datetime

class DuplicateSubmissionResponse(SQLModel):
    """Response schema for duplicate submission detection."""
    conflict: bool = Field(description="Whether conflict was detected")
    existing_job_id: Optional[uuid.UUID] = None
    existing_job_status: Optional[str] = None
    message: str
    audit_log_id: Optional[uuid.UUID] = None

# Utility classes
class EthicalLockManager:
    """Utility class for ethical lock management."""
    
    @staticmethod
    def calculate_expiry_time(ttl_minutes: int) -> datetime:
        """Calculate lock expiry time."""
        return datetime.utcnow() + timedelta(minutes=ttl_minutes)
    
    @staticmethod
    def is_lock_expired(lock_expires_at: datetime) -> bool:
        """Check if lock has expired."""
        return datetime.utcnow() > lock_expires_at
    
    @staticmethod
    def get_default_ttl(lock_type: LockType) -> int:
        """Get default TTL for lock type."""
        ttl_map = {
            LockType.MEDICAL_RECORD_EDIT: 15,
            LockType.SADT_SUBMISSION: 5,
            LockType.TUSS_SUBMISSION: 5,
            LockType.CID_DIAGNOSIS: 10,
            LockType.PRESCRIPTION_EDIT: 10,
            LockType.APPOINTMENT_EDIT: 5
        }
        return ttl_map.get(lock_type, 15)
    
    @staticmethod
    def can_user_acquire_lock(user_id: uuid.UUID, existing_lock: "EthicalLock") -> bool:
        """Check if user can acquire lock (same user can extend)."""
        return existing_lock.locked_by == user_id
    
    @staticmethod
    def generate_lock_key(resource_id: uuid.UUID, resource_type: str) -> str:
        """Generate unique lock key for resource."""
        return f"{resource_type}:{resource_id}"

class CollisionDetector:
    """Utility class for collision detection."""
    
    @staticmethod
    def detect_cid_conflict(
        patient_id: uuid.UUID,
        new_cid_code: str,
        existing_diagnoses: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect CID code conflicts."""
        
        # Define antagonistic CID code pairs
        antagonistic_pairs = {
            "F32": ["F31", "F33"],  # Depression vs Bipolar/Mania
            "F31": ["F32", "F33"],  # Bipolar vs Depression/Mania
            "F33": ["F31", "F32"],  # Mania vs Bipolar/Depression
            "I10": ["I11", "I12"],  # Essential hypertension vs Heart/Kidney disease
            "E11": ["E10", "E12"],  # Type 2 diabetes vs Type 1/Other
        }
        
        conflicting_codes = antagonistic_pairs.get(new_cid_code, [])
        
        for diagnosis in existing_diagnoses:
            if diagnosis.get("cid_code") in conflicting_codes:
                return {
                    "conflict_type": "antagonistic_cid",
                    "new_code": new_cid_code,
                    "conflicting_code": diagnosis["cid_code"],
                    "severity": "high",
                    "requires_manual_review": True
                }
        
        return None
    
    @staticmethod
    def detect_exam_conflict(
        patient_id: uuid.UUID,
        new_exam_code: str,
        recent_exams: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect exam conflicts."""
        
        # Define conflicting exam codes (same type of exam within short period)
        conflicting_exams = {
            "ECG": ["ECG", "HOLTER"],  # ECG conflicts with ECG or Holter
            "HOLTER": ["ECG", "HOLTER"],  # Holter conflicts with ECG or Holter
            "RX_TORAX": ["RX_TORAX", "TC_TORAX"],  # Chest X-ray conflicts
            "TC_TORAX": ["RX_TORAX", "TC_TORAX"],  # Chest CT conflicts
        }
        
        conflicting_codes = conflicting_exams.get(new_exam_code, [])
        
        for exam in recent_exams:
            if exam.get("exam_code") in conflicting_codes:
                # Check if within 7 days
                exam_date = exam.get("exam_date")
                if exam_date and (datetime.utcnow() - exam_date).days <= 7:
                    return {
                        "conflict_type": "duplicate_exam",
                        "new_code": new_exam_code,
                        "conflicting_code": exam["exam_code"],
                        "severity": "medium",
                        "requires_manual_review": True
                    }
        
        return None
    
    @staticmethod
    def detect_medication_conflict(
        patient_id: uuid.UUID,
        new_medication: str,
        current_medications: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect medication conflicts."""
        
        # Define medication interaction pairs
        interaction_pairs = {
            "WARFARINA": ["ASPIRINA", "IBUPROFENO", "DICLOFENACO"],
            "DIGOXINA": ["FUROSEMIDA", "HIDROCLOROTIAZIDA"],
            "METFORMINA": ["INSULINA", "GLIBENCLAMIDA"],
        }
        
        conflicting_meds = interaction_pairs.get(new_medication.upper(), [])
        
        for medication in current_medications:
            if medication.get("medication_name", "").upper() in conflicting_meds:
                return {
                    "conflict_type": "medication_interaction",
                    "new_medication": new_medication,
                    "conflicting_medication": medication["medication_name"],
                    "severity": "high",
                    "requires_manual_review": True
                }
        
        return None

class LockCleanupService:
    """Service for cleaning up expired locks."""
    
    @staticmethod
    async def cleanup_expired_locks() -> int:
        """Clean up expired locks."""
        
        # This would typically query the database
        # For now, return placeholder
        return 0
    
    @staticmethod
    async def get_lock_statistics() -> Dict[str, Any]:
        """Get lock usage statistics."""
        
        return {
            "active_locks": 0,
            "expired_locks": 0,
            "force_unlocked_locks": 0,
            "average_lock_duration_minutes": 0,
            "most_locked_resources": []
        }
