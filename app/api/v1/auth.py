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
    """
    Register a new clinic and admin user.
    
    This endpoint creates a clinic and its first admin user in a single transaction.
    All errors are caught and converted to appropriate HTTP status codes.
    """
    import logging
    logger = logging.getLogger("app.api.v1.auth")
    
    try:
        logger.info(f"========== REGISTRATION ATTEMPT ==========")
        logger.info(f"Email: {request.user.email}")
        logger.info(f"Clinic Name: {request.clinic.name}")
        logger.info(f"CNPJ: {request.clinic.cnpj_cpf}")
        logger.info(f"Role: {request.user.role}")
        
        # Validate email uniqueness first
        existing_user_query = await db.execute(
            select(User).where(User.email == request.user.email)
        )
        existing_user = existing_user_query.scalar_one_or_none()
        if existing_user:
            logger.warning(f"Registration failed: Email already exists - {request.user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-mail já cadastrado no sistema."
            )
        
        # Validate CNPJ uniqueness
        existing_clinic_query = await db.execute(
            select(Clinic).where(Clinic.cnpj_cpf == request.clinic.cnpj_cpf)
        )
        existing_clinic = existing_clinic_query.scalar_one_or_none()
        if existing_clinic:
            logger.warning(f"Registration failed: CNPJ already exists - {request.clinic.cnpj_cpf}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CNPJ/CPF já cadastrado no sistema."
            )
        
        # Create clinic using raw SQL - let DB defaults handle status and settings
        logger.info("Creating clinic with raw SQL (using DB defaults)...")
        from sqlalchemy import text
        
        clinic_id = uuid.uuid4()
        now = datetime.utcnow()
        
        try:
            # Insert without status (uses DB default 'active') and without settings (uses DB default {})
            await db.execute(
                text("""
                    INSERT INTO clinics 
                    (id, name, cnpj_cpf, contact_email, contact_phone, logo_url, created_at, updated_at)
                    VALUES 
                    (:id, :name, :cnpj, :email, :phone, :logo, :created, :updated)
                """),
                {
                    "id": str(clinic_id),
                    "name": request.clinic.name,
                    "cnpj": request.clinic.cnpj_cpf,
                    "email": request.clinic.contact_email,
                    "phone": request.clinic.contact_phone,
                    "logo": None,
                    "created": now,
                    "updated": now
                }
            )
            await db.flush()
            
            # Fetch the created clinic to get the full object
            result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
            clinic = result.scalar_one()
            
            logger.info(f"✅ Clinic created successfully: {clinic.id}")
        except Exception as clinic_error:
            logger.error(f"========== CLINIC CREATION ERROR ==========")
            logger.error(f"Error type: {type(clinic_error).__name__}")
            logger.error(f"Error message: {str(clinic_error)}")
            
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            
            await db.rollback()
            
            error_detail = f"Falha ao criar a clínica: {str(clinic_error)}"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_detail
            )
        
        # Hash password securely
        try:
            password_hash = security.hash_password(request.user.password)
        except Exception as hash_error:
            logger.error(f"Password hashing failed: {str(hash_error)}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Erro ao processar a senha. Tente novamente."
            )
        
        # Create admin user
        user = User(
            clinic_id=clinic.id,
            name=request.user.name,
            email=request.user.email,
            password_hash=password_hash,
            role=request.user.role,
            is_active=True,
            last_login=None
        )
        
        try:
            db.add(user)
            await db.flush()
            logger.info(f"User created successfully: {user.id}")
        except Exception as user_error:
            logger.error(f"User creation failed: {str(user_error)}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Falha ao criar o usuário. Verifique os dados e tente novamente."
            )
        
        # Create audit log
        try:
            audit_log = AuditLog(
                clinic_id=clinic.id,
                user_id=user.id,
                action="clinic_registered",
                entity="clinic",
                entity_id=clinic.id,
                details={
                    "clinic_name": clinic.name,
                    "admin_email": user.email,
                    "role": user.role
                }
            )
            db.add(audit_log)
            await db.commit()
            logger.info(f"Registration completed successfully for clinic: {clinic.id}, user: {user.id}")
        except Exception as audit_error:
            logger.warning(f"Audit log creation failed (non-critical): {str(audit_error)}")
            # Commit anyway - audit log failure shouldn't block registration
            await db.commit()
        
        return {
            "status": "success",
            "clinic_id": str(clinic.id),
            "user_id": str(user.id),
            "message": "Clínica e usuário administrador cadastrados com sucesso."
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (already properly formatted)
        raise
        
    except IntegrityError as e:
        await db.rollback()
        error_msg = str(e).lower()
        logger.error(f"Integrity error during registration: {error_msg}")
        
        if "email" in error_msg or "users_email" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-mail já cadastrado no sistema."
            )
        elif "cnpj_cpf" in error_msg or "clinics_cnpj" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CNPJ/CPF já cadastrado no sistema."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erro ao validar os dados. Verifique as informações e tente novamente."
            )
    
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error during registration: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Erro inesperado ao processar o cadastro. Tente novamente ou contate o suporte."
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
            detail="E-mail ou senha incorretos."
        )
    
    # Verify password
    if not security.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos."
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
            detail="Token de atualização inválido."
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dados do token inválidos."
        )
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo."
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
    
    return {"message": "Logout realizado com sucesso."}


@router.post("/2fa/setup")
async def setup_two_factor(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Setup two-factor authentication for user."""
    if current_user.twofa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Autenticação de dois fatores já está ativada."
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
        "message": "Escaneie o código QR com seu aplicativo autenticador."
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
            detail="Autenticação de dois fatores não está ativada."
        )
    
    # Verify TOTP token
    if not security.verify_totp(current_user.twofa_secret, request.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação inválido."
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
    
    return {"message": "Autenticação de dois fatores verificada com sucesso."}


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
            detail="Autenticação de dois fatores não está ativada."
        )
    
    # Verify TOTP token before disabling
    if not security.verify_totp(current_user.twofa_secret, request.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação inválido."
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
    
    return {"message": "Autenticação de dois fatores desativada com sucesso."}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user_response)
):
    """Get current user information."""
    return current_user
