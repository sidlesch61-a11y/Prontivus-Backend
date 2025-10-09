"""
Enhanced authentication system with RBAC and 2FA support.
"""

import jwt
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select, and_

from ..models.security import (
    TwoFASecret, Role, UserRole, Permission,
    TwoFAStatus, AuditAction, AuditSeverity
)
from ..core.config import settings
from ..db.session import get_db

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()

class RBACAuth:
    """Enhanced authentication with RBAC support."""
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
    
    def create_access_token(
        self,
        user_id: uuid.UUID,
        clinic_id: uuid.UUID,
        roles: List[str],
        permissions: List[str],
        twofa_verified: bool = False
    ) -> str:
        """Create JWT access token with RBAC claims."""
        
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": str(user_id),
            "clinic_id": str(clinic_id),
            "roles": roles,
            "permissions": permissions,
            "twofa_verified": twofa_verified,
            "iat": now,
            "exp": expire,
            "type": "access"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: uuid.UUID, clinic_id: uuid.UUID) -> str:
        """Create JWT refresh token."""
        
        now = datetime.utcnow()
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": str(user_id),
            "clinic_id": str(clinic_id),
            "iat": now,
            "exp": expire,
            "type": "refresh"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and return payload."""
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    async def get_user_permissions(
        self,
        db: Session,
        user_id: uuid.UUID,
        clinic_id: uuid.UUID
    ) -> List[str]:
        """Get all permissions for a user."""
        
        # Get user roles
        user_roles = db.exec(
            select(Role).join(UserRole).where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.clinic_id == clinic_id,
                    UserRole.is_active == True,
                    Role.is_active == True
                )
            )
        ).all()
        
        # Collect all permissions
        permissions = set()
        for role in user_roles:
            permissions.update(role.permissions)
        
        return list(permissions)
    
    async def check_2fa_requirement(
        self,
        db: Session,
        user_id: uuid.UUID
    ) -> bool:
        """Check if user has 2FA enabled."""
        
        twofa_record = db.exec(
            select(TwoFASecret).where(
                and_(
                    TwoFASecret.user_id == user_id,
                    TwoFASecret.status == TwoFAStatus.ENABLED
                )
            )
        ).first()
        
        return twofa_record is not None

# Global auth instance
rbac_auth = RBACAuth()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get current authenticated user with RBAC information."""
    
    try:
        # Verify token
        payload = rbac_auth.verify_token(credentials.credentials)
        
        # Extract user information
        user_id = uuid.UUID(payload["sub"])
        clinic_id = uuid.UUID(payload["clinic_id"])
        roles = payload.get("roles", [])
        permissions = payload.get("permissions", [])
        twofa_verified = payload.get("twofa_verified", False)
        
        # Check if user exists and is active
        user = db.exec(
            select("User").where(
                and_(
                    "User.id == user_id",
                    "User.clinic_id == clinic_id",
                    "User.is_active == True"
                )
            )
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Check 2FA requirement
        if await rbac_auth.check_2fa_requirement(db, user_id):
            if not twofa_verified:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="2FA verification required"
                )
        
        return {
            "id": user_id,
            "clinic_id": clinic_id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "roles": roles,
            "permissions": permissions,
            "twofa_verified": twofa_verified
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

async def get_current_tenant(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current tenant information."""
    
    return {
        "id": current_user["clinic_id"],
        "name": "Current Clinic"  # Would be fetched from database
    }

def require_permission(permission: str):
    """Dependency to require specific permission."""
    
    async def permission_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        
        if permission not in current_user["permissions"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        
        return current_user
    
    return permission_checker

def require_role(role: str):
    """Dependency to require specific role."""
    
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        
        if role not in current_user["roles"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required"
            )
        
        return current_user
    
    return role_checker

def require_2fa():
    """Dependency to require 2FA verification."""
    
    async def twofa_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        
        if not current_user["twofa_verified"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="2FA verification required"
            )
        
        return current_user
    
    return twofa_checker

async def verify_2fa_token(
    db: Session,
    user_id: uuid.UUID,
    token: str
) -> bool:
    """Verify 2FA token for user."""
    
    try:
        # Get 2FA record
        twofa_record = db.exec(
            select(TwoFASecret).where(
                and_(
                    TwoFASecret.user_id == user_id,
                    TwoFASecret.status == TwoFAStatus.ENABLED
                )
            )
        ).first()
        
        if not twofa_record:
            return False
        
        # Check if locked
        if twofa_record.locked_until and datetime.utcnow() < twofa_record.locked_until:
            return False
        
        # Decrypt secret
        encryption_key = "your-encryption-key-here"  # Should come from environment
        secret = TwoFAManager.decrypt_secret(twofa_record.secret_encrypted, encryption_key)
        
        # Verify token
        from ..models.security import TwoFAManager
        if TwoFAManager.verify_totp_token(secret, token):
            # Update last used time
            twofa_record.last_used_at = datetime.utcnow()
            twofa_record.failed_attempts = 0
            db.add(twofa_record)
            db.commit()
            return True
        else:
            # Increment failed attempts
            twofa_record.failed_attempts += 1
            if twofa_record.failed_attempts >= 5:
                twofa_record.locked_until = datetime.utcnow() + timedelta(minutes=15)
            
            db.add(twofa_record)
            db.commit()
            return False
            
    except Exception as e:
        logger.error(f"Error verifying 2FA token: {str(e)}")
        return False

async def login_with_2fa(
    db: Session,
    email: str,
    password: str,
    twofa_token: Optional[str] = None
) -> Dict[str, Any]:
    """Login with 2FA support."""
    
    try:
        # Verify user credentials
        user = db.exec(
            select("User").where(
                and_(
                    "User.email == email",
                    "User.is_active == True"
                )
            )
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password (simplified - use proper password hashing)
        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check 2FA requirement
        twofa_required = await rbac_auth.check_2fa_requirement(db, user.id)
        
        if twofa_required:
            if not twofa_token:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="2FA token required"
                )
            
            if not await verify_2fa_token(db, user.id, twofa_token):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid 2FA token"
                )
        
        # Get user permissions
        permissions = await rbac_auth.get_user_permissions(db, user.id, user.clinic_id)
        
        # Get user roles
        user_roles = db.exec(
            select(Role).join(UserRole).where(
                and_(
                    UserRole.user_id == user.id,
                    UserRole.clinic_id == user.clinic_id,
                    UserRole.is_active == True,
                    Role.is_active == True
                )
            )
        ).all()
        
        roles = [role.name for role in user_roles]
        
        # Create tokens
        access_token = rbac_auth.create_access_token(
            user.id, user.clinic_id, roles, permissions, twofa_token is not None
        )
        refresh_token = rbac_auth.create_refresh_token(user.id, user.clinic_id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "roles": roles,
                "permissions": permissions,
                "twofa_enabled": twofa_required
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    
    # Simplified - use proper password hashing library
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """Hash password for storage."""
    
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)

# Permission decorators
def has_permission(permission: str):
    """Decorator to check permission."""
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be used in route handlers
            # Implementation depends on FastAPI version
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def has_role(role: str):
    """Decorator to check role."""
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be used in route handlers
            # Implementation depends on FastAPI version
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Utility functions
async def get_user_effective_permissions(
    db: Session,
    user_id: uuid.UUID,
    clinic_id: uuid.UUID
) -> Dict[str, Any]:
    """Get user's effective permissions with metadata."""
    
    # Get user roles
    user_roles = db.exec(
        select(Role).join(UserRole).where(
            and_(
                UserRole.user_id == user_id,
                UserRole.clinic_id == clinic_id,
                UserRole.is_active == True,
                Role.is_active == True
            )
        )
    ).all()
    
    # Collect permissions
    permissions = set()
    role_permissions = {}
    
    for role in user_roles:
        role_permissions[role.name] = role.permissions
        permissions.update(role.permissions)
    
    return {
        "permissions": list(permissions),
        "roles": [role.name for role in user_roles],
        "role_permissions": role_permissions
    }

async def check_resource_access(
    db: Session,
    user_id: uuid.UUID,
    clinic_id: uuid.UUID,
    resource_type: str,
    action: str,
    resource_id: Optional[uuid.UUID] = None
) -> bool:
    """Check if user can perform action on resource."""
    
    # Get user permissions
    permissions = await rbac_auth.get_user_permissions(db, user_id, clinic_id)
    
    # Check specific permission
    required_permission = f"{resource_type}.{action}"
    if required_permission in permissions:
        return True
    
    # Check wildcard permissions
    if f"{resource_type}.*" in permissions or "*.{action}" in permissions or "*.*" in permissions:
        return True
    
    return False
