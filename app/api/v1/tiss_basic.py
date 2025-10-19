"""
Basic TISS providers CRUD (async) used by Health Plans UI.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
import uuid
from datetime import datetime

from app.db.session import get_db_session
from app.core.auth import AuthDependencies
from app.core.security import security
from app.models.tiss import (
    TISSProvider,
    TISSProviderCreateRequest,
    TISSProviderResponse,
    TISSProviderStatus,
    TISSLog,
    TISSLogLevel,
)

router = APIRouter(tags=["TISS - Basic"])


@router.get("/providers", response_model=List[TISSProviderResponse])
async def list_providers(
    status: Optional[TISSProviderStatus] = Query(None),
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        stmt = select(TISSProvider).where(TISSProvider.clinic_id == current_user.clinic_id)
        if status:
            stmt = stmt.where(TISSProvider.status == status)
        stmt = stmt.order_by(TISSProvider.created_at.desc())
        result = await db.execute(stmt)
        providers = result.scalars().all()

        responses: List[TISSProviderResponse] = []
        for p in providers:
            # Convert SQLModel to dict safely
            provider_dict = {
                "id": p.id,
                "clinic_id": p.clinic_id,
                "name": p.name,
                "code": p.code,
                "cnpj": p.cnpj,
                "endpoint_url": p.endpoint_url,
                "environment": p.environment,
                "username": p.username,
                "password_encrypted": "***MASKED***",
                "certificate_path": p.certificate_path,
                "timeout_seconds": p.timeout_seconds,
                "max_retries": p.max_retries,
                "retry_delay_seconds": p.retry_delay_seconds,
                "config_meta": p.config_meta,
                "notes": p.notes,
                "status": p.status,
                "last_test_result": p.last_test_result,
                "last_tested_at": p.last_tested_at,
                "last_successful_request": p.last_successful_request,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            responses.append(TISSProviderResponse(**provider_dict))
        return responses
    except Exception as e:
        import logging
        logging.error(f"Error listing TISS providers: {str(e)}", exc_info=True)
        # Return empty list if table doesn't exist
        return []


@router.post("/providers", response_model=TISSProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: TISSProviderCreateRequest,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    # Unique code per clinic
    exists_stmt = select(TISSProvider).where(
        and_(TISSProvider.clinic_id == current_user.clinic_id, TISSProvider.code == data.code)
    )
    if (await db.execute(exists_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Provider code already exists")

    provider = TISSProvider(
        clinic_id=current_user.clinic_id,
        name=data.name,
        code=data.code,
        cnpj=data.cnpj,
        endpoint_url=data.endpoint_url,
        environment=data.environment,
        username=data.username,
        password_encrypted=security.encrypt_field(data.password),
        certificate_path=data.certificate_path,
        timeout_seconds=data.timeout_seconds,
        max_retries=data.max_retries,
        retry_delay_seconds=data.retry_delay_seconds,
        config_meta=data.config_meta,
        notes=data.notes,
        status=TISSProviderStatus.INACTIVE,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    provider_dict = {
        "id": provider.id,
        "clinic_id": provider.clinic_id,
        "name": provider.name,
        "code": provider.code,
        "cnpj": provider.cnpj,
        "endpoint_url": provider.endpoint_url,
        "environment": provider.environment,
        "username": provider.username,
        "password_encrypted": "***MASKED***",
        "certificate_path": provider.certificate_path,
        "timeout_seconds": provider.timeout_seconds,
        "max_retries": provider.max_retries,
        "retry_delay_seconds": provider.retry_delay_seconds,
        "config_meta": provider.config_meta,
        "notes": provider.notes,
        "status": provider.status,
        "last_test_result": provider.last_test_result,
        "last_tested_at": provider.last_tested_at,
        "last_successful_request": provider.last_successful_request,
        "created_at": provider.created_at,
        "updated_at": provider.updated_at,
    }
    return TISSProviderResponse(**provider_dict)


@router.patch("/providers/{provider_id}", response_model=TISSProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    data: TISSProviderCreateRequest,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(TISSProvider).where(
        and_(TISSProvider.id == provider_id, TISSProvider.clinic_id == current_user.clinic_id)
    )
    provider = (await db.execute(stmt)).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    update = data.dict(exclude_unset=True)
    if update.get("password"):
        update["password_encrypted"] = security.encrypt_field(update.pop("password"))

    for k, v in update.items():
        setattr(provider, k, v)
    provider.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(provider)

    provider_dict = {
        "id": provider.id,
        "clinic_id": provider.clinic_id,
        "name": provider.name,
        "code": provider.code,
        "cnpj": provider.cnpj,
        "endpoint_url": provider.endpoint_url,
        "environment": provider.environment,
        "username": provider.username,
        "password_encrypted": "***MASKED***",
        "certificate_path": provider.certificate_path,
        "timeout_seconds": provider.timeout_seconds,
        "max_retries": provider.max_retries,
        "retry_delay_seconds": provider.retry_delay_seconds,
        "config_meta": provider.config_meta,
        "notes": provider.notes,
        "status": provider.status,
        "last_test_result": provider.last_test_result,
        "last_tested_at": provider.last_tested_at,
        "last_successful_request": provider.last_successful_request,
        "created_at": provider.created_at,
        "updated_at": provider.updated_at,
    }
    return TISSProviderResponse(**provider_dict)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: uuid.UUID,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(TISSProvider).where(
        and_(TISSProvider.id == provider_id, TISSProvider.clinic_id == current_user.clinic_id)
    )
    provider = (await db.execute(stmt)).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    await db.delete(provider)
    await db.commit()
    return None


@router.get("/jobs")
async def list_jobs(
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List TISS jobs (stub endpoint)."""
    # Return empty list for now - full implementation requires TISSJob table
    return []


@router.get("/stats")
async def get_tiss_stats(
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get TISS statistics for the current clinic."""
    try:
        from sqlalchemy import func, cast, String
        from datetime import date, timedelta
        
        clinic_id = current_user.clinic_id
        today = date.today()
        
        # Total providers
        total_providers = await db.scalar(
            select(func.count(TISSProvider.id))
            .where(TISSProvider.clinic_id == clinic_id)
        ) or 0
        
        # Active providers
        active_providers = await db.scalar(
            select(func.count(TISSProvider.id))
            .where(
                and_(
                    TISSProvider.clinic_id == clinic_id,
                    cast(TISSProvider.status, String) == "active"
                )
            )
        ) or 0
        
        # Since TISSJob table doesn't exist yet, return placeholder values
        total_jobs = 0
        jobs_today = 0
        pending_jobs = 0
        completed_jobs = 0
        failed_jobs = 0
        jobs_this_week = 0
        success_rate = 0.0
        
        return {
            "total_providers": total_providers,
            "active_providers": active_providers,
            "total_jobs": total_jobs,
            "jobs_today": jobs_today,
            "pending_jobs": pending_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "jobs_this_week": jobs_this_week,
            "success_rate": success_rate
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting TISS stats: {str(e)}", exc_info=True)
        # Return zeros if error
        return {
            "total_providers": 0,
            "active_providers": 0,
            "total_jobs": 0,
            "jobs_today": 0,
            "pending_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "jobs_this_week": 0,
            "success_rate": 0.0
        }


