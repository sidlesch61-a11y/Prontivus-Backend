"""
API endpoints for ethical locks and anti-collision mechanisms.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, and_, or_
from typing import List, Optional, Dict, Any
import uuid
import json
import logging
import asyncio
from datetime import datetime, timedelta

from ..models.ethical_locks import (
    EthicalLock, CollisionDetection, LockAuditLog,
    LockType, LockStatus, CollisionType,
    LockRequest, LockResponse, HeartbeatRequest, HeartbeatResponse,
    UnlockRequest, ForceUnlockRequest, CollisionDetectionResponse,
    DuplicateSubmissionResponse, EthicalLockManager, CollisionDetector
)
from ..core.auth import get_current_user, get_current_tenant, require_permission
from ..db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ethical_locks"])

@router.post("/acquire", response_model=LockResponse)
async def acquire_lock(
    request_data: LockRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Acquire an ethical lock for a resource."""
    
    try:
        # Calculate expiry time
        ttl_minutes = request_data.ttl_minutes or EthicalLockManager.get_default_ttl(request_data.lock_type)
        expires_at = EthicalLockManager.calculate_expiry_time(ttl_minutes)
        
        # Check for existing active lock
        existing_lock = db.exec(
            select(EthicalLock).where(
                and_(
                    EthicalLock.clinic_id == current_tenant.id,
                    EthicalLock.resource_id == request_data.resource_id,
                    EthicalLock.resource_type == request_data.resource_type,
                    EthicalLock.status == LockStatus.ACTIVE,
                    EthicalLock.lock_expires_at > datetime.utcnow()
                )
            )
        ).first()
        
        if existing_lock:
            # Check if same user can extend lock
            if EthicalLockManager.can_user_acquire_lock(current_user.id, existing_lock):
                # Extend existing lock
                existing_lock.lock_expires_at = expires_at
                existing_lock.heartbeat_at = datetime.utcnow()
                existing_lock.updated_at = datetime.utcnow()
                db.add(existing_lock)
                db.commit()
                db.refresh(existing_lock)
                
                # Log lock extension
                await log_lock_operation(
                    db, current_tenant.id, existing_lock.id, "extend",
                    current_user.id, "doctor", True, request
                )
                
                return LockResponse.from_orm(existing_lock)
            else:
                # Lock conflict - return 409 with lock info
                await log_lock_operation(
                    db, current_tenant.id, None, "acquire_conflict",
                    current_user.id, "doctor", False, request,
                    error_message=f"Resource locked by user {existing_lock.locked_by}"
                )
                
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": "Resource is currently locked by another user",
                        "locked_by": str(existing_lock.locked_by),
                        "locked_at": existing_lock.locked_at.isoformat(),
                        "expires_at": existing_lock.lock_expires_at.isoformat(),
                        "lock_id": str(existing_lock.id)
                    }
                )
        
        # Create new lock
        lock = EthicalLock(
            clinic_id=current_tenant.id,
            lock_type=request_data.lock_type,
            resource_id=request_data.resource_id,
            resource_type=request_data.resource_type,
            locked_by=current_user.id,
            locked_at=datetime.utcnow(),
            lock_expires_at=expires_at,
            status=LockStatus.ACTIVE,
            heartbeat_at=datetime.utcnow(),
            reason=request_data.reason,
            lock_meta={
                "acquired_via": "api",
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "ttl_minutes": ttl_minutes
            }
        )
        
        db.add(lock)
        db.commit()
        db.refresh(lock)
        
        # Log lock acquisition
        await log_lock_operation(
            db, current_tenant.id, lock.id, "acquire",
            current_user.id, "doctor", True, request
        )
        
        logger.info(f"Lock acquired: {lock.id} by user {current_user.id}")
        
        return LockResponse.from_orm(lock)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acquiring lock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acquire lock"
        )

@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat_lock(
    request_data: HeartbeatRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Extend lock expiry time (heartbeat)."""
    
    try:
        # Get lock
        lock = db.exec(
            select(EthicalLock).where(
                and_(
                    EthicalLock.id == request_data.lock_id,
                    EthicalLock.clinic_id == current_tenant.id,
                    EthicalLock.locked_by == current_user.id,
                    EthicalLock.status == LockStatus.ACTIVE
                )
            )
        ).first()
        
        if not lock:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lock not found or not owned by user"
            )
        
        # Check if lock is expired
        if EthicalLockManager.is_lock_expired(lock.lock_expires_at):
            lock.status = LockStatus.EXPIRED
            db.add(lock)
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Lock has expired"
            )
        
        # Extend lock
        new_expires_at = datetime.utcnow() + timedelta(minutes=request_data.extend_minutes)
        lock.lock_expires_at = new_expires_at
        lock.heartbeat_at = datetime.utcnow()
        lock.updated_at = datetime.utcnow()
        
        db.add(lock)
        db.commit()
        
        # Log heartbeat
        await log_lock_operation(
            db, current_tenant.id, lock.id, "heartbeat",
            current_user.id, "doctor", True, request
        )
        
        return HeartbeatResponse(
            lock_id=lock.id,
            new_expires_at=new_expires_at,
            status="extended",
            message="Lock successfully extended"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extending lock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extend lock"
        )

@router.post("/release")
async def release_lock(
    request_data: UnlockRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Release an ethical lock."""
    
    try:
        # Get lock
        lock = db.exec(
            select(EthicalLock).where(
                and_(
                    EthicalLock.id == request_data.lock_id,
                    EthicalLock.clinic_id == current_tenant.id,
                    EthicalLock.locked_by == current_user.id,
                    EthicalLock.status == LockStatus.ACTIVE
                )
            )
        ).first()
        
        if not lock:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lock not found or not owned by user"
            )
        
        # Release lock
        lock.status = LockStatus.RELEASED
        lock.released_at = datetime.utcnow()
        lock.updated_at = datetime.utcnow()
        
        # Update metadata
        if not lock.lock_meta:
            lock.lock_meta = {}
        lock.lock_meta.update({
            "released_reason": request_data.reason,
            "released_at": datetime.utcnow().isoformat()
        })
        
        db.add(lock)
        db.commit()
        
        # Log release
        await log_lock_operation(
            db, current_tenant.id, lock.id, "release",
            current_user.id, "doctor", True, request
        )
        
        return {"message": "Lock successfully released", "lock_id": str(lock.id)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error releasing lock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to release lock"
        )

@router.post("/force-unlock")
async def force_unlock(
    request_data: ForceUnlockRequest,
    request: Request,
    current_user = Depends(require_permission("admin")),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Force unlock a resource (admin only)."""
    
    try:
        # Get lock
        lock = db.exec(
            select(EthicalLock).where(
                and_(
                    EthicalLock.id == request_data.lock_id,
                    EthicalLock.clinic_id == current_tenant.id,
                    EthicalLock.status == LockStatus.ACTIVE
                )
            )
        ).first()
        
        if not lock:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lock not found"
            )
        
        # Force unlock
        lock.status = LockStatus.FORCE_UNLOCKED
        lock.force_unlocked_by = current_user.id
        lock.force_unlocked_at = datetime.utcnow()
        lock.force_unlock_reason = request_data.reason
        lock.updated_at = datetime.utcnow()
        
        # Update metadata
        if not lock.lock_meta:
            lock.lock_meta = {}
        lock.lock_meta.update({
            "force_unlocked_by": str(current_user.id),
            "force_unlock_reason": request_data.reason,
            "force_unlocked_at": datetime.utcnow().isoformat()
        })
        
        db.add(lock)
        db.commit()
        
        # Log force unlock
        await log_lock_operation(
            db, current_tenant.id, lock.id, "force_unlock",
            current_user.id, "admin", True, request
        )
        
        # TODO: Notify original user if requested
        if request_data.notify_user:
            # This would typically send a notification
            logger.info(f"Force unlock notification sent to user {lock.locked_by}")
        
        return {
            "message": "Lock force unlocked successfully",
            "lock_id": str(lock.id),
            "original_locked_by": str(lock.locked_by)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error force unlocking: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to force unlock"
        )

@router.get("/active", response_model=List[LockResponse])
async def list_active_locks(
    resource_type: Optional[str] = None,
    lock_type: Optional[LockType] = None,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """List active locks for the clinic."""
    
    statement = select(EthicalLock).where(
        and_(
            EthicalLock.clinic_id == current_tenant.id,
            EthicalLock.status == LockStatus.ACTIVE,
            EthicalLock.lock_expires_at > datetime.utcnow()
        )
    )
    
    if resource_type:
        statement = statement.where(EthicalLock.resource_type == resource_type)
    
    if lock_type:
        statement = statement.where(EthicalLock.lock_type == lock_type)
    
    statement = statement.order_by(EthicalLock.locked_at.desc())
    
    locks = db.exec(statement).all()
    
    return [LockResponse.from_orm(lock) for lock in locks]

@router.get("/{lock_id}", response_model=LockResponse)
async def get_lock(
    lock_id: uuid.UUID,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get lock details by ID."""
    
    lock = db.exec(
        select(EthicalLock).where(
            and_(
                EthicalLock.id == lock_id,
                EthicalLock.clinic_id == current_tenant.id
            )
        )
    ).first()
    
    if not lock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lock not found"
        )
    
    return LockResponse.from_orm(lock)

@router.get("/{lock_id}/audit", response_model=List[Dict[str, Any]])
async def get_lock_audit_logs(
    lock_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get audit logs for a specific lock."""
    
    # Verify lock exists and belongs to clinic
    lock = db.exec(
        select(EthicalLock).where(
            and_(
                EthicalLock.id == lock_id,
                EthicalLock.clinic_id == current_tenant.id
            )
        )
    ).first()
    
    if not lock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lock not found"
        )
    
    # Get audit logs
    logs = db.exec(
        select(LockAuditLog).where(
            LockAuditLog.lock_id == lock_id
        ).order_by(LockAuditLog.created_at.desc()).offset(offset).limit(limit)
    ).all()
    
    result = []
    for log in logs:
        log_dict = log.dict()
        log_dict["operation_meta"] = json.loads(log_dict["operation_meta"]) if log_dict["operation_meta"] else None
        result.append(log_dict)
    
    return result

# SADT/TUSS Duplicate Prevention
@router.post("/check-duplicate-submission")
async def check_duplicate_submission(
    request_data: dict,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Check for duplicate SADT/TUSS submissions."""
    
    try:
        # Extract required fields
        invoice_id = request_data.get("invoice_id")
        procedure_code = request_data.get("procedure_code")
        submission_type = request_data.get("submission_type", "SADT")
        
        if not invoice_id or not procedure_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invoice_id and procedure_code are required"
            )
        
        # Check for existing job
        existing_job = db.exec(
            select("TISSJob").where(
                and_(
                    "TISSJob.clinic_id == current_tenant.id",
                    "TISSJob.invoice_id == invoice_id",
                    "TISSJob.procedure_code == procedure_code",
                    "TISSJob.status != 'rejected'"
                )
            )
        ).first()
        
        if existing_job:
            # Create audit entry
            audit_log = LockAuditLog(
                clinic_id=current_tenant.id,
                operation="duplicate_submission_detected",
                user_id=current_user.id,
                user_role="doctor",
                operation_meta={
                    "invoice_id": str(invoice_id),
                    "procedure_code": procedure_code,
                    "submission_type": submission_type,
                    "existing_job_id": str(existing_job.id),
                    "existing_job_status": existing_job.status
                },
                success=False,
                error_message="Duplicate submission detected"
            )
            db.add(audit_log)
            db.commit()
            
            return DuplicateSubmissionResponse(
                conflict=True,
                existing_job_id=existing_job.id,
                existing_job_status=existing_job.status,
                message=f"Duplicate {submission_type} submission detected",
                audit_log_id=audit_log.id
            )
        
        return DuplicateSubmissionResponse(
            conflict=False,
            message="No duplicate submission detected"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking duplicate submission: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check duplicate submission"
        )

# CID Collision Detection
@router.post("/check-cid-collision")
async def check_cid_collision(
    request_data: dict,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Check for CID code conflicts."""
    
    try:
        patient_id = request_data.get("patient_id")
        new_cid_code = request_data.get("cid_code")
        
        if not patient_id or not new_cid_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id and cid_code are required"
            )
        
        # Get recent diagnoses for patient
        recent_diagnoses = db.exec(
            select("MedicalRecord").where(
                and_(
                    "MedicalRecord.patient_id == patient_id",
                    "MedicalRecord.clinic_id == current_tenant.id",
                    "MedicalRecord.created_at >= datetime.utcnow() - timedelta(days=30)"
                )
            )
        ).all()
        
        # Check for conflicts
        conflict = CollisionDetector.detect_cid_conflict(
            patient_id, new_cid_code, [d.dict() for d in recent_diagnoses]
        )
        
        if conflict:
            # Create collision detection record
            collision = CollisionDetection(
                clinic_id=current_tenant.id,
                collision_type=CollisionType.CID_CONFLICT,
                resource_id=patient_id,
                resource_type="patient_diagnosis",
                detection_meta=conflict,
                severity=conflict["severity"],
                requires_manual_review=conflict["requires_manual_review"]
            )
            db.add(collision)
            db.commit()
            db.refresh(collision)
            
            return CollisionDetectionResponse.from_orm(collision)
        
        return {"conflict": False, "message": "No CID conflicts detected"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking CID collision: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check CID collision"
        )

# Utility function for logging lock operations
async def log_lock_operation(
    db: Session,
    clinic_id: uuid.UUID,
    lock_id: Optional[uuid.UUID],
    operation: str,
    user_id: uuid.UUID,
    user_role: str,
    success: bool,
    request: Request,
    error_message: Optional[str] = None,
    operation_meta: Optional[Dict[str, Any]] = None
):
    """Log lock operation for audit trail."""
    
    try:
        log = LockAuditLog(
            clinic_id=clinic_id,
            lock_id=lock_id,
            operation=operation,
            user_id=user_id,
            user_role=user_role,
            operation_meta=operation_meta or {},
            success=success,
            error_message=error_message,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        db.add(log)
        db.commit()
        
    except Exception as e:
        logger.error(f"Error logging lock operation: {str(e)}")
        # Don't raise exception as this is just logging
