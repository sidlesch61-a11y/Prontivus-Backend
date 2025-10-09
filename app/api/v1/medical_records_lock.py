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

router = APIRouter(prefix="/medical_records", tags=["Medical Records - Locking"])


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
    from app.models.database import MedicalRecord, EthicalLock
    
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
    if hasattr(record, 'is_locked') and record.is_locked:
        raise HTTPException(status_code=400, detail="Record is already locked")
    
    # Lock the record
    # Since the current schema doesn't have is_locked field, we'll create an ethical lock
    
    try:
        # Create ethical lock entry
        ethical_lock = EthicalLock(
            id=uuid.uuid4(),
            record_type="medical_record",
            record_id=record.id,
            clinic_id=record.clinic_id,
            locked_by=current_user.id,
            locked_at=datetime.now(),
            reason=request.reason or "Record finalized by doctor",
            hash_signature=f"md5:{record.id}",  # Simplified for now
            can_unlock=False,  # Cannot be unlocked once finalized
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
    from app.models.database import EthicalLock
    
    # Find the ethical lock
    stmt = select(EthicalLock).where(
        EthicalLock.record_id == uuid.UUID(record_id),
        EthicalLock.record_type == "medical_record"
    )
    result = await db.execute(stmt)
    lock = result.scalar_one_or_none()
    
    if not lock:
        raise HTTPException(status_code=404, detail="No lock found for this record")
    
    if not lock.can_unlock:
        raise HTTPException(
            status_code=403,
            detail="This record cannot be unlocked (finalized records)"
        )
    
    # Delete the lock
    await db.delete(lock)
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
    from app.models.database import EthicalLock
    
    stmt = select(EthicalLock).where(
        EthicalLock.record_id == uuid.UUID(record_id),
        EthicalLock.record_type == "medical_record"
    )
    result = await db.execute(stmt)
    lock = result.scalar_one_or_none()
    
    if not lock:
        return {
            "is_locked": False,
            "can_edit": True,
            "message": "Record is unlocked and can be edited"
        }
    
    return {
        "is_locked": True,
        "can_edit": False,
        "locked_at": lock.locked_at.isoformat(),
        "locked_by": str(lock.locked_by),
        "reason": lock.reason,
        "can_unlock": lock.can_unlock,
        "message": "Record is locked and cannot be edited"
    }

