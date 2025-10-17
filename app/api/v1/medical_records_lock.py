"""
Medical Record Locking API - prevents modifications after finalization.
Integrates with the ethical_locks system for compliance.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.db.session import get_db_session
from app.core.auth import AuthDependencies, require_admin
from pydantic import BaseModel

router = APIRouter(prefix="/medical_records-lock", tags=["Medical Records - Locking"])


class LockRecordRequest(BaseModel):
    reason: str | None = "Record finalized by doctor"


class LockRecordResponse(BaseModel):
    success: bool
    message: str
    locked_at: datetime
    locked_by: str


@router.post("/{record_id}/lock", response_model=LockRecordResponse)
async def lock_medical_record(
    record_id: str,
    request: LockRecordRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(AuthDependencies.get_current_user),
):
    """
    Lock (finalize) a medical record to prevent further modifications.
    
    Once locked:
    - Record cannot be edited or deleted
    - Lock is logged in audit trail
    - Ethical lock is created for compliance
    
    **Only doctors can lock records.**
    """
    from app.models.database import MedicalRecord
    from app.models.ethical_locks import EthicalLock, LockType, LockStatus
    from datetime import timedelta
    
    # Check if user is a doctor
    user_role = getattr(current_user, "role", "").lower()
    if user_role not in ["doctor", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors can lock medical records"
        )
    
    # Get the record
    stmt = select(MedicalRecord).where(MedicalRecord.id == uuid.UUID(record_id))
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")
    
    # Check if already locked
    existing_lock_stmt = select(EthicalLock).where(
        EthicalLock.resource_id == record.id,
        EthicalLock.resource_type == "medical_record",
        EthicalLock.status == LockStatus.ACTIVE
    )
    existing_lock_result = await db.execute(existing_lock_stmt)
    if existing_lock_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Record is already locked")
    
    # Lock the record
    try:
        # Create ethical lock entry with correct field names
        ethical_lock = EthicalLock(
            id=uuid.uuid4(),
            clinic_id=record.clinic_id,
            lock_type=LockType.RECORD_FINALIZATION,  # Use proper enum
            resource_id=record.id,  # Correct field name
            resource_type="medical_record",  # Correct field name
            locked_by=current_user.id,
            locked_at=datetime.now(),
            lock_expires_at=datetime.now() + timedelta(days=36500),  # ~100 years (permanent)
            status=LockStatus.ACTIVE,
            reason=request.reason or "Record finalized by doctor",
        )
        
        db.add(ethical_lock)
        await db.commit()
        await db.refresh(ethical_lock)
        
        return LockRecordResponse(
            success=True,
            message="Medical record locked successfully",
            locked_at=ethical_lock.locked_at,
            locked_by=current_user.name
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to lock record: {str(e)}")


@router.post("/{record_id}/unlock", response_model=LockRecordResponse)
async def unlock_medical_record(
    record_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_admin),
):
    """
    Unlock a medical record (admin only, for corrections).
    
    **WARNING:** Unlocking finalized records should be rare and audited.
    Only admins can unlock records.
    """
    from app.models.ethical_locks import EthicalLock, LockStatus
    
    # Find the ethical lock
    stmt = select(EthicalLock).where(
        EthicalLock.resource_id == uuid.UUID(record_id),  # Correct field name
        EthicalLock.resource_type == "medical_record"
    )
    result = await db.execute(stmt)
    lock = result.scalar_one_or_none()
    
    if not lock:
        raise HTTPException(status_code=404, detail="No lock found for this record")
    
    # Check if lock is permanent (expires > 10 years from now)
    if lock.lock_expires_at and (lock.lock_expires_at - datetime.now()).days > 3650:
        raise HTTPException(
            status_code=403,
            detail="This record cannot be unlocked (finalized records)"
        )
    
    # Update lock status to released
    lock.status = LockStatus.RELEASED
    lock.released_at = datetime.now()
    await db.commit()
    
    return LockRecordResponse(
        success=True,
        message="Medical record unlocked successfully",
        locked_at=lock.locked_at,
        locked_by=current_user.name
    )


@router.get("/{record_id}/lock-status")
async def check_lock_status(
    record_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(AuthDependencies.get_current_user),
):
    """Check if a medical record is locked."""
    from app.models.ethical_locks import EthicalLock, LockStatus
    
    stmt = select(EthicalLock).where(
        EthicalLock.resource_id == uuid.UUID(record_id),  # Correct field name
        EthicalLock.resource_type == "medical_record",
        EthicalLock.status == LockStatus.ACTIVE  # Only check active locks
    )
    result = await db.execute(stmt)
    lock = result.scalar_one_or_none()
    
    if not lock:
        return {
            "is_locked": False,
            "can_edit": True,
            "message": "Record is unlocked and can be edited"
        }
    
    # Check if lock is permanent
    can_unlock = lock.lock_expires_at and (lock.lock_expires_at - datetime.now()).days <= 3650
    
    return {
        "is_locked": True,
        "can_edit": False,
        "locked_at": lock.locked_at.isoformat(),
        "locked_by": str(lock.locked_by),
        "reason": lock.reason or "Record locked",
        "can_unlock": can_unlock,
        "message": "Record is locked and cannot be edited"
    }

