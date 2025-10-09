"""
Database models for 2FA, RBAC, and comprehensive audit system.
"""

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
import uuid

class TwoFAStatus(str, Enum):
    """2FA status enumeration."""
    DISABLED = "disabled"
    PENDING_SETUP = "pending_setup"
    ENABLED = "enabled"
    SUSPENDED = "suspended"

class AuditAction(str, Enum):
    """Audit action enumeration."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    TWOFA_SETUP = "2fa_setup"
    TWOFA_VERIFY = "2fa_verify"
    TWOFA_DISABLE = "2fa_disable"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    FORCE_UNLOCK = "force_unlock"
    EXPORT_DATA = "export_data"
    IMPORT_DATA = "import_data"

class AuditSeverity(str, Enum):
    """Audit severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class PermissionCategory(str, Enum):
    """Permission category enumeration."""
    USER_MANAGEMENT = "user_management"
    PATIENT_MANAGEMENT = "patient_management"
    APPOINTMENT_MANAGEMENT = "appointment_management"
    MEDICAL_RECORDS = "medical_records"
    PRESCRIPTIONS = "prescriptions"
    INVOICES = "invoices"
    REPORTS = "reports"
    SYSTEM_ADMIN = "system_admin"
    AUDIT_LOGS = "audit_logs"
    LICENSES = "licenses"
    INTEGRATIONS = "integrations"

class TwoFASecret(SQLModel, table=True):
    """2FA secret storage model."""
    
    __tablename__ = "twofa_secrets"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", unique=True, index=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # 2FA configuration
    secret_encrypted: str = Field(description="Encrypted TOTP secret")
    backup_codes: Optional[List[str]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    status: TwoFAStatus = Field(default=TwoFAStatus.DISABLED, description="2FA status")
    
    # Setup metadata
    setup_at: Optional[datetime] = Field(default=None, description="When 2FA was enabled")
    last_used_at: Optional[datetime] = Field(default=None, description="Last successful verification")
    failed_attempts: int = Field(default=0, description="Consecutive failed attempts")
    locked_until: Optional[datetime] = Field(default=None, description="Lock expiry time")
    
    # Configuration
    issuer: str = Field(default="Prontivus", description="TOTP issuer")
    algorithm: str = Field(default="SHA1", description="TOTP algorithm")
    digits: int = Field(default=6, description="TOTP digits")
    period: int = Field(default=30, description="TOTP period in seconds")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: Optional["User"] = Relationship()
    clinic: Optional["Clinic"] = Relationship()

class Role(SQLModel, table=True):
    """Role model for RBAC."""
    
    __tablename__ = "roles"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Role definition
    name: str = Field(description="Role name", index=True)
    description: Optional[str] = Field(default=None, description="Role description")
    is_system_role: bool = Field(default=False, description="System-defined role")
    
    # Permissions
    permissions: List[str] = Field(default_factory=list, sa_column_kwargs={"type_": "JSONB"})
    permissions_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Role metadata
    role_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Status
    is_active: bool = Field(default=True, description="Role is active")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    user_roles: List["UserRole"] = Relationship(back_populates="role")

class UserRole(SQLModel, table=True):
    """User-Role assignment model."""
    
    __tablename__ = "user_roles"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    role_id: uuid.UUID = Field(foreign_key="roles.id", index=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # Assignment metadata
    assigned_by: uuid.UUID = Field(foreign_key="users.id", description="User who assigned the role")
    assigned_at: datetime = Field(default_factory=datetime.utcnow, description="When role was assigned")
    expires_at: Optional[datetime] = Field(default=None, description="Role expiration")
    
    # Assignment context
    assignment_reason: Optional[str] = Field(default=None, description="Reason for assignment")
    assignment_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Status
    is_active: bool = Field(default=True, description="Assignment is active")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: Optional["User"] = Relationship()
    role: Optional["Role"] = Relationship(back_populates="user_roles")
    clinic: Optional["Clinic"] = Relationship()
    assigned_by_user: Optional["User"] = Relationship(foreign_keys=[assigned_by])

class Permission(SQLModel, table=True):
    """Permission definition model."""
    
    __tablename__ = "permissions"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    # Permission definition
    name: str = Field(unique=True, index=True, description="Permission name")
    category: PermissionCategory = Field(description="Permission category")
    description: Optional[str] = Field(default=None, description="Permission description")
    
    # Permission metadata
    resource_type: Optional[str] = Field(default=None, description="Resource type this permission applies to")
    action: Optional[str] = Field(default=None, description="Action this permission allows")
    conditions: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Status
    is_active: bool = Field(default=True, description="Permission is active")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class AuditLog(SQLModel, table=True):
    """Comprehensive audit log model."""
    
    __tablename__ = "audit_logs"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", index=True)
    
    # User and session information
    user_id: Optional[uuid.UUID] = Field(foreign_key="users.id", default=None, index=True)
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    user_role: Optional[str] = Field(default=None, description="User role at time of action")
    
    # Action details
    action: AuditAction = Field(description="Action performed")
    resource_type: str = Field(description="Type of resource affected")
    resource_id: Optional[uuid.UUID] = Field(default=None, description="ID of resource affected")
    
    # Request details
    endpoint: str = Field(description="API endpoint accessed")
    method: str = Field(description="HTTP method")
    status_code: Optional[int] = Field(default=None, description="HTTP status code")
    
    # Data changes
    old_values: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    new_values: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Security and context
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    severity: AuditSeverity = Field(default=AuditSeverity.MEDIUM, description="Audit severity")
    
    # Additional metadata
    security_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    tags: Optional[List[str]] = Field(default=None, sa_column_kwargs={"type_": "JSONB"})
    
    # Compliance
    retention_until: Optional[datetime] = Field(default=None, description="Data retention expiry")
    is_sensitive: bool = Field(default=False, description="Contains sensitive data")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    clinic: Optional["Clinic"] = Relationship()
    user: Optional["User"] = Relationship()

# Pydantic schemas for API
class TwoFASetupRequest(SQLModel):
    """Request schema for 2FA setup."""
    pass

class TwoFASetupResponse(SQLModel):
    """Response schema for 2FA setup."""
    qr_code_url: str = Field(description="QR code provisioning URI")
    secret_key: str = Field(description="Secret key for manual entry")
    backup_codes: List[str] = Field(description="Backup codes for recovery")
    setup_token: str = Field(description="Token for verification step")

class TwoFAVerifyRequest(SQLModel):
    """Request schema for 2FA verification."""
    token: str = Field(description="TOTP token")
    setup_token: Optional[str] = Field(default=None, description="Setup token for initial verification")

class TwoFAVerifyResponse(SQLModel):
    """Response schema for 2FA verification."""
    success: bool = Field(description="Verification success")
    message: str = Field(description="Response message")
    backup_codes: Optional[List[str]] = Field(default=None, description="Backup codes if first verification")

class TwoFADisableRequest(SQLModel):
    """Request schema for 2FA disable."""
    token: str = Field(description="Current TOTP token")
    password: str = Field(description="User password for confirmation")

class RoleCreateRequest(SQLModel):
    """Request schema for role creation."""
    name: str = Field(description="Role name")
    description: Optional[str] = Field(default=None, description="Role description")
    permissions: List[str] = Field(description="List of permissions")

class RoleResponse(SQLModel):
    """Response schema for role."""
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    permissions: List[str]
    is_system_role: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

class UserRoleAssignRequest(SQLModel):
    """Request schema for user role assignment."""
    user_id: uuid.UUID = Field(description="User ID")
    role_id: uuid.UUID = Field(description="Role ID")
    expires_at: Optional[datetime] = Field(default=None, description="Role expiration")
    reason: Optional[str] = Field(default=None, description="Assignment reason")

class AuditLogResponse(SQLModel):
    """Response schema for audit log."""
    id: uuid.UUID
    clinic_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action: AuditAction
    resource_type: str
    resource_id: Optional[uuid.UUID] = None
    endpoint: str
    method: str
    status_code: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    severity: AuditSeverity
    audit_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

# Utility classes
class TwoFAManager:
    """Utility class for 2FA management."""
    
    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret."""
        import secrets
        return secrets.token_hex(20)
    
    @staticmethod
    def generate_qr_url(secret: str, user_email: str, issuer: str = "Prontivus") -> str:
        """Generate QR code provisioning URL."""
        return f"otpauth://totp/{issuer}:{user_email}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """Generate backup codes."""
        import secrets
        return [secrets.token_hex(4).upper() for _ in range(count)]
    
    @staticmethod
    def verify_totp_token(secret: str, token: str, window: int = 1) -> bool:
        """Verify TOTP token."""
        try:
            import pyotp
            totp = pyotp.TOTP(secret)
            return totp.verify(token, valid_window=window)
        except Exception:
            return False
    
    @staticmethod
    def encrypt_secret(secret: str, key: str) -> str:
        """Encrypt secret for storage."""
        from cryptography.fernet import Fernet
        f = Fernet(key.encode())
        return f.encrypt(secret.encode()).decode()
    
    @staticmethod
    def decrypt_secret(encrypted_secret: str, key: str) -> str:
        """Decrypt secret for use."""
        from cryptography.fernet import Fernet
        f = Fernet(key.encode())
        return f.decrypt(encrypted_secret.encode()).decode()

class RBACManager:
    """Utility class for RBAC management."""
    
    # System permissions
    SYSTEM_PERMISSIONS = {
        # User Management
        "users.create": {"category": PermissionCategory.USER_MANAGEMENT, "description": "Create users"},
        "users.read": {"category": PermissionCategory.USER_MANAGEMENT, "description": "Read user information"},
        "users.update": {"category": PermissionCategory.USER_MANAGEMENT, "description": "Update user information"},
        "users.delete": {"category": PermissionCategory.USER_MANAGEMENT, "description": "Delete users"},
        
        # Patient Management
        "patients.create": {"category": PermissionCategory.PATIENT_MANAGEMENT, "description": "Create patients"},
        "patients.read": {"category": PermissionCategory.PATIENT_MANAGEMENT, "description": "Read patient information"},
        "patients.update": {"category": PermissionCategory.PATIENT_MANAGEMENT, "description": "Update patient information"},
        "patients.delete": {"category": PermissionCategory.PATIENT_MANAGEMENT, "description": "Delete patients"},
        
        # Medical Records
        "medical_records.create": {"category": PermissionCategory.MEDICAL_RECORDS, "description": "Create medical records"},
        "medical_records.read": {"category": PermissionCategory.MEDICAL_RECORDS, "description": "Read medical records"},
        "medical_records.update": {"category": PermissionCategory.MEDICAL_RECORDS, "description": "Update medical records"},
        "medical_records.delete": {"category": PermissionCategory.MEDICAL_RECORDS, "description": "Delete medical records"},
        
        # System Administration
        "system.admin": {"category": PermissionCategory.SYSTEM_ADMIN, "description": "System administration"},
        "audit_logs.read": {"category": PermissionCategory.AUDIT_LOGS, "description": "Read audit logs"},
        "licenses.manage": {"category": PermissionCategory.LICENSES, "description": "Manage licenses"},
    }
    
    # Default roles
    DEFAULT_ROLES = {
        "superadmin": {
            "description": "Super administrator with all permissions",
            "permissions": list(SYSTEM_PERMISSIONS.keys()),
            "is_system_role": True
        },
        "admin": {
            "description": "Clinic administrator",
            "permissions": [
                "users.create", "users.read", "users.update",
                "patients.create", "patients.read", "patients.update", "patients.delete",
                "medical_records.create", "medical_records.read", "medical_records.update",
                "audit_logs.read"
            ],
            "is_system_role": True
        },
        "doctor": {
            "description": "Medical doctor",
            "permissions": [
                "patients.read", "patients.update",
                "medical_records.create", "medical_records.read", "medical_records.update"
            ],
            "is_system_role": True
        },
        "receptionist": {
            "description": "Reception staff",
            "permissions": [
                "patients.create", "patients.read", "patients.update"
            ],
            "is_system_role": True
        },
        "patient": {
            "description": "Patient user",
            "permissions": [
                "patients.read"  # Can only read their own data
            ],
            "is_system_role": True
        }
    }
    
    @staticmethod
    def get_user_permissions(user_roles: List[Role]) -> List[str]:
        """Get all permissions for a user based on their roles."""
        permissions = set()
        for role in user_roles:
            if role.is_active:
                permissions.update(role.permissions)
        return list(permissions)
    
    @staticmethod
    def has_permission(user_permissions: List[str], required_permission: str) -> bool:
        """Check if user has required permission."""
        return required_permission in user_permissions
    
    @staticmethod
    def check_resource_access(user_permissions: List[str], resource_type: str, action: str) -> bool:
        """Check if user can perform action on resource type."""
        permission = f"{resource_type}.{action}"
        return RBACManager.has_permission(user_permissions, permission)

class AuditManager:
    """Utility class for audit management."""
    
    # Sensitive fields that should be redacted
    SENSITIVE_FIELDS = {
        "password", "password_hash", "twofa_secret", "secret_encrypted",
        "api_key", "access_token", "refresh_token", "private_key",
        "ssn", "cpf", "credit_card", "bank_account"
    }
    
    # High-severity actions
    HIGH_SEVERITY_ACTIONS = {
        AuditAction.DELETE, AuditAction.TWOFA_SETUP, AuditAction.TWOFA_DISABLE,
        AuditAction.PERMISSION_GRANT, AuditAction.PERMISSION_REVOKE,
        AuditAction.FORCE_UNLOCK, AuditAction.EXPORT_DATA
    }
    
    @staticmethod
    def redact_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields from data."""
        if not data:
            return data
        
        redacted = {}
        for key, value in data.items():
            if key.lower() in AuditManager.SENSITIVE_FIELDS:
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = AuditManager.redact_sensitive_data(value)
            elif isinstance(value, list):
                redacted[key] = [
                    AuditManager.redact_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted
    
    @staticmethod
    def determine_severity(action: AuditAction, resource_type: str) -> AuditSeverity:
        """Determine audit severity based on action and resource."""
        if action in AuditManager.HIGH_SEVERITY_ACTIONS:
            return AuditSeverity.HIGH
        
        if action == AuditAction.UPDATE and resource_type in ["users", "roles", "permissions"]:
            return AuditSeverity.MEDIUM
        
        if action == AuditAction.CREATE and resource_type in ["medical_records", "prescriptions"]:
            return AuditSeverity.MEDIUM
        
        return AuditSeverity.LOW
    
    @staticmethod
    def is_sensitive_resource(resource_type: str) -> bool:
        """Check if resource type contains sensitive data."""
        sensitive_resources = {
            "users", "twofa_secrets", "audit_logs", "licenses",
            "medical_records", "prescriptions"
        }
        return resource_type in sensitive_resources
