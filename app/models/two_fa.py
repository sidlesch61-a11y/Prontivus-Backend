"""
Two-Factor Authentication Models
"""

import uuid
from datetime import datetime
from typing import Optional, List
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Text, ARRAY, String


class TwoFAStatus(str, Enum):
    """2FA status enumeration."""
    PENDING = "pending"
    ENABLED = "enabled"
    DISABLED = "disabled"


class TwoFASecret(SQLModel, table=True):
    """Two-factor authentication secrets table."""
    __tablename__ = "two_fa_secrets"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", unique=True)
    secret_encrypted: str = Field(description="Encrypted TOTP secret")
    status: str = Field(default=TwoFAStatus.PENDING)
    backup_codes_encrypted: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    enabled_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    failed_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None


class SecuritySettings(SQLModel, table=True):
    """Clinic-wide security settings."""
    __tablename__ = "security_settings"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = Field(foreign_key="clinics.id", unique=True)
    require_2fa_for_roles: List[str] = Field(
        default=["admin", "doctor", "superadmin"],
        sa_column=Column(ARRAY(String))
    )
    session_timeout_minutes: int = Field(default=60)
    max_login_attempts: int = Field(default=5)
    lockout_duration_minutes: int = Field(default=15)
    password_min_length: int = Field(default=8)
    password_require_special: bool = Field(default=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")


class LoginAttempt(SQLModel, table=True):
    """Login attempt tracking."""
    __tablename__ = "login_attempts"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    email: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool
    failure_reason: Optional[str] = None
    attempted_at: datetime = Field(default_factory=datetime.utcnow)


# Pydantic schemas for API
class TwoFASetupRequest(SQLModel):
    """Request to setup 2FA."""
    pass  # No input needed, will generate secret


class TwoFASetupResponse(SQLModel):
    """Response with 2FA setup information."""
    secret: str  # Base32 encoded secret for user
    qr_code_data: str  # Data URI for QR code image
    backup_codes: List[str]  # One-time backup codes


class TwoFAVerifyRequest(SQLModel):
    """Request to verify 2FA code."""
    code: str = Field(min_length=6, max_length=6, description="6-digit TOTP code")


class TwoFAVerifyResponse(SQLModel):
    """Response after 2FA verification."""
    verified: bool
    message: str


class TwoFADisableRequest(SQLModel):
    """Request to disable 2FA."""
    password: str = Field(description="User password for confirmation")
    code: str = Field(min_length=6, max_length=6, description="Current 2FA code")


class TwoFAStatusResponse(SQLModel):
    """2FA status for a user."""
    enabled: bool
    status: str
    enabled_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

