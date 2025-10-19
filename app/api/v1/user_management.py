"""
User Management API endpoints for RBAC system.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime
import uuid

from app.core.auth import get_current_user, require_admin_access
from app.db.session import get_db_session
from app.models import User, Clinic
from app.schemas import UserCreate, UserUpdate, UserResponse, UserRole

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_admin_access),
    db: AsyncSession = Depends(get_db_session)
):
    """
    List all users in the clinic with role information.
    """
    try:
        offset = (page - 1) * size
        
        users_result = await db.execute(
            select(User)
            .where(User.clinic_id == current_user.clinic_id)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        
        users = users_result.scalars().all()
        
        # Get total count
        count_result = await db.execute(
            select(User).where(User.clinic_id == current_user.clinic_id)
        )
        total = len(count_result.scalars().all())
        
        return [
            UserResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                role=getattr(user, 'role', 'user'),
                permissions=getattr(user, 'permissions', {}),
                is_active=getattr(user, 'is_active', True),
                created_at=user.created_at,
                updated_at=user.updated_at,
                clinic_id=user.clinic_id
            ) for user in users
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar usuários: {str(e)}")

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user = Depends(require_admin_access),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new user with role and permissions.
    """
    try:
        # Check if email already exists
        existing_user = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email já está em uso")
        
        # Create new user
        new_user = User(
            id=str(uuid.uuid4()),
            name=user_data.name,
            email=user_data.email,
            password_hash=user_data.password,  # This should be hashed in production
            clinic_id=current_user.clinic_id,
            role=user_data.role,
            permissions=user_data.permissions or {},
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        return UserResponse(
            id=new_user.id,
            name=new_user.name,
            email=new_user.email,
            role=getattr(new_user, 'role', 'user'),
            permissions=getattr(new_user, 'permissions', {}),
            is_active=getattr(new_user, 'is_active', True),
            created_at=new_user.created_at,
            updated_at=new_user.updated_at,
            clinic_id=new_user.clinic_id
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar usuário: {str(e)}")

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user = Depends(require_admin_access),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Update user role and permissions.
    """
    try:
        # Get user to update
        user_result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.clinic_id == current_user.clinic_id
            )
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        # Update user data
        update_data = {}
        if user_data.name:
            update_data['name'] = user_data.name
        if user_data.role:
            update_data['role'] = user_data.role
        if user_data.permissions is not None:
            update_data['permissions'] = user_data.permissions
        if user_data.is_active is not None:
            update_data['is_active'] = user_data.is_active
        
        update_data['updated_at'] = datetime.utcnow()
        
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(**update_data)
        )
        
        await db.commit()
        
        # Return updated user
        updated_user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        updated_user = updated_user_result.scalar_one()
        
        return UserResponse(
            id=updated_user.id,
            name=updated_user.name,
            email=updated_user.email,
            role=getattr(updated_user, 'role', 'user'),
            permissions=getattr(updated_user, 'permissions', {}),
            is_active=getattr(updated_user, 'is_active', True),
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at,
            clinic_id=updated_user.clinic_id
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar usuário: {str(e)}")

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user = Depends(require_admin_access),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Delete a user (soft delete by setting is_active to False).
    """
    try:
        # Check if user exists and belongs to the clinic
        user_result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.clinic_id == current_user.clinic_id
            )
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        # Prevent deleting the current user
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Não é possível deletar seu próprio usuário")
        
        # Soft delete by setting is_active to False
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        
        await db.commit()
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar usuário: {str(e)}")

@router.get("/roles", response_model=Dict[str, Any])
async def get_available_roles(
    current_user = Depends(require_admin_access)
):
    """
    Get available roles and their permissions.
    """
    return {
        "roles": {
            "admin": {
                "display_name": "Administrador",
                "description": "Acesso completo ao sistema",
                "permissions": [
                    "users.manage",
                    "patients.manage",
                    "consultations.manage",
                    "billing.manage",
                    "reports.view",
                    "settings.manage"
                ]
            },
            "medico": {
                "display_name": "Médico",
                "description": "Acesso ao atendimento e prontuário",
                "permissions": [
                    "patients.view",
                    "consultations.manage",
                    "prescriptions.create",
                    "medical_records.view"
                ]
            },
            "secretaria": {
                "display_name": "Secretária",
                "description": "Acesso à agenda, pacientes e fila",
                "permissions": [
                    "patients.manage",
                    "appointments.manage",
                    "queue.manage",
                    "billing.view"
                ]
            },
            "financeiro": {
                "display_name": "Financeiro",
                "description": "Acesso a relatórios e cobranças",
                "permissions": [
                    "billing.manage",
                    "reports.view",
                    "invoices.manage",
                    "payments.manage"
                ]
            }
        }
    }
