"""
Authentication API endpoints.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import security
from app.core.config import settings
from app.core.auth import get_current_user, get_current_user_response
from app.db.session import get_db_session, get_db_transaction
from app.models import User, Clinic, AuditLog
from app.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    TwoFactorRequest, UserResponse, ErrorResponse
)

router = APIRouter()


@router.post("/register", response_model=Dict[str, str], status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db_transaction)
):
    """Register a new clinic and admin user."""
    try:
        # Create clinic using raw SQL to properly handle ENUM type
        from sqlalchemy import text
        
        clinic_id = uuid.uuid4()
        
        # Insert clinic with explicit ENUM cast
        await db.execute(
            text("""
                INSERT INTO clinics (id, name, cnpj_cpf, contact_email, contact_phone, status, settings, created_at, updated_at)
                VALUES (:id, :name, :cnpj_cpf, :contact_email, :contact_phone, CAST(:status AS clinicstatus), CAST(:settings AS jsonb), :created_at, :updated_at)
            """),
            {
                "id": str(clinic_id),
                "name": request.clinic.name,
                "cnpj_cpf": request.clinic.cnpj_cpf,
                "contact_email": request.clinic.contact_email,
                "contact_phone": request.clinic.contact_phone,
                "status": "active",
                "settings": "{}",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )
        
        # Create admin user
        user = User(
            clinic_id=clinic_id,
            name=request.user.name,
            email=request.user.email,
            password_hash=security.hash_password(request.user.password),
            role=request.user.role,
            is_active=True
        )
        db.add(user)
        await db.flush()  # Get user ID
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=clinic_id,
            user_id=user.id,
            action="clinic_registered",
            entity="clinic",
            entity_id=clinic_id,
            details={
                "clinic_name": request.clinic.name,
                "admin_email": user.email
            }
        )
        db.add(audit_log)
        
        await db.commit()
        
        return {
            "clinic_id": str(clinic_id),
            "user_id": str(user.id),
            "message": "Clinic and admin user created successfully"
        }
        
    except IntegrityError as e:
        await db.rollback()
        if "email" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        elif "cnpj_cpf" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CNPJ/CPF already registered"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed"
            )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Authenticate user and return tokens."""
    # Get user by email
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    if not security.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create tokens
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "clinic_id": str(user.clinic_id)
    }
    
    access_token = security.create_access_token(token_data)
    refresh_token = security.create_refresh_token(token_data)
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=user.clinic_id,
        user_id=user.id,
        action="user_login",
        entity="user",
        entity_id=user.id,
        details={"login_method": "password"}
    )
    db.add(audit_log)
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Refresh access token using refresh token."""
    payload = security.verify_token(request.refresh_token, "refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "clinic_id": str(user.clinic_id)
    }
    
    access_token = security.create_access_token(token_data)
    refresh_token = security.create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/logout")
async def logout(
    request: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Logout user and invalidate refresh token."""
    # In a production system, you would store refresh tokens in a database
    # and mark them as invalidated here
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="user_logout",
        entity="user",
        entity_id=current_user.id,
        details={"logout_method": "token"}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "Logged out successfully"}


@router.post("/2fa/setup")
async def setup_two_factor(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Setup two-factor authentication for user."""
    if current_user.twofa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA already enabled"
        )
    
    # Generate TOTP secret
    secret = security.generate_totp_secret()
    
    # Update user
    current_user.twofa_secret = secret
    await db.commit()
    
    # Generate QR code URL
    qr_url = security.generate_totp_qr_url(
        secret, 
        current_user.email, 
        settings.app_name
    )
    
    return {
        "secret": secret,
        "qr_url": qr_url,
        "message": "Scan QR code with authenticator app"
    }


@router.post("/2fa/verify")
async def verify_two_factor(
    request: TwoFactorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Verify two-factor authentication token."""
    if not current_user.twofa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA not enabled"
        )
    
    # Verify TOTP token
    if not security.verify_totp(current_user.twofa_secret, request.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA token"
        )
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="2fa_verified",
        entity="user",
        entity_id=current_user.id,
        details={"verification_method": "totp"}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "2FA verification successful"}


@router.post("/2fa/disable")
async def disable_two_factor(
    request: TwoFactorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Disable two-factor authentication."""
    if not current_user.twofa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA not enabled"
        )
    
    # Verify TOTP token before disabling
    if not security.verify_totp(current_user.twofa_secret, request.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA token"
        )
    
    # Disable 2FA
    current_user.twofa_secret = None
    await db.commit()
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="2fa_disabled",
        entity="user",
        entity_id=current_user.id,
        details={"verification_method": "totp"}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "2FA disabled successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user_response)
):
    """Get current user information."""
    return current_user
