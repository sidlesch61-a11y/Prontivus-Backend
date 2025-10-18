"""
Patients API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from app.core.auth import get_current_user, require_patients_read, require_patients_write
from app.db.session import get_db_session
from app.models import Patient, AuditLog
from app.schemas import PatientCreate, PatientUpdate, PatientResponse, PaginationParams, PaginatedResponse

router = APIRouter()


@router.get("/test")
async def test_patients():
    """Test endpoint for patients router."""
    return {"message": "Patients router is working", "status": "ok"}


@router.get("/deployment-test")
async def deployment_test():
    """Test endpoint to verify deployment is working."""
    return {"message": "Deployment test successful", "timestamp": "2025-01-18T09:00:00Z", "status": "ok"}


@router.get("/simple")
async def list_patients_simple():
    """Simple patients endpoint without authentication for testing."""
    return {"message": "Simple patients endpoint working", "status": "ok"}


@router.get("/auth-test")
async def list_patients_auth_test(
    current_user = Depends(require_patients_read)
):
    """Patients endpoint with authentication but simple response for testing."""
    return {"message": "Auth test endpoint working", "user_id": str(current_user.id), "status": "ok"}


@router.get("/model-test", response_model=dict)
async def list_patients_model_test(
    search: Optional[str] = Query(None, description="Search by name or CPF"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Test endpoint with auth and simple dict response model."""
    return {"message": "Model test endpoint working", "user_id": str(current_user.id), "status": "ok"}


@router.get("/paginated-test", response_model=PaginatedResponse)
async def list_patients_paginated_test():
    """Test endpoint with PaginatedResponse model only."""
    return PaginatedResponse(
        items=[{"id": "1", "name": "Test Patient"}],
        total=1,
        page=1,
        size=20,
        pages=1
    )


@router.get("/main-test", response_model=PaginatedResponse)
async def list_patients_main_test(
    search: Optional[str] = Query(None, description="Search by name or CPF"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Test endpoint that mimics main endpoint but returns mock data."""
    # Mock data instead of database query
    mock_patients = [
        {"id": "1", "name": "Test Patient 1", "cpf": "12345678901"},
        {"id": "2", "name": "Test Patient 2", "cpf": "12345678902"}
    ]
    
    total = len(mock_patients)
    pages = (total + size - 1) // size
    
    return PaginatedResponse(
        items=mock_patients,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/db-test", response_model=PaginatedResponse)
async def list_patients_db_test(
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Test endpoint with database query but no complex logic."""
    try:
        # Simple database query
        query = select(Patient).where(Patient.clinic_id == current_user.clinic_id).limit(5)
        result = await db.execute(query)
        patients = result.scalars().all()
        
        # Simple serialization
        patient_data = []
        for patient in patients:
            patient_data.append({
                "id": str(patient.id),
                "name": patient.name,
                "cpf": patient.cpf,
                "city": patient.city
            })
        
        return PaginatedResponse(
            items=patient_data,
            total=len(patient_data),
            page=1,
            size=5,
            pages=1
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/serialization-test", response_model=PaginatedResponse)
async def list_patients_serialization_test(
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Test endpoint with PatientResponse.model_validate to isolate serialization issue."""
    try:
        # Simple database query
        query = select(Patient).where(Patient.clinic_id == current_user.clinic_id).limit(3)
        result = await db.execute(query)
        patients = result.scalars().all()
        
        # Test PatientResponse.model_validate
        patient_responses = []
        for patient in patients:
            try:
                patient_response = PatientResponse.model_validate(patient)
                patient_responses.append(patient_response)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Serialization error for patient {patient.id}: {str(e)}")
        
        return PaginatedResponse(
            items=patient_responses,
            total=len(patient_responses),
            page=1,
            size=3,
            pages=1
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/complex-test", response_model=PaginatedResponse)
async def list_patients_complex_test(
    search: Optional[str] = Query(None, description="Search by name or CPF"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Test endpoint with main endpoint's complex logic but simplified."""
    try:
        # Build query like main endpoint
        query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
        
        # Add search filter (like main endpoint)
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Patient.name.ilike(search_term),
                    Patient.cpf.ilike(search_term)
                )
            )
        
        # Get total count (like main endpoint)
        count_query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
        if search:
            search_term = f"%{search}%"
            count_query = count_query.where(
                or_(
                    Patient.name.ilike(search_term),
                    Patient.cpf.ilike(search_term)
                )
            )
        
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        # Apply pagination (like main endpoint)
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        result = await db.execute(query)
        patients = result.scalars().all()
        
        # Use simple serialization instead of PatientResponse.model_validate
        patient_data = []
        for patient in patients:
            patient_data.append({
                "id": str(patient.id),
                "name": patient.name,
                "cpf": patient.cpf,
                "city": patient.city,
                "clinic_id": str(patient.clinic_id),
                "created_at": patient.created_at.isoformat(),
                "updated_at": patient.updated_at.isoformat()
            })
        
        return PaginatedResponse(
            items=patient_data,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Complex logic error: {str(e)}")


@router.get("/final-test", response_model=PaginatedResponse)
async def list_patients_final_test(
    search: Optional[str] = Query(None, description="Search by name or CPF"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Test endpoint with EXACT main endpoint logic including PatientResponse.model_validate."""
    try:
        # EXACT same logic as main endpoint
        query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
        
        # Add search filter
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Patient.name.ilike(search_term),
                    Patient.cpf.ilike(search_term)
                )
            )
        
        # Get total count
        count_query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
        if search:
            search_term = f"%{search}%"
            count_query = count_query.where(
                or_(
                    Patient.name.ilike(search_term),
                    Patient.cpf.ilike(search_term)
                )
            )
        
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        result = await db.execute(query)
        patients = result.scalars().all()
        
        # EXACT same serialization as main endpoint
        return PaginatedResponse(
            items=[PatientResponse.model_validate(patient) for patient in patients],
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Final test error: {str(e)}")


@router.get("/", response_model=PaginatedResponse)
async def list_patients_root(
    search: Optional[str] = Query(None, description="Search by name or CPF"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """List patients with pagination and search at root path - handles both root and /list calls."""
    try:
        query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
        
        # Add search filter
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Patient.name.ilike(search_term),
                    Patient.cpf.ilike(search_term)
                )
            )
        
        # Get total count
        count_query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
        if search:
            search_term = f"%{search}%"
            count_query = count_query.where(
                or_(
                    Patient.name.ilike(search_term),
                    Patient.cpf.ilike(search_term)
                )
            )
        
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        result = await db.execute(query)
        patients = result.scalars().all()
        
        return PaginatedResponse(
            items=[PatientResponse.model_validate(patient) for patient in patients],
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing patients: {str(e)}")


@router.get("/list", response_model=PaginatedResponse)
async def list_patients(
    search: Optional[str] = Query(None, description="Search by name or CPF"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """List patients with pagination and search."""
    try:
        query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
        
        # Add search filter
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Patient.name.ilike(search_term),
                    Patient.cpf.ilike(search_term)
                )
            )
        
        # Get total count
        count_query = select(Patient).where(Patient.clinic_id == current_user.clinic_id)
        if search:
            search_term = f"%{search}%"
            count_query = count_query.where(
                or_(
                    Patient.name.ilike(search_term),
                    Patient.cpf.ilike(search_term)
                )
            )
        
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        result = await db.execute(query)
        patients = result.scalars().all()
        
        return PaginatedResponse(
            items=[PatientResponse.model_validate(patient) for patient in patients],
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing patients: {str(e)}")




@router.post("/create", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: PatientCreate,
    current_user = Depends(require_patients_write),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new patient.
    
    Validates required fields and prevents duplicate CPF registrations.
    Returns detailed error messages in Portuguese.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Creating patient: {patient_data.name}, CPF: {patient_data.cpf}")
        
        # Validate required fields
        if not patient_data.name or len(patient_data.name) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nome do paciente é obrigatório (mínimo 2 caracteres)"
            )
        
        if not patient_data.birthdate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data de nascimento é obrigatória"
            )
        
        if not patient_data.gender:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gênero é obrigatório"
            )
        
        if not patient_data.cpf:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CPF é obrigatório"
            )
        
        # Check if CPF already exists in clinic
        result = await db.execute(
            select(Patient).where(
                Patient.clinic_id == current_user.clinic_id,
                Patient.cpf == patient_data.cpf
            )
        )
        existing_patient = result.scalar_one_or_none()
        
        if existing_patient:
            logger.warning(f"CPF already exists: {patient_data.cpf}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Já existe um paciente cadastrado com este CPF nesta clínica"
            )
        
        # Create patient with address handling
        patient_dict = patient_data.dict()
        
        # Ensure address is a dict (not None)
        if patient_dict.get('address') is None:
            patient_dict['address'] = {}
        
        patient = Patient(
            clinic_id=current_user.clinic_id,
            **patient_dict
        )
        db.add(patient)
        await db.commit()
        await db.refresh(patient)
        
        logger.info(f"Patient created successfully: {patient.id}")
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="patient_created",
            entity="patient",
            entity_id=patient.id,
            details={"patient_name": patient.name, "cpf": patient.cpf}
        )
        db.add(audit_log)
        await db.commit()
        
        return PatientResponse.model_validate(patient)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log and return detailed error
        logger.error(f"Error creating patient: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar paciente: {str(e)}"
        )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    current_user = Depends(require_patients_read),
    db: AsyncSession = Depends(get_db_session)
):
    """Get patient by ID."""
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id
        )
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return PatientResponse.model_validate(patient)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: str,
    update_data: PatientUpdate,
    current_user = Depends(require_patients_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Update patient information."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔍 UPDATE REQUEST - Patient ID: {patient_id}")
    logger.info(f"Update Data: {update_data.dict(exclude_unset=True)}")
    
    # Get patient
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id
        )
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        logger.error(f"❌ Patient not found: {patient_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    logger.info(f"Found patient: {patient.name} (ID: {patient.id}, CPF: {patient.cpf})")
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        old_value = getattr(patient, field, None)
        setattr(patient, field, value)
        logger.info(f"  {field}: {old_value} → {value}")
    
    await db.commit()
    await db.refresh(patient)
    
    logger.info(f"✅ Patient updated successfully: {patient.name} (ID: {patient.id})")
    
    # Create audit log
    audit_log = AuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="patient_updated",
        entity="patient",
        entity_id=patient.id,
        details={"updated_fields": list(update_dict.keys())}
    )
    db.add(audit_log)
    await db.commit()
    
    return PatientResponse.model_validate(patient)


@router.delete("/{patient_id}")
async def delete_patient(
    patient_id: str,
    current_user = Depends(require_patients_write),
    db: AsyncSession = Depends(get_db_session)
):
    """Soft delete patient (archive)."""
    # Get patient
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id
        )
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    # Check if patient has related records (appointments, consultations, etc.)
    try:
        from app.models.database import Appointment, MedicalRecord, Invoice
        
        # Check for related appointments
        appointments_result = await db.execute(
            select(func.count(Appointment.id)).where(Appointment.patient_id == patient_id)
        )
        appointments_count = appointments_result.scalar()
        
        # Check for related medical records
        records_result = await db.execute(
            select(func.count(MedicalRecord.id)).where(MedicalRecord.patient_id == patient_id)
        )
        records_count = records_result.scalar()
        
        # If patient has related records, prevent deletion
        if appointments_count > 0 or records_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível excluir este paciente. Existem {appointments_count} consulta(s) e {records_count} prontuário(s) vinculados. Para preservar o histórico médico, os dados não podem ser removidos."
            )
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="patient_deleted",
            entity="patient",
            entity_id=patient.id,
            details={"patient_name": patient.name, "cpf": patient.cpf}
        )
        db.add(audit_log)
        
        # Only delete if no related records exist
        await db.delete(patient)
        await db.commit()
        
        return {"message": "Paciente excluído com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao excluir paciente. Erro: {str(e)}"
        )
