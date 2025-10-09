"""
Service for ethical locks and anti-collision business logic.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid
from sqlmodel import Session, select, and_, or_

from ..models.ethical_locks import (
    EthicalLock, CollisionDetection, LockAuditLog,
    LockType, LockStatus, CollisionType,
    EthicalLockManager, CollisionDetector
)

logger = logging.getLogger(__name__)

class EthicalLockService:
    """Service for ethical lock management and business logic."""
    
    def __init__(self):
        self.default_ttl_minutes = 15
        self.max_ttl_minutes = 60
        self.cleanup_interval_minutes = 5
    
    async def acquire_lock(
        self,
        db: Session,
        clinic_id: uuid.UUID,
        resource_id: uuid.UUID,
        resource_type: str,
        lock_type: LockType,
        user_id: uuid.UUID,
        ttl_minutes: Optional[int] = None
    ) -> Tuple[Optional[EthicalLock], Optional[str]]:
        """Acquire an ethical lock."""
        
        try:
            # Calculate TTL
            if ttl_minutes is None:
                ttl_minutes = EthicalLockManager.get_default_ttl(lock_type)
            
            ttl_minutes = min(ttl_minutes, self.max_ttl_minutes)
            expires_at = EthicalLockManager.calculate_expiry_time(ttl_minutes)
            
            # Check for existing active lock
            existing_lock = db.exec(
                select(EthicalLock).where(
                    and_(
                        EthicalLock.clinic_id == clinic_id,
                        EthicalLock.resource_id == resource_id,
                        EthicalLock.resource_type == resource_type,
                        EthicalLock.status == LockStatus.ACTIVE,
                        EthicalLock.lock_expires_at > datetime.utcnow()
                    )
                )
            ).first()
            
            if existing_lock:
                # Check if same user can extend lock
                if EthicalLockManager.can_user_acquire_lock(user_id, existing_lock):
                    # Extend existing lock
                    existing_lock.lock_expires_at = expires_at
                    existing_lock.heartbeat_at = datetime.utcnow()
                    existing_lock.updated_at = datetime.utcnow()
                    db.add(existing_lock)
                    db.commit()
                    db.refresh(existing_lock)
                    
                    return existing_lock, None
                else:
                    # Lock conflict
                    return None, f"Resource locked by user {existing_lock.locked_by}"
            
            # Create new lock
            lock = EthicalLock(
                clinic_id=clinic_id,
                lock_type=lock_type,
                resource_id=resource_id,
                resource_type=resource_type,
                locked_by=user_id,
                locked_at=datetime.utcnow(),
                lock_expires_at=expires_at,
                status=LockStatus.ACTIVE,
                heartbeat_at=datetime.utcnow(),
                lock_meta={
                    "ttl_minutes": ttl_minutes,
                    "acquired_via": "service"
                }
            )
            
            db.add(lock)
            db.commit()
            db.refresh(lock)
            
            logger.info(f"Lock acquired: {lock.id} for resource {resource_id}")
            return lock, None
            
        except Exception as e:
            logger.error(f"Error acquiring lock: {str(e)}")
            return None, str(e)
    
    async def release_lock(
        self,
        db: Session,
        lock_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Release an ethical lock."""
        
        try:
            # Get lock
            lock = db.exec(
                select(EthicalLock).where(
                    and_(
                        EthicalLock.id == lock_id,
                        EthicalLock.locked_by == user_id,
                        EthicalLock.status == LockStatus.ACTIVE
                    )
                )
            ).first()
            
            if not lock:
                return False
            
            # Release lock
            lock.status = LockStatus.RELEASED
            lock.released_at = datetime.utcnow()
            lock.updated_at = datetime.utcnow()
            
            # Update metadata
            if not lock.lock_meta:
                lock.lock_meta = {}
            lock.lock_meta.update({
                "released_reason": reason,
                "released_at": datetime.utcnow().isoformat()
            })
            
            db.add(lock)
            db.commit()
            
            logger.info(f"Lock released: {lock.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error releasing lock: {str(e)}")
            return False
    
    async def extend_lock(
        self,
        db: Session,
        lock_id: uuid.UUID,
        user_id: uuid.UUID,
        extend_minutes: int = 15
    ) -> Tuple[bool, Optional[str]]:
        """Extend lock expiry time."""
        
        try:
            # Get lock
            lock = db.exec(
                select(EthicalLock).where(
                    and_(
                        EthicalLock.id == lock_id,
                        EthicalLock.locked_by == user_id,
                        EthicalLock.status == LockStatus.ACTIVE
                    )
                )
            ).first()
            
            if not lock:
                return False, "Lock not found or not owned by user"
            
            # Check if lock is expired
            if EthicalLockManager.is_lock_expired(lock.lock_expires_at):
                lock.status = LockStatus.EXPIRED
                db.add(lock)
                db.commit()
                return False, "Lock has expired"
            
            # Extend lock
            new_expires_at = datetime.utcnow() + timedelta(minutes=extend_minutes)
            lock.lock_expires_at = new_expires_at
            lock.heartbeat_at = datetime.utcnow()
            lock.updated_at = datetime.utcnow()
            
            db.add(lock)
            db.commit()
            
            logger.info(f"Lock extended: {lock.id} until {new_expires_at}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error extending lock: {str(e)}")
            return False, str(e)
    
    async def force_unlock(
        self,
        db: Session,
        lock_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        reason: str
    ) -> Tuple[bool, Optional[str]]:
        """Force unlock a resource (admin only)."""
        
        try:
            # Get lock
            lock = db.exec(
                select(EthicalLock).where(
                    and_(
                        EthicalLock.id == lock_id,
                        EthicalLock.status == LockStatus.ACTIVE
                    )
                )
            ).first()
            
            if not lock:
                return False, "Lock not found"
            
            # Force unlock
            lock.status = LockStatus.FORCE_UNLOCKED
            lock.force_unlocked_by = admin_user_id
            lock.force_unlocked_at = datetime.utcnow()
            lock.force_unlock_reason = reason
            lock.updated_at = datetime.utcnow()
            
            # Update metadata
            if not lock.lock_meta:
                lock.lock_meta = {}
            lock.lock_meta.update({
                "force_unlocked_by": str(admin_user_id),
                "force_unlock_reason": reason,
                "force_unlocked_at": datetime.utcnow().isoformat()
            })
            
            db.add(lock)
            db.commit()
            
            logger.info(f"Lock force unlocked: {lock.id} by admin {admin_user_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error force unlocking: {str(e)}")
            return False, str(e)
    
    async def cleanup_expired_locks(self, db: Session) -> int:
        """Clean up expired locks."""
        
        try:
            # Find expired locks
            expired_locks = db.exec(
                select(EthicalLock).where(
                    and_(
                        EthicalLock.status == LockStatus.ACTIVE,
                        EthicalLock.lock_expires_at <= datetime.utcnow()
                    )
                )
            ).all()
            
            count = 0
            for lock in expired_locks:
                lock.status = LockStatus.EXPIRED
                lock.updated_at = datetime.utcnow()
                db.add(lock)
                count += 1
            
            db.commit()
            
            if count > 0:
                logger.info(f"Cleaned up {count} expired locks")
            
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired locks: {str(e)}")
            return 0
    
    async def get_lock_statistics(self, db: Session, clinic_id: uuid.UUID) -> Dict[str, Any]:
        """Get lock usage statistics."""
        
        try:
            # Get active locks
            active_locks = db.exec(
                select(EthicalLock).where(
                    and_(
                        EthicalLock.clinic_id == clinic_id,
                        EthicalLock.status == LockStatus.ACTIVE,
                        EthicalLock.lock_expires_at > datetime.utcnow()
                    )
                )
            ).all()
            
            # Get expired locks
            expired_locks = db.exec(
                select(EthicalLock).where(
                    and_(
                        EthicalLock.clinic_id == clinic_id,
                        EthicalLock.status == LockStatus.EXPIRED
                    )
                )
            ).all()
            
            # Get force unlocked locks
            force_unlocked_locks = db.exec(
                select(EthicalLock).where(
                    and_(
                        EthicalLock.clinic_id == clinic_id,
                        EthicalLock.status == LockStatus.FORCE_UNLOCKED
                    )
                )
            ).all()
            
            # Calculate average lock duration
            all_locks = db.exec(
                select(EthicalLock).where(
                    and_(
                        EthicalLock.clinic_id == clinic_id,
                        EthicalLock.status.in_([
                            LockStatus.RELEASED,
                            LockStatus.EXPIRED,
                            LockStatus.FORCE_UNLOCKED
                        ])
                    )
                )
            ).all()
            
            avg_duration = 0
            if all_locks:
                durations = []
                for lock in all_locks:
                    if lock.released_at:
                        duration = (lock.released_at - lock.locked_at).total_seconds() / 60
                    elif lock.force_unlocked_at:
                        duration = (lock.force_unlocked_at - lock.locked_at).total_seconds() / 60
                    else:
                        duration = (lock.lock_expires_at - lock.locked_at).total_seconds() / 60
                    durations.append(duration)
                
                avg_duration = sum(durations) / len(durations)
            
            # Get most locked resources
            resource_counts = {}
            for lock in active_locks:
                key = f"{lock.resource_type}:{lock.resource_id}"
                resource_counts[key] = resource_counts.get(key, 0) + 1
            
            most_locked = sorted(resource_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                "active_locks": len(active_locks),
                "expired_locks": len(expired_locks),
                "force_unlocked_locks": len(force_unlocked_locks),
                "average_lock_duration_minutes": round(avg_duration, 2),
                "most_locked_resources": most_locked
            }
            
        except Exception as e:
            logger.error(f"Error getting lock statistics: {str(e)}")
            return {}

class CollisionDetectionService:
    """Service for collision detection and prevention."""
    
    def __init__(self):
        self.cid_conflict_severity_map = {
            "high": ["F32", "F31", "F33"],  # Mental health conflicts
            "medium": ["I10", "I11", "I12"],  # Cardiovascular conflicts
            "low": ["E11", "E10", "E12"]  # Diabetes conflicts
        }
    
    async def detect_duplicate_submission(
        self,
        db: Session,
        clinic_id: uuid.UUID,
        invoice_id: uuid.UUID,
        procedure_code: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Detect duplicate SADT/TUSS submissions."""
        
        try:
            # Check for existing job
            existing_job = db.exec(
                select("TISSJob").where(
                    and_(
                        "TISSJob.clinic_id == clinic_id",
                        "TISSJob.invoice_id == invoice_id",
                        "TISSJob.procedure_code == procedure_code",
                        "TISSJob.status != 'rejected'"
                    )
                )
            ).first()
            
            if existing_job:
                return True, {
                    "existing_job_id": str(existing_job.id),
                    "existing_job_status": existing_job.status,
                    "submitted_at": existing_job.created_at.isoformat(),
                    "conflict_type": "duplicate_submission"
                }
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error detecting duplicate submission: {str(e)}")
            return False, None
    
    async def detect_cid_conflict(
        self,
        db: Session,
        clinic_id: uuid.UUID,
        patient_id: uuid.UUID,
        new_cid_code: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Detect CID code conflicts."""
        
        try:
            # Get recent diagnoses for patient
            recent_diagnoses = db.exec(
                select("MedicalRecord").where(
                    and_(
                        "MedicalRecord.patient_id == patient_id",
                        "MedicalRecord.clinic_id == clinic_id",
                        "MedicalRecord.created_at >= datetime.utcnow() - timedelta(days=30)"
                    )
                )
            ).all()
            
            # Check for conflicts
            conflict = CollisionDetector.detect_cid_conflict(
                patient_id, new_cid_code, [d.dict() for d in recent_diagnoses]
            )
            
            if conflict:
                return True, conflict
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error detecting CID conflict: {str(e)}")
            return False, None
    
    async def detect_exam_conflict(
        self,
        db: Session,
        clinic_id: uuid.UUID,
        patient_id: uuid.UUID,
        new_exam_code: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Detect exam conflicts."""
        
        try:
            # Get recent exams for patient
            recent_exams = db.exec(
                select("Exam").where(
                    and_(
                        "Exam.patient_id == patient_id",
                        "Exam.clinic_id == clinic_id",
                        "Exam.exam_date >= datetime.utcnow() - timedelta(days=7)"
                    )
                )
            ).all()
            
            # Check for conflicts
            conflict = CollisionDetector.detect_exam_conflict(
                patient_id, new_exam_code, [e.dict() for e in recent_exams]
            )
            
            if conflict:
                return True, conflict
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error detecting exam conflict: {str(e)}")
            return False, None
    
    async def detect_medication_conflict(
        self,
        db: Session,
        clinic_id: uuid.UUID,
        patient_id: uuid.UUID,
        new_medication: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Detect medication conflicts."""
        
        try:
            # Get current medications for patient
            current_medications = db.exec(
                select("Prescription").where(
                    and_(
                        "Prescription.patient_id == patient_id",
                        "Prescription.clinic_id == clinic_id",
                        "Prescription.status == 'active'"
                    )
                )
            ).all()
            
            # Check for conflicts
            conflict = CollisionDetector.detect_medication_conflict(
                patient_id, new_medication, [m.dict() for m in current_medications]
            )
            
            if conflict:
                return True, conflict
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error detecting medication conflict: {str(e)}")
            return False, None
    
    async def create_collision_record(
        self,
        db: Session,
        clinic_id: uuid.UUID,
        collision_type: CollisionType,
        resource_id: uuid.UUID,
        resource_type: str,
        detection_meta: Dict[str, Any],
        conflicting_resource_id: Optional[uuid.UUID] = None,
        conflicting_resource_type: Optional[str] = None
    ) -> CollisionDetection:
        """Create a collision detection record."""
        
        try:
            collision = CollisionDetection(
                clinic_id=clinic_id,
                collision_type=collision_type,
                resource_id=resource_id,
                resource_type=resource_type,
                conflicting_resource_id=conflicting_resource_id,
                conflicting_resource_type=conflicting_resource_type,
                detection_meta=detection_meta,
                severity=detection_meta.get("severity", "medium"),
                requires_manual_review=detection_meta.get("requires_manual_review", False)
            )
            
            db.add(collision)
            db.commit()
            db.refresh(collision)
            
            logger.info(f"Collision detection record created: {collision.id}")
            return collision
            
        except Exception as e:
            logger.error(f"Error creating collision record: {str(e)}")
            raise
    
    async def resolve_collision(
        self,
        db: Session,
        collision_id: uuid.UUID,
        resolved_by: uuid.UUID,
        resolution_notes: str
    ) -> bool:
        """Resolve a collision detection."""
        
        try:
            collision = db.exec(
                select(CollisionDetection).where(
                    CollisionDetection.id == collision_id
                )
            ).first()
            
            if not collision:
                return False
            
            collision.status = "resolved"
            collision.resolved_by = resolved_by
            collision.resolved_at = datetime.utcnow()
            collision.resolution_notes = resolution_notes
            collision.updated_at = datetime.utcnow()
            
            db.add(collision)
            db.commit()
            
            logger.info(f"Collision resolved: {collision_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resolving collision: {str(e)}")
            return False
    
    async def get_collision_statistics(self, db: Session, clinic_id: uuid.UUID) -> Dict[str, Any]:
        """Get collision detection statistics."""
        
        try:
            # Get all collisions for clinic
            collisions = db.exec(
                select(CollisionDetection).where(
                    CollisionDetection.clinic_id == clinic_id
                )
            ).all()
            
            # Calculate statistics
            total_collisions = len(collisions)
            resolved_collisions = len([c for c in collisions if c.status == "resolved"])
            pending_review = len([c for c in collisions if c.requires_manual_review and c.status == "detected"])
            
            # Collision type distribution
            type_distribution = {}
            for collision in collisions:
                collision_type = collision.collision_type.value
                type_distribution[collision_type] = type_distribution.get(collision_type, 0) + 1
            
            # Severity distribution
            severity_distribution = {}
            for collision in collisions:
                severity = collision.severity
                severity_distribution[severity] = severity_distribution.get(severity, 0) + 1
            
            return {
                "total_collisions": total_collisions,
                "resolved_collisions": resolved_collisions,
                "pending_review": pending_review,
                "resolution_rate": (resolved_collisions / total_collisions * 100) if total_collisions > 0 else 0,
                "type_distribution": type_distribution,
                "severity_distribution": severity_distribution
            }
            
        except Exception as e:
            logger.error(f"Error getting collision statistics: {str(e)}")
            return {}

class LockMonitoringService:
    """Service for monitoring lock usage and performance."""
    
    def __init__(self):
        self.monitoring_interval_minutes = 1
        self.alert_thresholds = {
            "max_concurrent_locks": 100,
            "max_lock_duration_minutes": 60,
            "max_expired_locks": 50
        }
    
    async def monitor_lock_usage(self, db: Session, clinic_id: uuid.UUID) -> Dict[str, Any]:
        """Monitor lock usage and generate alerts."""
        
        try:
            # Get current lock statistics
            lock_service = EthicalLockService()
            stats = await lock_service.get_lock_statistics(db, clinic_id)
            
            # Generate alerts
            alerts = []
            
            if stats["active_locks"] > self.alert_thresholds["max_concurrent_locks"]:
                alerts.append({
                    "type": "high_concurrent_locks",
                    "message": f"High number of concurrent locks: {stats['active_locks']}",
                    "severity": "warning"
                })
            
            if stats["average_lock_duration_minutes"] > self.alert_thresholds["max_lock_duration_minutes"]:
                alerts.append({
                    "type": "long_lock_duration",
                    "message": f"Average lock duration is high: {stats['average_lock_duration_minutes']} minutes",
                    "severity": "warning"
                })
            
            if stats["expired_locks"] > self.alert_thresholds["max_expired_locks"]:
                alerts.append({
                    "type": "many_expired_locks",
                    "message": f"Many expired locks need cleanup: {stats['expired_locks']}",
                    "severity": "info"
                })
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "clinic_id": str(clinic_id),
                "statistics": stats,
                "alerts": alerts,
                "status": "healthy" if not alerts else "warning"
            }
            
        except Exception as e:
            logger.error(f"Error monitoring lock usage: {str(e)}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "clinic_id": str(clinic_id),
                "error": str(e),
                "status": "error"
            }
    
    async def generate_lock_report(self, db: Session, clinic_id: uuid.UUID) -> Dict[str, Any]:
        """Generate comprehensive lock usage report."""
        
        try:
            # Get lock statistics
            lock_service = EthicalLockService()
            lock_stats = await lock_service.get_lock_statistics(db, clinic_id)
            
            # Get collision statistics
            collision_service = CollisionDetectionService()
            collision_stats = await collision_service.get_collision_statistics(db, clinic_id)
            
            # Generate recommendations
            recommendations = []
            
            if lock_stats["average_lock_duration_minutes"] > 30:
                recommendations.append("Consider reducing lock TTL to improve resource availability")
            
            if collision_stats["resolution_rate"] < 80:
                recommendations.append("Improve collision resolution process to increase resolution rate")
            
            if lock_stats["force_unlocked_locks"] > 10:
                recommendations.append("Review lock usage patterns to reduce force unlocks")
            
            return {
                "report_timestamp": datetime.utcnow().isoformat(),
                "clinic_id": str(clinic_id),
                "lock_statistics": lock_stats,
                "collision_statistics": collision_stats,
                "recommendations": recommendations,
                "overall_status": "healthy"
            }
            
        except Exception as e:
            logger.error(f"Error generating lock report: {str(e)}")
            return {
                "report_timestamp": datetime.utcnow().isoformat(),
                "clinic_id": str(clinic_id),
                "error": str(e),
                "overall_status": "error"
            }
