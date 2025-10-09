"""
API endpoints for 2FA, RBAC, and audit system.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, and_
from typing import List, Optional, Dict, Any
import uuid
import json
import logging
import qrcode
import io
import base64
from datetime import datetime, timedelta

from ..models.security import (
    TwoFASecret, Role, UserRole, Permission, AuditLog,
    TwoFAStatus, AuditAction, AuditSeverity, PermissionCategory,
    TwoFASetupRequest, TwoFASetupResponse, TwoFAVerifyRequest, TwoFAVerifyResponse,
    TwoFADisableRequest, RoleCreateRequest, RoleResponse, UserRoleAssignRequest,
    AuditLogResponse, TwoFAManager, RBACManager, AuditManager
)
from ..core.auth import get_current_user, get_current_tenant, require_permission
from ..db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["security"])

# 2FA Endpoints
@router.post("/auth/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Setup 2FA for a user."""
    
    try:
        # Check if 2FA is already enabled
        existing_2fa = db.exec(
            select(TwoFASecret).where(
                and_(
                    TwoFASecret.user_id == current_user.id,
                    TwoFASecret.status == TwoFAStatus.ENABLED
                )
            )
        ).first()
        
        if existing_2fa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is already enabled for this user"
            )
        
        # Generate new secret
        secret = TwoFAManager.generate_secret()
        backup_codes = TwoFAManager.generate_backup_codes()
        setup_token = str(uuid.uuid4())
        
        # Encrypt secret (in production, use proper key management)
        encryption_key = "your-encryption-key-here"  # Should come from environment
        encrypted_secret = TwoFAManager.encrypt_secret(secret, encryption_key)
        
        # Create or update 2FA record
        twofa_record = db.exec(
            select(TwoFASecret).where(TwoFASecret.user_id == current_user.id)
        ).first()
        
        if twofa_record:
            # Update existing record
            twofa_record.secret_encrypted = encrypted_secret
            twofa_record.backup_codes = backup_codes
            twofa_record.status = TwoFAStatus.PENDING_SETUP
            twofa_record.updated_at = datetime.utcnow()
            db.add(twofa_record)
        else:
            # Create new record
            twofa_record = TwoFASecret(
                user_id=current_user.id,
                clinic_id=current_tenant.id,
                secret_encrypted=encrypted_secret,
                backup_codes=backup_codes,
                status=TwoFAStatus.PENDING_SETUP,
                issuer="Prontivus",
                algorithm="SHA1",
                digits=6,
                period=30
            )
            db.add(twofa_record)
        
        db.commit()
        db.refresh(twofa_record)
        
        # Generate QR code URL
        qr_url = TwoFAManager.generate_qr_url(
            secret, 
            current_user.get("email", "user@example.com"),
            "Prontivus"
        )
        
        # Log 2FA setup initiation
        await log_audit_event(
            db, current_tenant.id, current_user.id, AuditAction.TWOFA_SETUP,
            "twofa_secret", twofa_record.id, request, "2FA setup initiated"
        )
        
        return TwoFASetupResponse(
            qr_code_url=qr_url,
            secret_key=secret,
            backup_codes=backup_codes,
            setup_token=setup_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up 2FA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup 2FA"
        )

@router.post("/auth/2fa/verify", response_model=TwoFAVerifyResponse)
async def verify_2fa(
    request_data: TwoFAVerifyRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Verify 2FA token and enable 2FA."""
    
    try:
        # Get 2FA record
        twofa_record = db.exec(
            select(TwoFASecret).where(TwoFASecret.user_id == current_user.id)
        ).first()
        
        if not twofa_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="2FA setup not found"
            )
        
        # Decrypt secret
        encryption_key = "your-encryption-key-here"  # Should come from environment
        secret = TwoFAManager.decrypt_secret(twofa_record.secret_encrypted, encryption_key)
        
        # Verify token
        if not TwoFAManager.verify_totp_token(secret, request_data.token):
            # Increment failed attempts
            twofa_record.failed_attempts += 1
            if twofa_record.failed_attempts >= 5:
                twofa_record.locked_until = datetime.utcnow() + timedelta(minutes=15)
                twofa_record.status = TwoFAStatus.SUSPENDED
            
            db.add(twofa_record)
            db.commit()
            
            # Log failed verification
            await log_audit_event(
                db, current_tenant.id, current_user.id, AuditAction.TWOFA_VERIFY,
                "twofa_secret", twofa_record.id, request, "2FA verification failed",
                severity=AuditSeverity.HIGH
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 2FA token"
            )
        
        # Check if locked
        if twofa_record.locked_until and datetime.utcnow() < twofa_record.locked_until:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="2FA is temporarily locked due to too many failed attempts"
            )
        
        # Enable 2FA
        twofa_record.status = TwoFAStatus.ENABLED
        twofa_record.setup_at = datetime.utcnow()
        twofa_record.last_used_at = datetime.utcnow()
        twofa_record.failed_attempts = 0
        twofa_record.locked_until = None
        twofa_record.updated_at = datetime.utcnow()
        
        db.add(twofa_record)
        db.commit()
        
        # Log successful verification
        await log_audit_event(
            db, current_tenant.id, current_user.id, AuditAction.TWOFA_VERIFY,
            "twofa_secret", twofa_record.id, request, "2FA verification successful"
        )
        
        return TwoFAVerifyResponse(
            success=True,
            message="2FA has been enabled successfully",
            backup_codes=twofa_record.backup_codes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying 2FA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify 2FA"
        )

@router.post("/auth/2fa/disable")
async def disable_2fa(
    request_data: TwoFADisableRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Disable 2FA for a user."""
    
    try:
        # Get 2FA record
        twofa_record = db.exec(
            select(TwoFASecret).where(TwoFASecret.user_id == current_user.id)
        ).first()
        
        if not twofa_record or twofa_record.status != TwoFAStatus.ENABLED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="2FA is not enabled for this user"
            )
        
        # Verify current token
        encryption_key = "your-encryption-key-here"  # Should come from environment
        secret = TwoFAManager.decrypt_secret(twofa_record.secret_encrypted, encryption_key)
        
        if not TwoFAManager.verify_totp_token(secret, request_data.token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 2FA token"
            )
        
        # Disable 2FA
        twofa_record.status = TwoFAStatus.DISABLED
        twofa_record.secret_encrypted = None
        twofa_record.backup_codes = None
        twofa_record.updated_at = datetime.utcnow()
        
        db.add(twofa_record)
        db.commit()
        
        # Log 2FA disable
        await log_audit_event(
            db, current_tenant.id, current_user.id, AuditAction.TWOFA_DISABLE,
            "twofa_secret", twofa_record.id, request, "2FA disabled",
            severity=AuditSeverity.HIGH
        )
        
        return {"message": "2FA has been disabled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling 2FA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable 2FA"
        )

# RBAC Endpoints
@router.post("/roles", response_model=RoleResponse)
async def create_role(
    request_data: RoleCreateRequest,
    request: Request,
    current_user = Depends(require_permission("users.create")),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Create a new role."""
    
    try:
        # Check if role name already exists
        existing_role = db.exec(
            select(Role).where(
                and_(
                    Role.clinic_id == current_tenant.id,
                    Role.name == request_data.name
                )
            )
        ).first()
        
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Role with this name already exists"
            )
        
        # Create role
        role = Role(
            clinic_id=current_tenant.id,
            name=request_data.name,
            description=request_data.description,
            permissions=request_data.permissions,
            is_system_role=False,
            is_active=True
        )
        
        db.add(role)
        db.commit()
        db.refresh(role)
        
        # Log role creation
        await log_audit_event(
            db, current_tenant.id, current_user.id, AuditAction.CREATE,
            "roles", role.id, request, f"Role '{role.name}' created",
            new_values=role.dict()
        )
        
        return RoleResponse.from_orm(role)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create role"
        )

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    current_user = Depends(require_permission("users.read")),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """List all roles for the clinic."""
    
    roles = db.exec(
        select(Role).where(
            and_(
                Role.clinic_id == current_tenant.id,
                Role.is_active == True
            )
        ).order_by(Role.name)
    ).all()
    
    return [RoleResponse.from_orm(role) for role in roles]

@router.post("/users/{user_id}/roles")
async def assign_user_role(
    user_id: uuid.UUID,
    request_data: UserRoleAssignRequest,
    request: Request,
    current_user = Depends(require_permission("users.update")),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Assign a role to a user."""
    
    try:
        # Verify user exists and belongs to clinic
        user = db.exec(
            select("User").where(
                and_(
                    "User.id == user_id",
                    "User.clinic_id == current_tenant.id"
                )
            )
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify role exists and belongs to clinic
        role = db.exec(
            select(Role).where(
                and_(
                    Role.id == request_data.role_id,
                    Role.clinic_id == current_tenant.id,
                    Role.is_active == True
                )
            )
        ).first()
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        # Check if assignment already exists
        existing_assignment = db.exec(
            select(UserRole).where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.role_id == request_data.role_id,
                    UserRole.is_active == True
                )
            )
        ).first()
        
        if existing_assignment:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has this role assigned"
            )
        
        # Create role assignment
        user_role = UserRole(
            user_id=user_id,
            role_id=request_data.role_id,
            clinic_id=current_tenant.id,
            assigned_by=current_user.id,
            expires_at=request_data.expires_at,
            assignment_reason=request_data.reason,
            is_active=True
        )
        
        db.add(user_role)
        db.commit()
        db.refresh(user_role)
        
        # Log role assignment
        await log_audit_event(
            db, current_tenant.id, current_user.id, AuditAction.PERMISSION_GRANT,
            "user_roles", user_role.id, request, f"Role '{role.name}' assigned to user",
            new_values=user_role.dict()
        )
        
        return {"message": f"Role '{role.name}' assigned to user successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role"
        )

@router.delete("/users/{user_id}/roles/{role_id}")
async def revoke_user_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    request: Request,
    current_user = Depends(require_permission("users.update")),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Revoke a role from a user."""
    
    try:
        # Get role assignment
        user_role = db.exec(
            select(UserRole).where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role_id,
                    UserRole.clinic_id == current_tenant.id,
                    UserRole.is_active == True
                )
            )
        ).first()
        
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role assignment not found"
            )
        
        # Get role name for logging
        role = db.exec(
            select(Role).where(Role.id == role_id)
        ).first()
        
        # Revoke role
        user_role.is_active = False
        user_role.updated_at = datetime.utcnow()
        
        db.add(user_role)
        db.commit()
        
        # Log role revocation
        await log_audit_event(
            db, current_tenant.id, current_user.id, AuditAction.PERMISSION_REVOKE,
            "user_roles", user_role.id, request, f"Role '{role.name}' revoked from user",
            old_values=user_role.dict()
        )
        
        return {"message": f"Role '{role.name}' revoked from user successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke role"
        )

# Audit Endpoints
@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    action: Optional[AuditAction] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    current_user = Depends(require_permission("audit_logs.read")),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """List audit logs with optional filters."""
    
    statement = select(AuditLog).where(AuditLog.clinic_id == current_tenant.id)
    
    if action:
        statement = statement.where(AuditLog.action == action)
    
    if resource_type:
        statement = statement.where(AuditLog.resource_type == resource_type)
    
    if user_id:
        statement = statement.where(AuditLog.user_id == user_id)
    
    if start_date:
        statement = statement.where(AuditLog.created_at >= start_date)
    
    if end_date:
        statement = statement.where(AuditLog.created_at <= end_date)
    
    statement = statement.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    
    logs = db.exec(statement).all()
    
    return [AuditLogResponse.from_orm(log) for log in logs]

@router.get("/audit-logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: uuid.UUID,
    current_user = Depends(require_permission("audit_logs.read")),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get specific audit log details."""
    
    log = db.exec(
        select(AuditLog).where(
            and_(
                AuditLog.id == log_id,
                AuditLog.clinic_id == current_tenant.id
            )
        )
    ).first()
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )
    
    return AuditLogResponse.from_orm(log)

# Utility function for audit logging
async def log_audit_event(
    db: Session,
    clinic_id: uuid.UUID,
    user_id: uuid.UUID,
    action: AuditAction,
    resource_type: str,
    resource_id: Optional[uuid.UUID],
    request: Request,
    message: str,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    severity: Optional[AuditSeverity] = None
):
    """Log an audit event."""
    
    try:
        # Determine severity if not provided
        if severity is None:
            severity = AuditManager.determine_severity(action, resource_type)
        
        # Redact sensitive data
        redacted_old_values = AuditManager.redact_sensitive_data(old_values) if old_values else None
        redacted_new_values = AuditManager.redact_sensitive_data(new_values) if new_values else None
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=clinic_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            endpoint=str(request.url.path),
            method=request.method,
            old_values=redacted_old_values,
            new_values=redacted_new_values,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            severity=severity,
            metadata={
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            },
            is_sensitive=AuditManager.is_sensitive_resource(resource_type)
        )
        
        db.add(audit_log)
        db.commit()
        
    except Exception as e:
        logger.error(f"Error logging audit event: {str(e)}")
        # Don't raise exception as this is just logging
