"""
Enhanced Authentication with 2FA Support
To be integrated into existing auth.py
"""

from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User
from app.models.two_fa import TwoFASecret, TwoFAStatus, LoginAttempt
from app.services.two_fa_service import two_fa_service
from app.core.security import security
from datetime import datetime
import uuid


async def enhanced_login(
    email: str,
    password: str,
    two_fa_code: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
    db: AsyncSession
) -> dict:
    """
    Enhanced login with 2FA support.
    
    Returns token info or raises exception with 2FA requirement.
    """
    # Find user
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    
    # Log attempt
    attempt = LoginAttempt(
        user_id=user.id if user else None,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=False,
        failure_reason=None,
        attempted_at=datetime.utcnow()
    )
    
    if not user or not user.is_active:
        attempt.failure_reason = "user_not_found_or_inactive"
        db.add(attempt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    if not security.verify_password(password, user.password_hash):
        attempt.failure_reason = "invalid_password"
        db.add(attempt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if 2FA is enabled for this user
    result = await db.execute(
        select(TwoFASecret).where(
            TwoFASecret.user_id == user.id,
            TwoFASecret.status == TwoFAStatus.ENABLED
        )
    )
    two_fa_record = result.scalar_one_or_none()
    
    if two_fa_record:
        # 2FA is enabled - require code
        if not two_fa_code:
            attempt.failure_reason = "2fa_code_required"
            db.add(attempt)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="2FA code required",
                headers={"X-Require-2FA": "true"}
            )
        
        # Verify 2FA code
        code_valid = await two_fa_service.verify_2fa_for_login(
            db, user.id, two_fa_code
        )
        
        if not code_valid:
            attempt.failure_reason = "invalid_2fa_code"
            db.add(attempt)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code"
            )
    
    # Check if 2FA is REQUIRED for this role but not enabled
    from app.core.security_config import SecurityPolicy
    
    if SecurityPolicy.requires_2fa(user.role) and not two_fa_record:
        # Role requires 2FA but user hasn't set it up
        # Allow login but flag that 2FA setup is required
        attempt.success = True
        attempt.failure_reason = "2fa_setup_required"
        db.add(attempt)
        
        # Update last login
        user.last_login = datetime.utcnow()
        await db.commit()
        
        # Generate tokens
        access_token = security.create_access_token(
            data={"sub": str(user.id), "clinic_id": str(user.clinic_id), "twofa_verified": False}
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "clinic_id": str(user.clinic_id)
            },
            "require_2fa_setup": True,
            "message": "2FA is required for your role. Please set it up in Settings."
        }
    
    # Successful login
    attempt.success = True
    db.add(attempt)
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Generate tokens with 2FA verification status
    twofa_verified = two_fa_record is not None
    access_token = security.create_access_token(
        data={"sub": str(user.id), "clinic_id": str(user.clinic_id), "twofa_verified": twofa_verified}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "clinic_id": str(user.clinic_id),
            "two_fa_enabled": twofa_verified
        }
    }

