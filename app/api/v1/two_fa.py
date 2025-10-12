"""
Two-Factor Authentication API Endpoints
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.auth import AuthDependencies
from app.models import User
from app.models.two_fa import (
    TwoFASetupRequest, TwoFASetupResponse,
    TwoFAVerifyRequest, TwoFAVerifyResponse,
    TwoFADisableRequest, TwoFAStatusResponse
)
from app.services.two_fa_service import two_fa_service
from app.core.security import security

router = APIRouter(prefix="/two-fa", tags=["Two-Factor Authentication"])


@router.post("/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    request: Request,
    current_user: User = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Setup 2FA for current user.
    
    Returns QR code and backup codes.
    User must verify code to enable 2FA.
    """
    try:
        # Setup 2FA
        secret, qr_code_data, backup_codes = await two_fa_service.setup_2fa(
            db, current_user.id, current_user.email
        )
        
        return TwoFASetupResponse(
            secret=secret,
            qr_code_data=qr_code_data,
            backup_codes=backup_codes
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to setup 2FA: {str(e)}"
        )


@router.post("/verify", response_model=TwoFAVerifyResponse)
async def verify_2fa(
    verify_request: TwoFAVerifyRequest,
    current_user: User = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Verify 2FA code and enable 2FA.
    
    Must be called after setup to activate 2FA.
    """
    try:
        success = await two_fa_service.verify_and_enable_2fa(
            db, current_user.id, verify_request.code
        )
        
        if success:
            return TwoFAVerifyResponse(
                verified=True,
                message="2FA enabled successfully"
            )
        else:
            return TwoFAVerifyResponse(
                verified=False,
                message="Invalid code or 2FA locked. Try again or use backup code."
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify 2FA: {str(e)}"
        )


@router.post("/disable")
async def disable_2fa(
    disable_request: TwoFADisableRequest,
    current_user: User = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Disable 2FA for current user.
    
    Requires password and current 2FA code for security.
    """
    try:
        # Verify password
        if not security.verify_password(disable_request.password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password"
            )
        
        # Verify 2FA code
        code_valid = await two_fa_service.verify_2fa_for_login(
            db, current_user.id, disable_request.code
        )
        
        if not code_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code"
            )
        
        # Disable 2FA
        success = await two_fa_service.disable_2fa(db, current_user.id)
        
        if success:
            return {"message": "2FA disabled successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to disable 2FA"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable 2FA: {str(e)}"
        )


@router.get("/status", response_model=TwoFAStatusResponse)
async def get_2fa_status(
    current_user: User = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get 2FA status for current user."""
    try:
        from app.models.two_fa import TwoFASecret
        from sqlalchemy import select
        
        result = await db.execute(
            select(TwoFASecret).where(TwoFASecret.user_id == current_user.id)
        )
        two_fa = result.scalar_one_or_none()
        
        if two_fa:
            return TwoFAStatusResponse(
                enabled=two_fa.status == "enabled",
                status=two_fa.status,
                enabled_at=two_fa.enabled_at,
                last_used_at=two_fa.last_used_at
            )
        else:
            return TwoFAStatusResponse(
                enabled=False,
                status="not_setup",
                enabled_at=None,
                last_used_at=None
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get 2FA status: {str(e)}"
        )


@router.post("/regenerate-backup-codes")
async def regenerate_backup_codes(
    current_user: User = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Regenerate backup codes for user with 2FA enabled.
    
    Old backup codes will be invalidated.
    """
    try:
        from app.models.two_fa import TwoFASecret, TwoFAStatus
        from sqlalchemy import select
        
        # Check if user has 2FA enabled
        result = await db.execute(
            select(TwoFASecret).where(
                TwoFASecret.user_id == current_user.id,
                TwoFASecret.status == TwoFAStatus.ENABLED
            )
        )
        two_fa = result.scalar_one_or_none()
        
        if not two_fa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is not enabled"
            )
        
        # Generate new backup codes
        new_backup_codes = two_fa_service.generate_backup_codes()
        encrypted_codes = two_fa_service.encrypt_backup_codes(new_backup_codes)
        
        # Update record
        two_fa.backup_codes_encrypted = encrypted_codes
        await db.commit()
        
        return {
            "message": "Backup codes regenerated successfully",
            "backup_codes": new_backup_codes
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate backup codes: {str(e)}"
        )

