"""
Enhanced Authentication Middleware
Enforces security policies including 2FA for admins and doctors
"""

import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import security
from app.core.security_config import (
    UserRole, SecurityPolicy, RolePermissions, 
    RoleHierarchy, DataAccessRules
)
from app.db.session import get_db_session
from app.models import User

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer()


class EnhancedAuthDependencies:
    """Enhanced authentication with enforced security policies."""
    
    @staticmethod
    async def get_current_user_with_2fa_check(
        credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
        db: AsyncSession = Depends(get_db_session),
        request: Request = None
    ) -> User:
        """
        Get current user with 2FA enforcement for admins and doctors.
        
        This is the MAIN authentication dependency that should be used
        throughout the application for best security.
        """
        token = credentials.credentials
        payload = security.verify_token(token, "access")
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user from database
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # ENFORCE 2FA for admins and doctors
        if SecurityPolicy.requires_2fa(user.role):
            # Check if 2FA is verified in token
            twofa_verified = payload.get("twofa_verified", False)
            
            if not twofa_verified:
                # Check if user has 2FA enabled
                # (In production, check against TwoFASecret table)
                logger.warning(
                    f"2FA required but not verified for {user.role} user: {user.email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Two-factor authentication is required for {user.role} role. "
                           "Please enable 2FA in your account settings."
                )
        
        # Check session timeout
        issued_at = payload.get("iat")
        if issued_at:
            token_age_minutes = (datetime.utcnow().timestamp() - issued_at) / 60
            timeout = SecurityPolicy.get_session_timeout(user.role)
            
            if token_age_minutes > timeout:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired. Please log in again."
                )
        
        # Log access for audit
        if request:
            logger.info(
                f"User access: {user.email} ({user.role}) - "
                f"IP: {request.client.host} - "
                f"Endpoint: {request.url.path}"
            )
        
        return user
    
    @staticmethod
    def require_role_strict(required_role: str):
        """
        Require exact role match (no hierarchy).
        Use this when you need specific role, not higher.
        """
        async def role_checker(
            user: User = Depends(EnhancedAuthDependencies.get_current_user_with_2fa_check)
        ):
            if user.role.lower() != required_role.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This action requires {required_role} role"
                )
            return user
        
        return role_checker
    
    @staticmethod
    def require_role_hierarchy(required_role: str):
        """
        Require role at or above required level (with hierarchy).
        This is the default and most commonly used.
        """
        async def role_checker(
            user: User = Depends(EnhancedAuthDependencies.get_current_user_with_2fa_check)
        ):
            if not RoleHierarchy.can_access_role(user.role, required_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {required_role} or higher"
                )
            return user
        
        return role_checker
    
    @staticmethod
    def require_permission_enhanced(permission: str):
        """
        Require specific permission using enhanced permission system.
        """
        async def permission_checker(
            user: User = Depends(EnhancedAuthDependencies.get_current_user_with_2fa_check)
        ):
            if not RolePermissions.has_permission(user.role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}"
                )
            return user
        
        return permission_checker
    
    @staticmethod
    async def check_data_access(
        user: User,
        resource_type: str,
        resource_owner_id: Optional[uuid.UUID] = None,
        db: AsyncSession = None
    ) -> bool:
        """
        Check if user can access specific resource.
        
        Args:
            user: Current user
            resource_type: Type of resource (patient, medical_record, etc.)
            resource_owner_id: ID of resource owner (for patient data)
            db: Database session
        """
        is_own_data = False
        
        # Check if accessing own data (for patients)
        if resource_owner_id and user.role.lower() == UserRole.PATIENT:
            # For patients, check if they're accessing their own data
            # In a real system, you'd query the patients table to link user to patient
            is_own_data = True  # Simplified for now
        
        if resource_type == "patient":
            return DataAccessRules.can_access_patient_data(
                user.role, str(user.id), str(resource_owner_id), is_own_data
            )
        elif resource_type == "medical_record":
            return DataAccessRules.can_access_medical_records(user.role, is_own_data)
        elif resource_type == "billing":
            return DataAccessRules.can_modify_billing(user.role)
        elif resource_type == "user":
            return DataAccessRules.can_manage_users(user.role)
        
        return False


# Convenience dependencies with 2FA enforcement
get_current_user = EnhancedAuthDependencies.get_current_user_with_2fa_check

# Role-based dependencies (with hierarchy)
require_admin = EnhancedAuthDependencies.require_role_hierarchy("admin")
require_doctor = EnhancedAuthDependencies.require_role_hierarchy("doctor")
require_secretary = EnhancedAuthDependencies.require_role_hierarchy("secretary")

# Strict role dependencies (exact match only)
require_admin_only = EnhancedAuthDependencies.require_role_strict("admin")
require_doctor_only = EnhancedAuthDependencies.require_role_strict("doctor")

# Permission-based dependencies (using enhanced system)
require_medical_records_write = EnhancedAuthDependencies.require_permission_enhanced("medical_records.write")
require_prescriptions_sign = EnhancedAuthDependencies.require_permission_enhanced("prescriptions.sign")
require_billing_write = EnhancedAuthDependencies.require_permission_enhanced("billing.write")
require_users_manage = EnhancedAuthDependencies.require_permission_enhanced("users.write")
require_settings_write = EnhancedAuthDependencies.require_permission_enhanced("settings.write")


def create_audit_log_entry(
    user: User,
    action: str,
    resource_type: str,
    resource_id: Optional[uuid.UUID],
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> Dict[str, Any]:
    """
    Create audit log entry for user action.
    
    This should be called after any sensitive operation.
    """
    log_entry = {
        "user_id": str(user.id),
        "user_email": user.email,
        "user_role": user.role,
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id else None,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {},
    }
    
    if request:
        log_entry["ip_address"] = request.client.host if request.client else None
        log_entry["user_agent"] = request.headers.get("user-agent")
        log_entry["endpoint"] = request.url.path
    
    logger.info(f"AUDIT: {action} on {resource_type} by {user.email} ({user.role})")
    
    return log_entry


# Export main items
__all__ = [
    "EnhancedAuthDependencies",
    "get_current_user",
    "require_admin",
    "require_doctor",
    "require_secretary",
    "require_admin_only",
    "require_doctor_only",
    "require_medical_records_write",
    "require_prescriptions_sign",
    "require_billing_write",
    "require_users_manage",
    "require_settings_write",
    "create_audit_log_entry",
]

