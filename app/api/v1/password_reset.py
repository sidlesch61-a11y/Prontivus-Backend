"""
Password Reset API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import uuid
import secrets

from app.db.session import get_db_session
from app.core.security import security
from app.core.auth import AuthDependencies
from app.models.database import User
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["Password Reset"])


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ForgotPasswordResponse(BaseModel):
    success: bool
    message: str


class ResetPasswordResponse(BaseModel):
    success: bool
    message: str


# In-memory token storage (in production, use Redis or database table)
reset_tokens = {}


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Request password reset.
    
    **Workflow:**
    1. Verify email exists
    2. Generate secure reset token
    3. Send email with reset link (background task)
    4. Token expires in 1 hour
    
    **Security:**
    - Always returns success (prevents email enumeration)
    - Token is single-use
    - Short expiration time
    """
    try:
        # Find user by email
        stmt = select(User).where(User.email == request.email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user and user.is_active:
            # Generate secure reset token
            reset_token = secrets.token_urlsafe(32)
            expiry = datetime.now() + timedelta(hours=1)
            
            # Store token (in production: use Redis or database)
            reset_tokens[reset_token] = {
                "user_id": str(user.id),
                "email": user.email,
                "expires_at": expiry,
                "used": False,
            }
            
            # Send email in background (placeholder)
            # background_tasks.add_task(send_reset_email, user.email, reset_token)
            
            # Log password reset request
            from app.models.database import AuditLog
            audit_log = AuditLog(
                clinic_id=user.clinic_id,
                user_id=user.id,
                action="password_reset_requested",
                entity="user",
                entity_id=user.id,
                details={"email": user.email}
            )
            db.add(audit_log)
            await db.commit()
        
        # Always return success (security best practice)
        return ForgotPasswordResponse(
            success=True,
            message="If the email exists, a password reset link has been sent."
        )
        
    except Exception as e:
        # Still return success to prevent enumeration
        return ForgotPasswordResponse(
            success=True,
            message="If the email exists, a password reset link has been sent."
        )


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Reset password using token.
    
    **Workflow:**
    1. Validate reset token
    2. Check expiration
    3. Update password
    4. Invalidate token
    5. Log password change
    """
    try:
        # Validate token exists
        if request.token not in reset_tokens:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        token_data = reset_tokens[request.token]
        
        # Check if already used
        if token_data["used"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has already been used"
            )
        
        # Check expiration
        if datetime.now() > token_data["expires_at"]:
            del reset_tokens[request.token]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired"
            )
        
        # Get user
        stmt = select(User).where(User.id == uuid.UUID(token_data["user_id"]))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Validate new password strength
        if len(request.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters"
            )
        
        # Update password
        user.password_hash = security.get_password_hash(request.new_password)
        user.updated_at = datetime.now()
        
        # Invalidate token
        token_data["used"] = True
        
        # Log password change
        from app.models.database import AuditLog
        audit_log = AuditLog(
            clinic_id=user.clinic_id,
            user_id=user.id,
            action="password_reset_completed",
            entity="user",
            entity_id=user.id,
            details={"method": "reset_token"}
        )
        db.add(audit_log)
        await db.commit()
        
        # Clean up used token
        del reset_tokens[request.token]
        
        return ResetPasswordResponse(
            success=True,
            message="Password reset successfully. You can now login with your new password."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset password: {str(e)}"
        )


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Change password for authenticated user.
    
    Requires current password verification.
    """
    # Verify old password
    if not security.verify_password(old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters"
        )
    
    # Update password
    current_user.password_hash = security.get_password_hash(new_password)
    current_user.updated_at = datetime.now()
    
    # Log password change
    from app.models.database import AuditLog
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="password_changed",
        entity="user",
        entity_id=current_user.id,
        details={"method": "authenticated_change"}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"success": True, "message": "Password changed successfully"}


# Utility function for email sending (placeholder)
async def send_reset_email(email: str, reset_token: str):
    """
    Send password reset email.
    
    In production, integrate with:
    - SendGrid
    - AWS SES
    - Mailgun
    - etc.
    """
    reset_link = f"https://prontivus.com/reset-password?token={reset_token}"
    
    # Email content
    subject = "Prontivus - Password Reset Request"
    body = f"""
    Hello,
    
    You requested a password reset for your Prontivus account.
    
    Click the link below to reset your password:
    {reset_link}
    
    This link will expire in 1 hour.
    
    If you didn't request this reset, please ignore this email.
    
    Best regards,
    Prontivus Team
    """
    
    # In production: Send actual email
    print(f"[EMAIL] To: {email}")
    print(f"[EMAIL] Subject: {subject}")
    print(f"[EMAIL] Reset Link: {reset_link}")

