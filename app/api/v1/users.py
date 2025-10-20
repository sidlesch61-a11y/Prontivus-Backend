"""
Users API endpoints.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user, get_current_user_response, require_admin, require_users_read, require_users_write
from app.db.session import get_db_session
from app.models import User, AuditLog
from app.schemas import UserResponse, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user_response)
):
    """Get current user information."""
    return current_user


@router.get("/list", response_model=Dict[str, Any])
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List all users in the current clinic."""
    # Get all users from the same clinic
    query = select(User).where(User.clinic_id == current_user.clinic_id).order_by(User.name)
    
    # Get total count
    count_query = select(User).where(User.clinic_id == current_user.clinic_id)
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "items": [UserResponse.model_validate(user) for user in users],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user = Depends(require_users_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Get user by ID."""
    # Verify user belongs to same clinic
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.clinic_id == current_user.clinic_id
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    current_user = Depends(require_users_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Update user information."""
    # Get user
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.clinic_id == current_user.clinic_id
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=user.clinic_id,
        user_id=current_user.id,
        action="user_updated",
        entity="user",
        entity_id=user.id,
        details={"updated_fields": list(update_dict.keys())}
    )
    db.add(audit_log)
    await db.commit()
    
    return UserResponse.model_validate(user)
