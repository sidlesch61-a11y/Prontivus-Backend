"""
Clinics API endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_current_clinic, require_admin, AuthDependencies
from app.db.session import get_db_session
from app.models import Clinic, AuditLog
from app.schemas import ClinicResponse, ClinicUpdate

router = APIRouter()


@router.get("/", response_model=List[ClinicResponse])
async def list_clinics(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List all clinics accessible to the current user."""
    # For now, return the user's clinic
    # In multi-clinic setups, this could return multiple clinics
    clinic = await AuthDependencies._get_current_clinic_impl(current_user, db)
    return [ClinicResponse.from_orm(clinic)]


@router.get("/{clinic_id}", response_model=ClinicResponse)
async def get_clinic(
    clinic_id: str,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get clinic information."""
    # Verify user has access to this clinic
    if str(current_user.clinic_id) != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    clinic = await AuthDependencies._get_current_clinic_impl(current_user, db)
    return ClinicResponse.from_orm(clinic)


@router.patch("/{clinic_id}", response_model=ClinicResponse)
async def update_clinic(
    clinic_id: str,
    update_data: ClinicUpdate,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Update clinic information."""
    # Verify user has access to this clinic
    if str(current_user.clinic_id) != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    clinic = await AuthDependencies._get_current_clinic_impl(current_user, db)
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(clinic, field, value)
    
    await db.commit()
    await db.refresh(clinic)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=clinic.id,
        user_id=current_user.id,
        action="clinic_updated",
        entity="clinic",
        entity_id=clinic.id,
        details={"updated_fields": list(update_dict.keys())}
    )
    db.add(audit_log)
    await db.commit()
    
    return ClinicResponse.from_orm(clinic)
