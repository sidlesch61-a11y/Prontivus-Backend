"""
Authentication dependencies and middleware for FastAPI.
"""

import uuid
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import security
from app.core.config import settings
from app.db.session import get_db_session
from app.models import User, Clinic, License, ActivationStatus
from app.schemas import UserResponse


# Security scheme
security_scheme = HTTPBearer()


# Forward declarations - will be defined after AuthDependencies class
get_current_user = None
get_current_clinic = None
get_current_user_response = None
get_license_entitlements = None


class AuthDependencies:
    """Authentication dependencies for FastAPI endpoints."""
    
    @staticmethod
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
        db: AsyncSession = Depends(get_db_session)
    ) -> User:
        """Get current authenticated user."""
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
        
        return user
    
    @staticmethod
    async def _get_current_clinic_impl(user: User, db: AsyncSession) -> Clinic:
        """Implementation for getting current clinic."""
        result = await db.execute(
            select(Clinic).where(Clinic.id == user.clinic_id)
        )
        clinic = result.scalar_one_or_none()
        
        if not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clinic not found"
            )
        
        return clinic
    
    @staticmethod
    async def get_current_clinic(
        credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
        db: AsyncSession = Depends(get_db_session)
    ) -> Clinic:
        """Get current user's clinic."""
        user = await AuthDependencies.get_current_user(credentials, db)
        return await AuthDependencies._get_current_clinic_impl(user, db)
    
    @staticmethod
    async def get_current_user_response(
        credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
        db: AsyncSession = Depends(get_db_session)
    ) -> UserResponse:
        """Get current user as response schema."""
        user = await AuthDependencies.get_current_user(credentials, db)
        return UserResponse.model_validate(user)
    
    @staticmethod
    def require_role(required_role: str):
        """Dependency factory for role-based access control."""
        async def role_checker(user: User = Depends(AuthDependencies.get_current_user)):
            # Role hierarchy: superadmin > admin > doctor > secretary > patient
            role_hierarchy = {
                "superadmin": 5,
                "admin": 4,
                "doctor": 3,
                "secretary": 2,
                "patient": 1
            }
            
            # Make role comparison case-insensitive
            user_level = role_hierarchy.get(user.role.lower(), 0)
            required_level = role_hierarchy.get(required_role.lower(), 0)
            
            if user_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required role: {required_role}"
                )
            
            return user
        
        return role_checker
    
    @staticmethod
    def require_permission(permission: str):
        """Dependency factory for permission-based access control."""
        async def permission_checker(
            credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
            db: AsyncSession = Depends(get_db_session)
        ):
            # Get current user
            user = await AuthDependencies.get_current_user(credentials, db)
            
            # Check if user has required permission
            # This would typically check against a permissions table
            # For now, we'll use role-based permissions
            
            permissions = {
                "users.read": ["superadmin", "admin"],
                "users.write": ["superadmin", "admin"],
                "patients.read": ["superadmin", "admin", "doctor", "secretary"],
                "patients.write": ["superadmin", "admin", "doctor", "secretary"],
                "appointments.read": ["superadmin", "admin", "doctor", "secretary"],
                "appointments.write": ["superadmin", "admin", "doctor", "secretary"],
                "medical_records.read": ["superadmin", "admin", "doctor"],
                "medical_records.write": ["superadmin", "admin", "doctor"],
                "billing.read": ["superadmin", "admin", "doctor", "secretary"],
                "billing.write": ["superadmin", "admin"],
                "settings.read": ["superadmin", "admin"],
                "settings.write": ["superadmin", "admin"],
            }
            
            allowed_roles = permissions.get(permission, [])
            # Make role comparison case-insensitive
            if user.role.lower() not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions for: {permission}"
                )
            
            return user
        
        return permission_checker
    
    @staticmethod
    async def get_license_entitlements(
        clinic: Clinic = Depends(get_current_clinic),
        db: AsyncSession = Depends(get_db_session)
    ) -> Dict[str, Any]:
        """Get clinic's license entitlements."""
        result = await db.execute(
            select(License).where(
                License.clinic_id == clinic.id,
                License.status == "active"
            ).order_by(License.end_at.desc())
        )
        license_obj = result.scalar_one_or_none()
        
        if not license_obj:
            return {
                "modules": [],
                "users_limit": 0,
                "units_limit": 0,
                "expires_at": None
            }
        
        return {
            "modules": license_obj.modules,
            "users_limit": license_obj.users_limit,
            "units_limit": license_obj.units_limit,
            "expires_at": license_obj.end_at
        }
    
    @staticmethod
    def require_module(module: str):
        """Dependency factory for module-based access control."""
        async def module_checker(
            entitlements: Dict[str, Any] = Depends(get_license_entitlements)
        ):
            if module not in entitlements.get("modules", []):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Module '{module}' not enabled in license"
                )
            return entitlements
        
        return module_checker

    @staticmethod
    def require_admin_access(user: User = Depends(get_current_user)):
        """Require admin access."""
        if not hasattr(user, 'role') or user.role != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return user


# Tenant middleware
class TenantMiddleware:
    """Middleware for multi-tenant support."""
    
    @staticmethod
    async def get_tenant_from_request(request: Request) -> Optional[uuid.UUID]:
        """Extract tenant ID from request."""
        # Try to get from subdomain
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            if subdomain != "www" and subdomain != "api":
                # This would typically query database for clinic by subdomain
                # For now, return None
                pass
        
        # Try to get from header
        clinic_id = request.headers.get("X-Clinic-Id")
        if clinic_id:
            try:
                return uuid.UUID(clinic_id)
            except ValueError:
                pass
        
        # Try to get from JWT token (if available)
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = security.verify_token(token, "access")
            if payload:
                clinic_id = payload.get("clinic_id")
                if clinic_id:
                    try:
                        return uuid.UUID(clinic_id)
                    except ValueError:
                        pass
        
        return None
    
    @staticmethod
    async def validate_tenant_access(
        tenant_id: uuid.UUID,
        user: User = Depends(AuthDependencies.get_current_user)
    ) -> uuid.UUID:
        """Validate user has access to tenant."""
        if user.clinic_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this tenant"
            )
        return tenant_id


# Convenience dependencies
get_current_user = AuthDependencies.get_current_user
get_current_clinic = AuthDependencies.get_current_clinic
get_current_user_response = AuthDependencies.get_current_user_response
get_license_entitlements = AuthDependencies.get_license_entitlements
require_admin_access = AuthDependencies.require_admin_access

# Role-based dependencies
require_admin = AuthDependencies.require_role("admin")
require_doctor = AuthDependencies.require_role("doctor")
require_secretary = AuthDependencies.require_role("secretary")

# Permission-based dependencies
require_users_read = AuthDependencies.require_permission("users.read")
require_users_write = AuthDependencies.require_permission("users.write")
require_patients_read = AuthDependencies.require_permission("patients.read")
require_patients_write = AuthDependencies.require_permission("patients.write")
require_appointments_read = AuthDependencies.require_permission("appointments.read")
require_appointments_write = AuthDependencies.require_permission("appointments.write")
require_medical_records_read = AuthDependencies.require_permission("medical_records.read")
require_medical_records_write = AuthDependencies.require_permission("medical_records.write")
require_billing_read = AuthDependencies.require_permission("billing.read")
require_billing_write = AuthDependencies.require_permission("billing.write")

# Module-based dependencies
require_billing_module = AuthDependencies.require_module("billing")
require_inventory_module = AuthDependencies.require_module("inventory")
require_telemedicine_module = AuthDependencies.require_module("telemedicine")
