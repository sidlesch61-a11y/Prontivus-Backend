"""
Core database models for Prontivus medical SaaS.
"""

import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from sqlalchemy import String, Text, Boolean, DateTime, Date, Numeric, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import BaseModel, TenantModel

# Import main models from database.py to avoid duplicates
from app.models.database import (
    User,
    Clinic, 
    Patient,
    Appointment,
    MedicalRecord,
    Consultation,
    File,
    Invoice,
    License,
    AuditLog
)

# PrintLog is already imported from print_models in database.py

# Define enums that are used across the application
from enum import Enum

class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    DOCTOR = "doctor"
    SECRETARY = "secretary"
    PATIENT = "patient"

class ClinicStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class InvoiceStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"

class ActivationStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

class AppointmentSource(str, Enum):
    MANUAL = "manual"
    WEB = "web"
    MOBILE = "mobile"
    PHONE = "phone"

class MedicalRecordType(str, Enum):
    CONSULTATION = "consultation"
    EXAM = "exam"
    PRESCRIPTION = "prescription"
    REFERRAL = "referral"

class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    PIX = "pix"
    BANK_TRANSFER = "bank_transfer"
    INSURANCE = "insurance"

class LicenseStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"

# Import 2FA models
from app.models.two_fa import (
    TwoFASecret,
    TwoFAStatus,
    SecuritySettings,
    LoginAttempt
)

# Re-export for backwards compatibility
__all__ = [
    "User",
    "Clinic",
    "Patient",
    "Appointment",
    "MedicalRecord",
    "Consultation",
    "File",
    "Invoice",
    "License",
    "AuditLog",
    "UserRole",
    "ClinicStatus",
    "AppointmentStatus",
    "AppointmentSource",
    "MedicalRecordType",
    "InvoiceStatus",
    "PaymentMethod",
    "LicenseStatus",
    "ActivationStatus",
    "BaseModel",
    "TenantModel",
    "TwoFASecret",
    "TwoFAStatus",
    "SecuritySettings",
    "LoginAttempt"
]