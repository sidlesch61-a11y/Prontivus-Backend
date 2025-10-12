"""
Enhanced Security Configuration for Prontivus Medical System
Implements "Secure & Simple" best practices
"""

from typing import Dict, List, Set
from enum import Enum


class UserRole(str, Enum):
    """User roles with clear hierarchy."""
    SUPERADMIN = "superadmin"  # Level 5
    ADMIN = "admin"             # Level 4
    DOCTOR = "doctor"           # Level 3
    SECRETARY = "secretary"     # Level 2
    PATIENT = "patient"         # Level 1


class SecurityPolicy:
    """Security policies per role."""
    
    # 2FA Requirements
    REQUIRE_2FA_ROLES: Set[str] = {
        UserRole.SUPERADMIN,
        UserRole.ADMIN,
        UserRole.DOCTOR,
    }
    
    RECOMMEND_2FA_ROLES: Set[str] = {
        UserRole.SECRETARY,
    }
    
    # Session timeouts (in minutes)
    SESSION_TIMEOUT = {
        UserRole.SUPERADMIN: 30,
        UserRole.ADMIN: 60,
        UserRole.DOCTOR: 120,
        UserRole.SECRETARY: 240,
        UserRole.PATIENT: 480,  # 8 hours for patient portal
    }
    
    # Password requirements
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_NUMBERS = True
    PASSWORD_REQUIRE_SPECIAL = True
    
    # Account lockout
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    
    # Ethical locks (medical records)
    ETHICAL_LOCK_TIMEOUT_MINUTES = 30
    ETHICAL_LOCK_ROLES = {UserRole.DOCTOR, UserRole.ADMIN}
    
    @staticmethod
    def requires_2fa(role: str) -> bool:
        """Check if role requires 2FA."""
        return role.lower() in [r.value.lower() for r in SecurityPolicy.REQUIRE_2FA_ROLES]
    
    @staticmethod
    def get_session_timeout(role: str) -> int:
        """Get session timeout for role."""
        role_enum = UserRole(role.lower())
        return SecurityPolicy.SESSION_TIMEOUT.get(role_enum, 60)


class RolePermissions:
    """
    Permission mapping for each role.
    Format: "resource.action"
    
    Actions: read, write, delete, manage
    """
    
    # Define all available permissions
    ALL_PERMISSIONS = {
        # Patients
        "patients.read",
        "patients.write",
        "patients.delete",
        
        # Appointments
        "appointments.read",
        "appointments.write",
        "appointments.delete",
        "appointments.manage",  # Includes calendar management
        
        # Medical Records
        "medical_records.read",
        "medical_records.write",
        "medical_records.delete",
        "medical_records.lock",  # Ethical locks
        
        # Prescriptions
        "prescriptions.read",
        "prescriptions.write",
        "prescriptions.sign",
        
        # Billing
        "billing.read",
        "billing.write",
        "billing.process",  # Process payments
        
        # Users
        "users.read",
        "users.write",
        "users.delete",
        "users.manage_roles",
        
        # Settings
        "settings.read",
        "settings.write",
        
        # Files
        "files.read",
        "files.write",
        "files.delete",
        
        # Reports
        "reports.read",
        "reports.export",
        
        # Audit Logs
        "audit.read",
        
        # Telemedicine
        "telemedicine.access",
        "telemedicine.conduct",
        
        # AI Features
        "ai.consultation",
        "ai.transcription",
        
        # TISS
        "tiss.read",
        "tiss.submit",
    }
    
    # Permissions by role
    ROLE_PERMISSIONS: Dict[str, Set[str]] = {
        # SUPERADMIN - Full access to everything
        UserRole.SUPERADMIN: ALL_PERMISSIONS,
        
        # ADMIN - Full clinic management
        UserRole.ADMIN: {
            "patients.read",
            "patients.write",
            "patients.delete",
            "appointments.read",
            "appointments.write",
            "appointments.delete",
            "appointments.manage",
            "medical_records.read",
            "medical_records.write",
            "medical_records.lock",
            "prescriptions.read",
            "prescriptions.write",
            "prescriptions.sign",
            "billing.read",
            "billing.write",
            "billing.process",
            "users.read",
            "users.write",
            "users.delete",
            "users.manage_roles",
            "settings.read",
            "settings.write",
            "files.read",
            "files.write",
            "files.delete",
            "reports.read",
            "reports.export",
            "audit.read",
            "telemedicine.access",
            "telemedicine.conduct",
            "ai.consultation",
            "ai.transcription",
            "tiss.read",
            "tiss.submit",
        },
        
        # DOCTOR - Medical care focus
        UserRole.DOCTOR: {
            "patients.read",
            "patients.write",
            "appointments.read",
            "appointments.write",
            "appointments.manage",
            "medical_records.read",
            "medical_records.write",
            "medical_records.lock",
            "prescriptions.read",
            "prescriptions.write",
            "prescriptions.sign",
            "billing.read",  # View only
            "files.read",
            "files.write",
            "reports.read",
            "telemedicine.access",
            "telemedicine.conduct",
            "ai.consultation",
            "ai.transcription",
            "tiss.read",
            "tiss.submit",
        },
        
        # SECRETARY - Administrative support
        UserRole.SECRETARY: {
            "patients.read",
            "patients.write",
            "appointments.read",
            "appointments.write",
            "appointments.manage",
            "billing.read",  # View only
            "files.read",
            "files.write",
        },
        
        # PATIENT - Self-service portal
        UserRole.PATIENT: {
            "patients.read",  # Own data only
            "appointments.read",  # Own appointments only
            "medical_records.read",  # Own records only (if shared)
            "prescriptions.read",  # Own prescriptions only
            "billing.read",  # Own invoices only
            "files.read",  # Own files only
        },
    }
    
    @staticmethod
    def get_permissions(role: str) -> Set[str]:
        """Get all permissions for a role."""
        role_enum = UserRole(role.lower())
        return RolePermissions.ROLE_PERMISSIONS.get(role_enum, set())
    
    @staticmethod
    def has_permission(role: str, permission: str) -> bool:
        """Check if role has specific permission."""
        return permission in RolePermissions.get_permissions(role)
    
    @staticmethod
    def check_permission(role: str, resource: str, action: str) -> bool:
        """Check if role can perform action on resource."""
        permission = f"{resource}.{action}"
        return RolePermissions.has_permission(role, permission)


class RoleHierarchy:
    """Role hierarchy and level-based access."""
    
    ROLE_LEVELS = {
        UserRole.SUPERADMIN: 5,
        UserRole.ADMIN: 4,
        UserRole.DOCTOR: 3,
        UserRole.SECRETARY: 2,
        UserRole.PATIENT: 1,
    }
    
    @staticmethod
    def get_level(role: str) -> int:
        """Get numeric level for role."""
        try:
            role_enum = UserRole(role.lower())
            return RoleHierarchy.ROLE_LEVELS.get(role_enum, 0)
        except ValueError:
            return 0
    
    @staticmethod
    def can_access_role(user_role: str, required_role: str) -> bool:
        """Check if user role meets or exceeds required role."""
        user_level = RoleHierarchy.get_level(user_role)
        required_level = RoleHierarchy.get_level(required_role)
        return user_level >= required_level
    
    @staticmethod
    def get_subordinate_roles(role: str) -> List[str]:
        """Get all roles below this role in hierarchy."""
        user_level = RoleHierarchy.get_level(role)
        return [
            r.value for r, level in RoleHierarchy.ROLE_LEVELS.items()
            if level < user_level
        ]


class DataAccessRules:
    """Rules for data access by role."""
    
    @staticmethod
    def can_access_patient_data(user_role: str, user_id: str, patient_id: str, 
                                is_own_data: bool = False) -> bool:
        """Check if user can access patient data."""
        role = user_role.lower()
        
        # Patients can only access own data
        if role == UserRole.PATIENT:
            return is_own_data
        
        # Staff can access all patients in their clinic
        if role in [UserRole.SECRETARY, UserRole.DOCTOR, UserRole.ADMIN, UserRole.SUPERADMIN]:
            return True
        
        return False
    
    @staticmethod
    def can_access_medical_records(user_role: str, is_own_data: bool = False) -> bool:
        """Check if user can access medical records."""
        role = user_role.lower()
        
        # Only doctors and admins can access medical records
        if role in [UserRole.DOCTOR, UserRole.ADMIN, UserRole.SUPERADMIN]:
            return True
        
        # Patients can view their own records if shared
        if role == UserRole.PATIENT and is_own_data:
            return True
        
        return False
    
    @staticmethod
    def can_modify_billing(user_role: str) -> bool:
        """Check if user can modify billing data."""
        role = user_role.lower()
        return role in [UserRole.ADMIN, UserRole.SUPERADMIN]
    
    @staticmethod
    def can_manage_users(user_role: str) -> bool:
        """Check if user can manage other users."""
        role = user_role.lower()
        return role in [UserRole.ADMIN, UserRole.SUPERADMIN]


# Export configuration
__all__ = [
    "UserRole",
    "SecurityPolicy",
    "RolePermissions",
    "RoleHierarchy",
    "DataAccessRules",
]

