"""
User management schemas for RBAC system.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    """User roles enum."""
    ADMIN = "admin"
    MEDICO = "medico"
    SECRETARIA = "secretaria"
    FINANCEIRO = "financeiro"

class UserCreate(BaseModel):
    """Schema for creating a new user."""
    
    name: str = Field(..., min_length=2, max_length=255, description="Nome completo do usuário")
    email: EmailStr = Field(..., description="Email do usuário")
    password: str = Field(..., min_length=8, description="Senha temporária")
    role: UserRole = Field(..., description="Função do usuário")
    permissions: Optional[Dict[str, Any]] = Field(default={}, description="Permissões específicas")

class UserUpdate(BaseModel):
    """Schema for updating a user."""
    
    name: Optional[str] = Field(None, min_length=2, max_length=255, description="Nome completo do usuário")
    role: Optional[UserRole] = Field(None, description="Função do usuário")
    permissions: Optional[Dict[str, Any]] = Field(None, description="Permissões específicas")
    is_active: Optional[bool] = Field(None, description="Status ativo/inativo")

class UserResponse(BaseModel):
    """Schema for user response."""
    
    id: str
    name: str
    email: str
    role: str
    permissions: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    clinic_id: str

class TeamMember(BaseModel):
    """Schema for team member display."""
    
    id: str
    name: str
    email: str
    role: str
    role_display_name: str
    permissions: List[str]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

class RoleInfo(BaseModel):
    """Schema for role information."""
    
    name: str
    display_name: str
    description: str
    permissions: List[str]

class PermissionInfo(BaseModel):
    """Schema for permission information."""
    
    name: str
    display_name: str
    description: str
    category: str
