"""
Team management API endpoints for user roles and permissions.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_

from app.db.session import get_db_session
from app.models.database import User
from app.api.v1.auth import get_current_user
from pydantic import BaseModel, EmailStr

router = APIRouter()

# Pydantic models for team management
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str
    crm: Optional[str] = None
    phone: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    crm: Optional[str] = None
    phone: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    crm: Optional[str] = None
    phone: Optional[str] = None
    permissions: Dict[str, Any]
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    size: int

# Role definitions
ROLES = {
    "administrador": {
        "name": "Administrador",
        "description": "Acesso completo ao sistema",
        "permissions": {
            "can_view_patients": True,
            "can_edit_patients": True,
            "can_view_appointments": True,
            "can_edit_appointments": True,
            "can_view_consultations": True,
            "can_edit_consultations": True,
            "can_view_reports": True,
            "can_manage_users": True,
            "can_manage_settings": True
        }
    },
    "medico": {
        "name": "Médico",
        "description": "Acesso ao atendimento e prontuário",
        "permissions": {
            "can_view_patients": True,
            "can_edit_patients": True,
            "can_view_appointments": True,
            "can_edit_appointments": True,
            "can_view_consultations": True,
            "can_edit_consultations": True,
            "can_view_reports": True,
            "can_manage_users": False,
            "can_manage_settings": False
        }
    },
    "secretaria": {
        "name": "Secretária",
        "description": "Acesso à agenda, pacientes e fila",
        "permissions": {
            "can_view_patients": True,
            "can_edit_patients": True,
            "can_view_appointments": True,
            "can_edit_appointments": True,
            "can_view_consultations": False,
            "can_edit_consultations": False,
            "can_view_reports": True,
            "can_manage_users": False,
            "can_manage_settings": False
        }
    },
    "financeiro": {
        "name": "Financeiro",
        "description": "Acesso a relatórios e cobranças",
        "permissions": {
            "can_view_patients": True,
            "can_edit_patients": False,
            "can_view_appointments": True,
            "can_edit_appointments": False,
            "can_view_consultations": False,
            "can_edit_consultations": False,
            "can_view_reports": True,
            "can_manage_users": False,
            "can_manage_settings": False
        }
    }
}

def check_admin_permission(current_user: User) -> None:
    """Check if current user has admin permissions."""
    if current_user.role != "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas administradores podem gerenciar usuários."
        )

@router.get("/team/roles", response_model=Dict[str, Any])
async def get_available_roles():
    """Get available user roles and their permissions."""
    return ROLES

@router.get("/team/users", response_model=UserListResponse)
async def get_team_users(
    page: int = 1,
    size: int = 20,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get list of team users with filtering and pagination."""
    check_admin_permission(current_user)
    
    # Build query
    query = select(User).where(User.clinic_id == current_user.clinic_id)
    
    # Apply filters
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        query = query.where(
            User.name.ilike(f"%{search}%") | 
            User.email.ilike(f"%{search}%")
        )
    
    # Get total count
    count_query = select(User).where(User.clinic_id == current_user.clinic_id)
    if role:
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        count_query = count_query.where(User.is_active == is_active)
    if search:
        count_query = count_query.where(
            User.name.ilike(f"%{search}%") | 
            User.email.ilike(f"%{search}%")
        )
    
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(User.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Convert to response format
    user_responses = []
    for user in users:
        user_responses.append(UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role or "medico",
            crm=user.crm,
            phone=user.phone,
            permissions=user.permissions or {},
            is_active=user.is_active if user.is_active is not None else True,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at,
            created_by=user.created_by,
            updated_by=user.updated_by
        ))
    
    return UserListResponse(
        users=user_responses,
        total=total,
        page=page,
        size=size
    )

@router.post("/team/users", response_model=UserResponse)
async def create_team_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new team user."""
    check_admin_permission(current_user)
    
    # Validate role
    if user_data.role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role inválida. Roles disponíveis: {', '.join(ROLES.keys())}"
        )
    
    # Check if email already exists
    existing_user = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já está em uso"
        )
    
    # Get default permissions for role
    default_permissions = ROLES[user_data.role]["permissions"]
    if user_data.permissions:
        default_permissions.update(user_data.permissions)
    
    # Create user
    from app.core.security import get_password_hash
    
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role,
        crm=user_data.crm,
        phone=user_data.phone,
        permissions=default_permissions,
        clinic_id=current_user.clinic_id,
        is_active=True,
        created_by=current_user.id,
        updated_by=current_user.id,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        role=new_user.role,
        crm=new_user.crm,
        phone=new_user.phone,
        permissions=new_user.permissions or {},
        is_active=new_user.is_active,
        last_login=new_user.last_login,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        created_by=new_user.created_by,
        updated_by=new_user.updated_by
    )

@router.patch("/team/users/{user_id}", response_model=UserResponse)
async def update_team_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update a team user."""
    check_admin_permission(current_user)
    
    # Get user
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.clinic_id == current_user.clinic_id
            )
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Validate role if provided
    if user_data.role and user_data.role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role inválida. Roles disponíveis: {', '.join(ROLES.keys())}"
        )
    
    # Check email uniqueness if changing email
    if user_data.email and user_data.email != user.email:
        existing_user = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já está em uso"
            )
    
    # Update user fields
    update_data = user_data.model_dump(exclude_unset=True)
    
    # Handle permissions update
    if user_data.permissions is not None:
        if user_data.role:
            # Merge with default permissions for the role
            default_permissions = ROLES[user_data.role]["permissions"]
            default_permissions.update(user_data.permissions)
            update_data["permissions"] = default_permissions
        else:
            # Keep current role permissions and merge with provided permissions
            current_permissions = user.permissions or {}
            current_permissions.update(user_data.permissions)
            update_data["permissions"] = current_permissions
    
    # Update fields
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_by = current_user.id
    user.updated_at = datetime.now()
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        crm=user.crm,
        phone=user.phone,
        permissions=user.permissions or {},
        is_active=user.is_active,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
        created_by=user.created_by,
        updated_by=user.updated_by
    )

@router.delete("/team/users/{user_id}")
async def delete_team_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a team user (soft delete by setting is_active to False)."""
    check_admin_permission(current_user)
    
    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode excluir sua própria conta"
        )
    
    # Get user
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.clinic_id == current_user.clinic_id
            )
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Soft delete by setting is_active to False
    user.is_active = False
    user.updated_by = current_user.id
    user.updated_at = datetime.now()
    
    await db.commit()
    
    return {"message": "Usuário excluído com sucesso"}

@router.post("/team/users/{user_id}/activate")
async def activate_team_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Activate a team user."""
    check_admin_permission(current_user)
    
    # Get user
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.clinic_id == current_user.clinic_id
            )
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    user.is_active = True
    user.updated_by = current_user.id
    user.updated_at = datetime.now()
    
    await db.commit()
    
    return {"message": "Usuário ativado com sucesso"}
