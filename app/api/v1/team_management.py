"""
Team management API endpoints for Prontivus.
Handles user role management and team administration.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from pydantic import BaseModel, EmailStr

from app.core.auth import get_current_user, require_admin
from app.db.session import get_db_session
from app.models import User, Clinic, AuditLog

router = APIRouter()


# Use the proper require_admin dependency from auth module


class UserCreateRequest(BaseModel):
    """User creation request schema."""
    name: str
    email: EmailStr
    password: str
    role: str
    permissions: Optional[Dict[str, Any]] = None
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    """User update request schema."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """User response schema."""
    id: str
    name: str
    email: str
    role: str
    permissions: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    clinic_name: Optional[str] = None


class TeamManagementResponse(BaseModel):
    """Team management response schema."""
    success: bool
    message: str
    user_id: Optional[str] = None


@router.get("/", response_model=List[UserResponse])
async def get_team_members(
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all team members for the current clinic."""
    try:
        # Get all users in the current clinic
        users_result = await db.execute(
            select(User).where(
                User.clinic_id == current_user.clinic_id
            ).order_by(User.created_at.desc())
        )
        users = users_result.scalars().all()
        
        # Get clinic name
        clinic_result = await db.execute(
            select(Clinic.name).where(Clinic.id == current_user.clinic_id)
        )
        clinic_name = clinic_result.scalar_one_or_none()
        
        # Format response
        team_members = []
        for user in users:
            team_members.append(UserResponse(
                id=str(user.id),
                name=user.name,
                email=user.email,
                role=getattr(user, 'role', 'secretary'),  # Default role if not set
                permissions=getattr(user, 'permissions', {}),
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
                clinic_name=clinic_name
            ))
        
        return team_members
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar membros da equipe: {str(e)}"
        )


@router.post("/", response_model=TeamManagementResponse)
async def create_team_member(
    request: UserCreateRequest,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new team member."""
    try:
        # Validate role
        valid_roles = ["admin", "doctor", "secretary", "financeiro"]
        if request.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Função inválida. Funções válidas: {', '.join(valid_roles)}"
            )
        
        # Check if email already exists in clinic
        existing_user_result = await db.execute(
            select(User).where(
                User.email == request.email,
                User.clinic_id == current_user.clinic_id
            )
        )
        existing_user = existing_user_result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Já existe um usuário com este e-mail nesta clínica"
            )
        
        # Hash password
        from app.core.security import get_password_hash
        password_hash = get_password_hash(request.password)
        
        # Create user
        user = User(
            id=uuid.uuid4(),
            clinic_id=current_user.clinic_id,
            name=request.name,
            email=request.email,
            password_hash=password_hash,
            role=request.role,
            permissions=request.permissions or {},
            is_active=request.is_active,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="user_created",
            entity="user",
            entity_id=str(user.id),
            details={
                "new_user_name": user.name,
                "new_user_email": user.email,
                "new_user_role": user.role,
                "created_by": current_user.name
            }
        )
        db.add(audit_log)
        await db.commit()
        
        return TeamManagementResponse(
            success=True,
            message=f"Usuário {user.name} criado com sucesso",
            user_id=str(user.id)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar usuário: {str(e)}"
        )


@router.patch("/{user_id}", response_model=TeamManagementResponse)
async def update_team_member(
    user_id: str,
    request: UserUpdateRequest,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Update a team member."""
    try:
        # Get user
        user_result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.clinic_id == current_user.clinic_id
            )
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        
        # Prevent admin from modifying themselves
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você não pode modificar seu próprio usuário"
            )
        
        # Validate role if provided
        if request.role:
            valid_roles = ["admin", "doctor", "secretary", "financeiro"]
            if request.role not in valid_roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Função inválida. Funções válidas: {', '.join(valid_roles)}"
                )
        
        # Check email uniqueness if provided
        if request.email and request.email != user.email:
            existing_user_result = await db.execute(
                select(User).where(
                    User.email == request.email,
                    User.clinic_id == current_user.clinic_id,
                    User.id != user_id
                )
            )
            existing_user = existing_user_result.scalar_one_or_none()
            
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Já existe um usuário com este e-mail nesta clínica"
                )
        
        # Update user fields
        update_data = request.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        user.updated_at = datetime.now()
        
        await db.commit()
        await db.refresh(user)
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="user_updated",
            entity="user",
            entity_id=str(user.id),
            details={
                "updated_user_name": user.name,
                "updated_fields": list(update_data.keys()),
                "updated_by": current_user.name
            }
        )
        db.add(audit_log)
        await db.commit()
        
        return TeamManagementResponse(
            success=True,
            message=f"Usuário {user.name} atualizado com sucesso",
            user_id=str(user.id)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar usuário: {str(e)}"
        )


@router.delete("/{user_id}", response_model=TeamManagementResponse)
async def delete_team_member(
    user_id: str,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a team member."""
    try:
        # Get user
        user_result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.clinic_id == current_user.clinic_id
            )
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        
        # Prevent admin from deleting themselves
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você não pode excluir seu próprio usuário"
            )
        
        # Store user name for audit log
        user_name = user.name
        
        # Delete user
        await db.execute(
            delete(User).where(User.id == user_id)
        )
        await db.commit()
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="user_deleted",
            entity="user",
            entity_id=user_id,
            details={
                "deleted_user_name": user_name,
                "deleted_by": current_user.name
            }
        )
        db.add(audit_log)
        await db.commit()
        
        return TeamManagementResponse(
            success=True,
            message=f"Usuário {user_name} excluído com sucesso",
            user_id=user_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao excluir usuário: {str(e)}"
        )


@router.get("/roles")
async def get_available_roles(
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session)
):
    """Get available user roles and their permissions."""
    roles = {
        "admin": {
            "name": "Administrador",
            "description": "Acesso completo ao sistema",
            "permissions": [
                "users.read", "users.write", "patients.read", "patients.write",
                "appointments.read", "appointments.write", "medical_records.read", "medical_records.write",
                "billing.read", "billing.write", "settings.read", "settings.write"
            ]
        },
        "doctor": {
            "name": "Médico",
            "description": "Acesso ao atendimento e prontuário",
            "permissions": [
                "patients.read", "patients.write", "appointments.read", "appointments.write",
                "medical_records.read", "medical_records.write", "consultations.read", "consultations.write"
            ]
        },
        "secretary": {
            "name": "Secretária",
            "description": "Acesso à agenda, pacientes e fila",
            "permissions": [
                "patients.read", "patients.write", "appointments.read", "appointments.write",
                "queue.read", "queue.write"
            ]
        },
        "financeiro": {
            "name": "Financeiro",
            "description": "Acesso a relatórios e cobranças",
            "permissions": [
                "billing.read", "billing.write", "reports.read", "invoices.read", "invoices.write"
            ]
        }
    }
    
    return roles