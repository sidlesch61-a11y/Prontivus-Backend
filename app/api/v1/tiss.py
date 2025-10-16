"""
API endpoints for TISS Multi-Convênio system.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional
import uuid
import json
import logging
from datetime import datetime, timedelta

from app.models.tiss import (
    TISSProvider, TISSJob, TISSLog, TISSEthicalLock,
    TISSProviderCreateRequest, TISSProviderResponse, TISSJobCreateRequest,
    TISSJobResponse, TISSLogResponse, TISSTestConnectionRequest,
    TISSTestConnectionResponse, TISSEthicalLockResponse,
    TISSProviderStatus, TISSJobStatus, TISSLogLevel, TISSEthicalLockType
)
from app.core.auth import AuthDependencies
from app.db.session import get_db_session
from app.services.tiss_service import TISSService
from app.core.security import security
from app.workers.tiss_tasks import process_tiss_job_task
from app.models.database import Patient, User, Consultation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tiss", tags=["tiss"])

@router.get("/providers", response_model=List[TISSProviderResponse])
async def list_tiss_providers(
    status: Optional[TISSProviderStatus] = Query(None),
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List TISS providers for the current clinic."""
    
    statement = select(TISSProvider).where(TISSProvider.clinic_id == current_user.clinic_id)
    
    if status:
        statement = statement.where(TISSProvider.status == status)
    
    statement = statement.order_by(TISSProvider.created_at.desc())
    
    result = await db.execute(statement)
    providers = result.scalars().all()
    
    # Mask sensitive data
    response_providers = []
    for provider in providers:
        provider_dict = provider.dict()
        provider_dict["password_encrypted"] = "***MASKED***"
        response_providers.append(TISSProviderResponse(**provider_dict))
    
    return response_providers

@router.post("/providers", response_model=TISSProviderResponse)
async def create_tiss_provider(
    provider_data: TISSProviderCreateRequest,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new TISS provider configuration."""
    
    try:
        # Check if provider code already exists for this clinic
        existing_stmt = select(TISSProvider).where(
            and_(
                TISSProvider.clinic_id == current_user.clinic_id,
                TISSProvider.code == provider_data.code
            )
        )
        existing_provider = (await db.execute(existing_stmt)).scalar_one_or_none()
        
        if existing_provider:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Provider with code '{provider_data.code}' already exists"
            )
        
        # Encrypt password
        encrypted_password = security.encrypt_field(provider_data.password)
        
        # Create provider
        provider = TISSProvider(
            clinic_id=current_user.clinic_id,
            name=provider_data.name,
            code=provider_data.code,
            cnpj=provider_data.cnpj,
            endpoint_url=provider_data.endpoint_url,
            environment=provider_data.environment,
            username=provider_data.username,
            password_encrypted=encrypted_password,
            certificate_path=provider_data.certificate_path,
            timeout_seconds=provider_data.timeout_seconds,
            max_retries=provider_data.max_retries,
            retry_delay_seconds=provider_data.retry_delay_seconds,
            config_meta=provider_data.config_meta,
            notes=provider_data.notes,
            status=TISSProviderStatus.INACTIVE
        )
        
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        
        # Log the creation
        log = TISSLog(
            clinic_id=current_user.clinic_id,
            provider_id=provider.id,
            level=TISSLogLevel.INFO,
            message=f"TISS provider '{provider.name}' created",
            operation="create_provider",
            user_id=current_user.id,
            details={"provider_code": provider.code, "environment": provider.environment}
        )
        db.add(log)
        await db.commit()
        
        logger.info(f"TISS provider created: {provider.id} by user {current_user.id}")
        
        # Return response with masked password
        provider_dict = provider.dict()
        provider_dict["password_encrypted"] = "***MASKED***"
        return TISSProviderResponse(**provider_dict)
        
    except Exception as e:
        logger.error(f"Error creating TISS provider: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create TISS provider"
        )


@router.patch("/providers/{provider_id}", response_model=TISSProviderResponse)
async def update_tiss_provider(
    provider_id: uuid.UUID,
    provider_data: TISSProviderCreateRequest,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update an existing TISS provider (partial)."""
    stmt = select(TISSProvider).where(
        and_(
            TISSProvider.id == provider_id,
            TISSProvider.clinic_id == current_user.clinic_id
        )
    )
    provider = (await db.execute(stmt)).scalar_one_or_none()

    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TISS provider not found")

    try:
        update_dict = provider_data.dict(exclude_unset=True)
        if "password" in update_dict and update_dict["password"]:
            encryption_service = EncryptionService()
            update_dict["password_encrypted"] = encryption_service.encrypt(update_dict.pop("password"))
        for field, value in update_dict.items():
            setattr(provider, field, value)

        db.add(provider)
        await db.commit()
        await db.refresh(provider)

        provider_dict = provider.dict()
        provider_dict["password_encrypted"] = "***MASKED***"
        return TISSProviderResponse(**provider_dict)
    except Exception as e:
        logger.error(f"Error updating TISS provider: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update TISS provider")


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tiss_provider(
    provider_id: uuid.UUID,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a TISS provider."""
    stmt = select(TISSProvider).where(
        and_(
            TISSProvider.id == provider_id,
            TISSProvider.clinic_id == current_user.clinic_id
        )
    )
    provider = (await db.execute(stmt)).scalar_one_or_none()

    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TISS provider not found")

    await db.delete(provider)
    await db.commit()
    return None

@router.get("/providers/{provider_id}", response_model=TISSProviderResponse)
async def get_tiss_provider(
    provider_id: uuid.UUID,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get TISS provider by ID."""
    
    stmt = select(TISSProvider).where(
        and_(
            TISSProvider.id == provider_id,
            TISSProvider.clinic_id == current_user.clinic_id
        )
    )
    provider = (await db.execute(stmt)).scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TISS provider not found"
        )
    
    # Return response with masked password
    provider_dict = provider.dict()
    provider_dict["password_encrypted"] = "***MASKED***"
    return TISSProviderResponse(**provider_dict)

@router.post("/providers/{provider_id}/test", response_model=TISSTestConnectionResponse)
async def test_tiss_provider_connection(
    provider_id: uuid.UUID,
    test_data: Optional[TISSTestConnectionRequest] = None,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Test TISS provider connection."""
    
    result = await db.execute(
        select(TISSProvider).where(
            and_(
                TISSProvider.id == provider_id,
                TISSProvider.clinic_id == current_user.clinic_id
            )
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TISS provider not found"
        )
    
    try:
        # Use test data if provided, otherwise use stored credentials
        username = test_data.username if test_data and test_data.username else provider.username
        password = test_data.password if test_data and test_data.password else None
        endpoint_url = test_data.endpoint_url if test_data and test_data.endpoint_url else provider.endpoint_url
        
        if not password and not test_data:
            # Decrypt stored password
            password = security.decrypt_field(provider.password_encrypted)
        
        # Test connection
        tiss_service = TISSService()
        test_result = await tiss_service.test_connection(
            endpoint_url=endpoint_url,
            username=username,
            password=password,
            timeout=provider.timeout_seconds
        )
        
        # Update provider with test result
        provider.last_test_result = test_result.dict()
        provider.last_tested_at = datetime.utcnow()
        
        if test_result.success:
            provider.status = TISSProviderStatus.ACTIVE
            provider.last_successful_request = datetime.utcnow()
        else:
            provider.status = TISSProviderStatus.INACTIVE
        
        db.add(provider)
        
        # Log the test
        log = TISSLog(
            clinic_id=current_user.clinic_id,
            provider_id=provider.id,
            level=TISSLogLevel.INFO if test_result.success else TISSLogLevel.ERROR,
            message=f"TISS provider connection test {'successful' if test_result.success else 'failed'}",
            operation="test_connection",
            user_id=current_user.id,
            details=test_result.dict()
        )
        db.add(log)
        await db.commit()
        
        logger.info(f"TISS provider connection test: {provider.id} - {'success' if test_result.success else 'failed'}")
        
        return test_result
        
    except Exception as e:
        logger.error(f"Error testing TISS provider connection: {str(e)}")
        
        # Log the error
        log = TISSLog(
            clinic_id=current_user.clinic_id,
            provider_id=provider.id,
            level=TISSLogLevel.ERROR,
            message=f"TISS provider connection test failed: {str(e)}",
            operation="test_connection",
            user_id=current_user.id
        )
        db.add(log)
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}"
        )

@router.post("/jobs", response_model=TISSJobResponse)
async def create_tiss_job(
    job_data: TISSJobCreateRequest,
    request: Request,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new TISS job."""
    
    try:
        # Verify provider exists and belongs to clinic
        provider_stmt = select(TISSProvider).where(
            and_(
                TISSProvider.id == job_data.provider_id,
                TISSProvider.clinic_id == current_user.clinic_id,
                TISSProvider.status == TISSProviderStatus.ACTIVE
            )
        )
        provider = (await db.execute(provider_stmt)).scalar_one_or_none()
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TISS provider not found or inactive"
            )
        
        # Check for ethical locks
        tiss_service = TISSService()
        ethical_lock_check = await tiss_service.check_ethical_locks(
            clinic_id=current_user.clinic_id,
            invoice_id=job_data.invoice_id,
            procedure_code=job_data.procedure_code,
            job_type=job_data.job_type
        )
        
        if ethical_lock_check.has_lock:
            # Create ethical lock record
            ethical_lock = TISSEthicalLock(
                clinic_id=current_user.clinic_id,
                lock_type=ethical_lock_check.lock_type,
                invoice_id=job_data.invoice_id,
                procedure_code=job_data.procedure_code,
                reason=ethical_lock_check.reason,
                manual_review_required=True
            )
            db.add(ethical_lock)
            
            # Log the ethical lock
            log = TISSLog(
                clinic_id=current_user.clinic_id,
                provider_id=job_data.provider_id,
                level=TISSLogLevel.WARNING,
                message=f"Ethical lock triggered: {ethical_lock_check.reason}",
                operation="create_job",
                user_id=current_user.id,
                details={
                    "lock_type": ethical_lock_check.lock_type,
                    "reason": ethical_lock_check.reason
                }
            )
            db.add(log)
            await db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ethical lock: {ethical_lock_check.reason}"
            )
        
        # Create job
        job = TISSJob(
            clinic_id=current_user.clinic_id,
            provider_id=job_data.provider_id,
            job_type=job_data.job_type,
            invoice_id=job_data.invoice_id,
            procedure_code=job_data.procedure_code,
            payload=job_data.payload,
            priority=job_data.priority,
            job_meta=job_data.job_meta,
            status=TISSJobStatus.PENDING
        )
        
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Log the job creation
        log = TISSLog(
            clinic_id=current_user.clinic_id,
            provider_id=job_data.provider_id,
            job_id=job.id,
            level=TISSLogLevel.INFO,
            message=f"TISS job created: {job.job_type}",
            operation="create_job",
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            details={
                "job_type": job.job_type,
                "invoice_id": str(job.invoice_id) if job.invoice_id else None,
                "procedure_code": job.procedure_code
            }
        )
        db.add(log)
        await db.commit()
        
        # Queue the job for processing
        process_tiss_job_task.delay(str(job.id))
        
        logger.info(f"TISS job created: {job.id} by user {current_user.id}")
        
        return TISSJobResponse.from_orm(job)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating TISS job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create TISS job"
        )

@router.get("/jobs", response_model=List[TISSJobResponse])
async def list_tiss_jobs(
    status: Optional[TISSJobStatus] = Query(None),
    provider_id: Optional[uuid.UUID] = Query(None),
    job_type: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List TISS jobs with optional filters."""
    
    statement = select(TISSJob).where(TISSJob.clinic_id == current_user.clinic_id)
    
    if status:
        statement = statement.where(TISSJob.status == status)
    
    if provider_id:
        statement = statement.where(TISSJob.provider_id == provider_id)
    
    if job_type:
        statement = statement.where(TISSJob.job_type == job_type)
    
    statement = statement.order_by(TISSJob.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(statement)
    jobs = result.scalars().all()
    
    return [TISSJobResponse.from_orm(job) for job in jobs]

@router.get("/jobs/{job_id}", response_model=TISSJobResponse)
async def get_tiss_job(
    job_id: uuid.UUID,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get TISS job by ID."""
    
    job_stmt = select(TISSJob).where(
        and_(
            TISSJob.id == job_id,
            TISSJob.clinic_id == current_user.clinic_id
        )
    )
    job = (await db.execute(job_stmt)).scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TISS job not found"
        )
    
    return TISSJobResponse.from_orm(job)

@router.post("/jobs/{job_id}/reprocess")
async def reprocess_tiss_job(
    job_id: uuid.UUID,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Reprocess a TISS job."""
    
    job_stmt = select(TISSJob).where(
        and_(
            TISSJob.id == job_id,
            TISSJob.clinic_id == current_user.clinic_id
        )
    )
    job = (await db.execute(job_stmt)).scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TISS job not found"
        )
    
    if job.status not in [TISSJobStatus.FAILED, TISSJobStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed or rejected jobs can be reprocessed"
        )
    
    try:
        # Reset job status
        job.status = TISSJobStatus.PENDING
        job.attempts = 0
        job.last_error = None
        job.last_error_at = None
        job.next_retry_at = None
        job.updated_at = datetime.utcnow()
        
        db.add(job)
        
        # Log the reprocess
        log = TISSLog(
            clinic_id=current_user.clinic_id,
            provider_id=job.provider_id,
            job_id=job.id,
            level=TISSLogLevel.INFO,
            message="TISS job reprocessed",
            operation="reprocess_job",
            user_id=current_user.id,
            details={"previous_status": job.status}
        )
        db.add(log)
        await db.commit()
        
        # Queue the job for processing
        process_tiss_job_task.delay(str(job.id))
        
        logger.info(f"TISS job reprocessed: {job.id} by user {current_user.id}")
        
        return {"message": "Job queued for reprocessing", "job_id": str(job.id)}
        
    except Exception as e:
        logger.error(f"Error reprocessing TISS job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reprocess TISS job"
        )

@router.get("/jobs/{job_id}/logs", response_model=List[TISSLogResponse])
async def get_tiss_job_logs(
    job_id: uuid.UUID,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get logs for a specific TISS job."""
    
    # Verify job exists and belongs to clinic
    job_stmt = select(TISSJob).where(
        and_(
            TISSJob.id == job_id,
            TISSJob.clinic_id == current_user.clinic_id
        )
    )
    job = (await db.execute(job_stmt)).scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TISS job not found"
        )
    
    # Get logs
    statement = select(TISSLog).where(
        and_(
            TISSLog.job_id == job_id,
            TISSLog.clinic_id == current_user.clinic_id
        )
    ).order_by(TISSLog.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(statement)
    logs = result.scalars().all()
    
    return [TISSLogResponse.from_orm(log) for log in logs]


# ---------------------------------------------------------------------------
# Simple Generate Endpoint (SADT or CONSULTA)
# ---------------------------------------------------------------------------
@router.post("/generate")
async def generate_tiss_guide(
    payload: dict,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate a TISS guide (simplified sync flow)."""
    try:
        clinic_id = current_user.clinic_id
        guide_type = (payload or {}).get("type", "CONSULTA")
        consultation_id = (payload or {}).get("consultation_id")

        if not consultation_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="consultation_id é obrigatório")

        # Load consultation, patient, doctor
        cons_stmt = select(Consultation).where(Consultation.id == consultation_id)
        cons = (await db.execute(cons_stmt)).scalar_one_or_none()
        if not cons:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")

        pat = (await db.execute(select(Patient).where(Patient.id == cons.patient_id))).scalar_one_or_none()
        if not pat:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")

        doc = (await db.execute(select(User).where(User.id == cons.doctor_id))).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Médico não encontrado")

        # Basic validation of convênio/particular
        convenio = getattr(pat, "insurance_provider", None)
        payment_type = getattr(pat, "payment_type", None)  # "particular" or "convenio"
        if not convenio and (payment_type or "").lower() != "particular":
            logger.warning("TISS generate: paciente sem convênio configurado")

        # Build minimal XML/JSON structure (placeholder)
        generated_at = datetime.utcnow().isoformat()
        xml_stub = f"""
<tiss>
  <cabecalho>
    <registroANS>{str(clinic_id)[:8]}</registroANS>
    <dataGeracao>{generated_at}</dataGeracao>
    <tipoGuia>{guide_type}</tipoGuia>
  </cabecalho>
  <dadosBeneficiario>
    <nome>{getattr(pat, 'name', '')}</nome>
    <numeroCarteira>{getattr(pat, 'insurance_number', '')}</numeroCarteira>
    <operadora>{convenio or 'PARTICULAR'}</operadora>
  </dadosBeneficiario>
  <dadosProfissionais>
    <medico>{getattr(doc, 'full_name', getattr(doc, 'name', ''))}</medico>
    <crm>{getattr(doc, 'license_number', '')}</crm>
  </dadosProfissionais>
  <dadosAtendimento>
    <consultaId>{consultation_id}</consultaId>
  </dadosAtendimento>
</tiss>
""".strip()

        # Log success (simplified - skip TISSLog for now)
        logger.info(f"TISS guide generated: {guide_type} for consultation {consultation_id}")

        return {
            "status": "ok",
            "type": guide_type,
            "consultation_id": str(consultation_id),
            "xml": xml_stub,
            "generated_at": generated_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao gerar guia TISS", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar guia TISS: {str(e)}",
        )

@router.get("/logs", response_model=List[TISSLogResponse])
async def list_tiss_logs(
    provider_id: Optional[uuid.UUID] = Query(None),
    level: Optional[TISSLogLevel] = Query(None),
    operation: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List TISS logs with optional filters."""
    
    statement = select(TISSLog).where(TISSLog.clinic_id == current_user.clinic_id)
    
    if provider_id:
        statement = statement.where(TISSLog.provider_id == provider_id)
    
    if level:
        statement = statement.where(TISSLog.level == level)
    
    if operation:
        statement = statement.where(TISSLog.operation == operation)
    
    statement = statement.order_by(TISSLog.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(statement)
    logs = result.scalars().all()
    
    return [TISSLogResponse.from_orm(log) for log in logs]

@router.get("/ethical-locks", response_model=List[TISSEthicalLockResponse])
async def list_tiss_ethical_locks(
    resolved: Optional[bool] = Query(None),
    lock_type: Optional[TISSEthicalLockType] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List TISS ethical locks."""
    
    statement = select(TISSEthicalLock).where(TISSEthicalLock.clinic_id == current_user.clinic_id)
    
    if resolved is not None:
        statement = statement.where(TISSEthicalLock.resolved == resolved)
    
    if lock_type:
        statement = statement.where(TISSEthicalLock.lock_type == lock_type)
    
    statement = statement.order_by(TISSEthicalLock.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(statement)
    locks = result.scalars().all()
    
    return [TISSEthicalLockResponse.from_orm(lock) for lock in locks]

@router.post("/ethical-locks/{lock_id}/resolve")
async def resolve_tiss_ethical_lock(
    lock_id: uuid.UUID,
    resolution_notes: str,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Resolve a TISS ethical lock."""
    
    ethical_lock_stmt = select(TISSEthicalLock).where(
        and_(
            TISSEthicalLock.id == lock_id,
            TISSEthicalLock.clinic_id == current_user.clinic_id
        )
    )
    ethical_lock = (await db.execute(ethical_lock_stmt)).scalar_one_or_none()
    
    if not ethical_lock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TISS ethical lock not found"
        )
    
    if ethical_lock.resolved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ethical lock already resolved"
        )
    
    try:
        # Resolve the lock
        ethical_lock.resolved = True
        ethical_lock.resolved_at = datetime.utcnow()
        ethical_lock.resolved_by = current_user.id
        ethical_lock.resolution_notes = resolution_notes
        ethical_lock.updated_at = datetime.utcnow()
        
        db.add(ethical_lock)
        
        # Log the resolution
        log = TISSLog(
            clinic_id=current_user.clinic_id,
            level=TISSLogLevel.INFO,
            message=f"TISS ethical lock resolved: {ethical_lock.lock_type}",
            operation="resolve_ethical_lock",
            user_id=current_user.id,
            details={
                "lock_id": str(lock_id),
                "lock_type": ethical_lock.lock_type,
                "resolution_notes": resolution_notes
            }
        )
        db.add(log)
        await db.commit()
        
        logger.info(f"TISS ethical lock resolved: {lock_id} by user {current_user.id}")
        
        return {"message": "Ethical lock resolved successfully", "lock_id": str(lock_id)}
        
    except Exception as e:
        logger.error(f"Error resolving TISS ethical lock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve ethical lock"
        )


@router.get("/stats")
async def get_tiss_stats(
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get TISS statistics for the current clinic."""
    try:
        from sqlalchemy import func, cast, String
        from datetime import date
        
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
        
        # Total jobs
        total_jobs = await db.scalar(
            select(func.count(TISSJob.id))
            .where(TISSJob.clinic_id == clinic_id)
        ) or 0
        
        # Jobs today
        jobs_today = await db.scalar(
            select(func.count(TISSJob.id))
            .where(
                and_(
                    TISSJob.clinic_id == clinic_id,
                    func.date(TISSJob.created_at) == today
                )
            )
        ) or 0
        
        # Pending jobs
        pending_jobs = await db.scalar(
            select(func.count(TISSJob.id))
            .where(
                and_(
                    TISSJob.clinic_id == clinic_id,
                    cast(TISSJob.status, String).in_(["pending", "processing"])
                )
            )
        ) or 0
        
        # Completed jobs
        completed_jobs = await db.scalar(
            select(func.count(TISSJob.id))
            .where(
                and_(
                    TISSJob.clinic_id == clinic_id,
                    cast(TISSJob.status, String) == "completed"
                )
            )
        ) or 0
        
        # Failed jobs
        failed_jobs = await db.scalar(
            select(func.count(TISSJob.id))
            .where(
                and_(
                    TISSJob.clinic_id == clinic_id,
                    cast(TISSJob.status, String) == "failed"
                )
            )
        ) or 0
        
        # Jobs this week
        week_start = today - timedelta(days=today.weekday())
        jobs_this_week = await db.scalar(
            select(func.count(TISSJob.id))
            .where(
                and_(
                    TISSJob.clinic_id == clinic_id,
                    func.date(TISSJob.created_at) >= week_start
                )
            )
        ) or 0
        
        # Success rate
        if total_jobs > 0:
            success_rate = round((completed_jobs / total_jobs) * 100, 1)
        else:
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
        logger.error(f"Error getting TISS stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get TISS statistics: {str(e)}"
        )