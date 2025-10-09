"""
Licenses API endpoints.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.auth import get_current_user, require_admin
from app.core.security import security
from app.db.session import get_db_session
from app.models import License, ActivationStatus, AuditLog
from app.schemas import LicenseCreate, LicenseActivateRequest, LicenseResponse

router = APIRouter()


@router.get("/", response_model=List[LicenseResponse])
async def list_licenses(
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """List all licenses for the clinic."""
    result = await db.execute(
        select(License).where(
            License.clinic_id == current_user.clinic_id
        ).order_by(License.created_at.desc())
    )
    licenses = result.scalars().all()
    
    return [LicenseResponse.from_orm(license) for license in licenses]


@router.post("/", response_model=LicenseResponse, status_code=status.HTTP_201_CREATED)
async def create_license(
    license_data: LicenseCreate,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new license."""
    # Create license
    license_obj = License(
        clinic_id=current_user.clinic_id,
        **license_data.dict()
    )
    
    # Sign license
    license_payload = {
        "license_id": str(license_obj.id),
        "tenant_id": str(license_obj.clinic_id),
        "plan": license_obj.plan,
        "end_at": license_obj.end_at.isoformat()
    }
    
    license_obj.signature = security.sign_license(license_payload)
    
    db.add(license_obj)
    await db.commit()
    await db.refresh(license_obj)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="license_created",
        entity="license",
        entity_id=license_obj.id,
        details={
            "plan": license_obj.plan,
            "modules": license_obj.modules,
            "users_limit": license_obj.users_limit,
            "end_at": license_obj.end_at.isoformat()
        }
    )
    db.add(audit_log)
    await db.commit()
    
    return LicenseResponse.from_orm(license_obj)


@router.get("/{license_id}", response_model=LicenseResponse)
async def get_license(
    license_id: str,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Get license by ID."""
    result = await db.execute(
        select(License).where(
            License.id == license_id,
            License.clinic_id == current_user.clinic_id
        )
    )
    license_obj = result.scalar_one_or_none()
    
    if not license_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found"
        )
    
    return LicenseResponse.from_orm(license_obj)


@router.post("/{license_id}/activate")
async def activate_license(
    license_id: str,
    activation_data: LicenseActivateRequest,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Activate license for instance."""
    # Get license
    result = await db.execute(
        select(License).where(
            License.id == license_id,
            License.clinic_id == current_user.clinic_id
        )
    )
    license_obj = result.scalar_one_or_none()
    
    if not license_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found"
        )
    
    if license_obj.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License is not active"
        )
    
    # Check if license is expired
    if license_obj.end_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License has expired"
        )
    
    # Check if already activated for this instance
    existing_activation = await db.execute(
        select(Activation).where(
            Activation.license_id == license_id,
            Activation.instance_id == activation_data.instance_id
        )
    )
    
    if existing_activation.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License already activated for this instance"
        )
    
    # Create activation
    activation = Activation(
        clinic_id=current_user.clinic_id,
        license_id=license_id,
        instance_id=activation_data.instance_id,
        device_info=activation_data.device_info,
        status="active"
    )
    db.add(activation)
    await db.commit()
    await db.refresh(activation)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="license_activated",
        entity="activation",
        entity_id=activation.id,
        details={
            "license_id": str(license_id),
            "instance_id": activation_data.instance_id,
            "device_info": activation_data.device_info
        }
    )
    db.add(audit_log)
    await db.commit()
    
    return {
        "message": "License activated successfully",
        "activation_id": str(activation.id),
        "offline_grace_hours": 72  # From settings
    }


@router.post("/{license_id}/suspend")
async def suspend_license(
    license_id: str,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Suspend license."""
    # Get license
    result = await db.execute(
        select(License).where(
            License.id == license_id,
            License.clinic_id == current_user.clinic_id
        )
    )
    license_obj = result.scalar_one_or_none()
    
    if not license_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found"
        )
    
    # Update license status
    license_obj.status = "suspended"
    await db.commit()
    
    # Suspend all activations
    activations_result = await db.execute(
        select(Activation).where(Activation.license_id == license_id)
    )
    activations = activations_result.scalars().all()
    
    for activation in activations:
        activation.status = "suspended"
    
    await db.commit()
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="license_suspended",
        entity="license",
        entity_id=license_obj.id,
        details={"previous_status": "active"}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "License suspended successfully"}


@router.post("/{license_id}/reactivate")
async def reactivate_license(
    license_id: str,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Reactivate license."""
    # Get license
    result = await db.execute(
        select(License).where(
            License.id == license_id,
            License.clinic_id == current_user.clinic_id
        )
    )
    license_obj = result.scalar_one_or_none()
    
    if not license_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found"
        )
    
    # Check if license is expired
    if license_obj.end_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License has expired"
        )
    
    # Update license status
    license_obj.status = "active"
    await db.commit()
    
    # Reactivate all activations
    activations_result = await db.execute(
        select(Activation).where(Activation.license_id == license_id)
    )
    activations = activations_result.scalars().all()
    
    for activation in activations:
        activation.status = "active"
    
    await db.commit()
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="license_reactivated",
        entity="license",
        entity_id=license_obj.id,
        details={"previous_status": "suspended"}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "License reactivated successfully"}
