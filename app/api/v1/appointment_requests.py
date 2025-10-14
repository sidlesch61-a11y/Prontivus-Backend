"""
Patient Appointment Request API
Allows patients to request appointments (pending staff approval)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from app.db.session import get_db_session
from app.core.auth import AuthDependencies
from app.models.database import Patient, User, Clinic, AuditLog
from app.schemas import BaseSchema
from pydantic import Field

router = APIRouter(prefix="/appointment-requests", tags=["Appointment Requests"])


class AppointmentRequestCreate(BaseSchema):
    """Patient appointment request creation"""
    patient_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None  # If patient selects specific doctor
    preferred_date: str  # Date in YYYY-MM-DD format
    preferred_time: Optional[str] = None  # Time in HH:MM format (optional)
    reason: str = Field(..., min_length=10, max_length=500, description="Reason for appointment")
    notes: Optional[str] = Field(None, max_length=1000)


class AppointmentRequestResponse(BaseSchema):
    """Appointment request response"""
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    doctor_id: Optional[uuid.UUID]
    doctor_name: Optional[str]
    preferred_date: str
    preferred_time: Optional[str]
    reason: str
    notes: Optional[str]
    status: str  # pending, approved, rejected, cancelled
    requested_at: datetime
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[uuid.UUID]
    reviewer_name: Optional[str]
    rejection_reason: Optional[str]
    
    # Approved appointment details
    approved_appointment_id: Optional[uuid.UUID]
    approved_start_time: Optional[datetime]
    approved_end_time: Optional[datetime]


class AppointmentRequestReview(BaseSchema):
    """Review (approve/reject) appointment request"""
    action: str = Field(..., pattern="^(approve|reject)$")
    rejection_reason: Optional[str] = Field(None, min_length=10, max_length=500)
    
    # For approval
    start_time: Optional[datetime] = None  # When appointment should start
    duration_minutes: Optional[int] = Field(30, ge=15, le=180)  # Appointment duration


# Database model for appointment requests
from sqlmodel import SQLModel, Field as SQLField, Column
from sqlalchemy import JSON, Text, DateTime


class AppointmentRequest(SQLModel, table=True):
    """Appointment request model"""
    __tablename__ = "appointment_requests"
    __table_args__ = {'extend_existing': True}
    
    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: uuid.UUID = SQLField(foreign_key="clinics.id")
    patient_id: uuid.UUID = SQLField(foreign_key="patients.id")
    doctor_id: Optional[uuid.UUID] = SQLField(default=None, foreign_key="users.id")
    
    preferred_date: str
    preferred_time: Optional[str] = None
    reason: str = SQLField(sa_column=Column(Text))
    notes: Optional[str] = SQLField(default=None, sa_column=Column(Text))
    
    status: str = SQLField(default="pending")  # pending, approved, rejected, cancelled
    requested_at: datetime = SQLField(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[uuid.UUID] = SQLField(default=None, foreign_key="users.id")
    rejection_reason: Optional[str] = SQLField(default=None, sa_column=Column(Text))
    
    # If approved, link to actual appointment
    approved_appointment_id: Optional[uuid.UUID] = SQLField(default=None, foreign_key="appointments.id")
    approved_start_time: Optional[datetime] = None
    approved_end_time: Optional[datetime] = None


@router.post("/", response_model=AppointmentRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment_request(
    request_data: AppointmentRequestCreate,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new appointment request (patient-facing).
    
    Patients can request appointments which will be reviewed by staff.
    """
    try:
        # Verify patient exists and belongs to clinic
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == request_data.patient_id,
                Patient.clinic_id == current_user.clinic_id
            )
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paciente não encontrado"
            )
        
        # Verify doctor if specified
        doctor = None
        if request_data.doctor_id:
            doctor_result = await db.execute(
                select(User).where(
                    User.id == request_data.doctor_id,
                    User.clinic_id == current_user.clinic_id,
                    or_(User.role == "doctor", User.role == "admin")
                )
            )
            doctor = doctor_result.scalar_one_or_none()
            
            if not doctor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Médico não encontrado"
                )
        
        # Create appointment request
        appointment_request = AppointmentRequest(
            clinic_id=current_user.clinic_id,
            patient_id=request_data.patient_id,
            doctor_id=request_data.doctor_id,
            preferred_date=request_data.preferred_date,
            preferred_time=request_data.preferred_time,
            reason=request_data.reason,
            notes=request_data.notes,
            status="pending",
            requested_at=datetime.now()
        )
        
        db.add(appointment_request)
        await db.commit()
        await db.refresh(appointment_request)
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="appointment_request_created",
            entity="appointment_request",
            entity_id=appointment_request.id,
            details={
                "patient_id": str(request_data.patient_id),
                "doctor_id": str(request_data.doctor_id) if request_data.doctor_id else None,
                "preferred_date": request_data.preferred_date
            }
        )
        db.add(audit_log)
        await db.commit()
        
        # Build response
        response = AppointmentRequestResponse(
            id=appointment_request.id,
            patient_id=appointment_request.patient_id,
            patient_name=patient.name,
            doctor_id=appointment_request.doctor_id,
            doctor_name=doctor.name if doctor else None,
            preferred_date=appointment_request.preferred_date,
            preferred_time=appointment_request.preferred_time,
            reason=appointment_request.reason,
            notes=appointment_request.notes,
            status=appointment_request.status,
            requested_at=appointment_request.requested_at,
            reviewed_at=None,
            reviewed_by=None,
            reviewer_name=None,
            rejection_reason=None,
            approved_appointment_id=None,
            approved_start_time=None,
            approved_end_time=None
        )
        
        return response
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        print(f"Error creating appointment request: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao criar solicitação de consulta: {str(e)}"
        )


@router.get("/", response_model=List[AppointmentRequestResponse])
async def list_appointment_requests(
    status_filter: Optional[str] = Query(None, description="Filter by status (pending/approved/rejected/cancelled)"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    List appointment requests.
    
    - Patients can only see their own requests
    - Staff can see all requests for their clinic
    """
    try:
        query = select(AppointmentRequest).where(AppointmentRequest.clinic_id == current_user.clinic_id)
        
        # If user is patient, only show their requests
        user_role = getattr(current_user, "role", "").lower()
        if user_role == "patient":
            # Find patient record for this user
            patient_result = await db.execute(
                select(Patient).where(
                    Patient.email == current_user.email,
                    Patient.clinic_id == current_user.clinic_id
                )
            )
            patient = patient_result.scalar_one_or_none()
            if patient:
                query = query.where(AppointmentRequest.patient_id == patient.id)
            else:
                return []  # Patient record not found
        
        # Apply filters
        if status_filter:
            query = query.where(AppointmentRequest.status == status_filter)
        
        if patient_id:
            query = query.where(AppointmentRequest.patient_id == patient_id)
        
        query = query.order_by(AppointmentRequest.requested_at.desc())
        
        result = await db.execute(query)
        requests = result.scalars().all()
        
        # Build responses
        response_list = []
        for req in requests:
            # Get patient name
            patient_result = await db.execute(
                select(Patient).where(Patient.id == req.patient_id)
            )
            patient = patient_result.scalar_one_or_none()
            
            # Get doctor name if specified
            doctor_name = None
            if req.doctor_id:
                doctor_result = await db.execute(
                    select(User).where(User.id == req.doctor_id)
                )
                doctor = doctor_result.scalar_one_or_none()
                if doctor:
                    doctor_name = doctor.name
            
            # Get reviewer name if reviewed
            reviewer_name = None
            if req.reviewed_by:
                reviewer_result = await db.execute(
                    select(User).where(User.id == req.reviewed_by)
                )
                reviewer = reviewer_result.scalar_one_or_none()
                if reviewer:
                    reviewer_name = reviewer.name
            
            response = AppointmentRequestResponse(
                id=req.id,
                patient_id=req.patient_id,
                patient_name=patient.name if patient else "Unknown",
                doctor_id=req.doctor_id,
                doctor_name=doctor_name,
                preferred_date=req.preferred_date,
                preferred_time=req.preferred_time,
                reason=req.reason,
                notes=req.notes,
                status=req.status,
                requested_at=req.requested_at,
                reviewed_at=req.reviewed_at,
                reviewed_by=req.reviewed_by,
                reviewer_name=reviewer_name,
                rejection_reason=req.rejection_reason,
                approved_appointment_id=req.approved_appointment_id,
                approved_start_time=req.approved_start_time,
                approved_end_time=req.approved_end_time
            )
            
            response_list.append(response)
        
        return response_list
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao listar solicitações: {str(e)}"
        )


@router.post("/{request_id}/review", response_model=AppointmentRequestResponse)
async def review_appointment_request(
    request_id: str,
    review_data: AppointmentRequestReview,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Review (approve/reject) an appointment request.
    
    Only staff (admin, doctor, secretary) can review requests.
    """
    try:
        # Check permissions
        user_role = getattr(current_user, "role", "").lower()
        if user_role not in ["admin", "doctor", "secretary", "superadmin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Somente membros da equipe podem revisar solicitações"
            )
        
        # Get appointment request
        result = await db.execute(
            select(AppointmentRequest).where(
                AppointmentRequest.id == request_id,
                AppointmentRequest.clinic_id == current_user.clinic_id
            )
        )
        appointment_request = result.scalar_one_or_none()
        
        if not appointment_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação de consulta não encontrada"
            )
        
        if appointment_request.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Solicitação já foi revisada (status: {appointment_request.status})"
            )
        
        # Update request status
        appointment_request.status = "approved" if review_data.action == "approve" else "rejected"
        appointment_request.reviewed_at = datetime.now()
        appointment_request.reviewed_by = current_user.id
        
        if review_data.action == "reject":
            appointment_request.rejection_reason = review_data.rejection_reason
        else:
            # Create actual appointment
            from app.models.database import Appointment
            
            if not review_data.start_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Hora de início da consulta é obrigatória para aprovação"
                )
            
            end_time = review_data.start_time + timedelta(minutes=review_data.duration_minutes)
            
            appointment = Appointment(
                clinic_id=current_user.clinic_id,
                patient_id=appointment_request.patient_id,
                doctor_id=appointment_request.doctor_id or current_user.id,
                start_time=review_data.start_time,
                end_time=end_time,
                status="scheduled"
            )
            
            db.add(appointment)
            await db.flush()
            
            appointment_request.approved_appointment_id = appointment.id
            appointment_request.approved_start_time = review_data.start_time
            appointment_request.approved_end_time = end_time
        
        await db.commit()
        await db.refresh(appointment_request)
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action=f"appointment_request_{review_data.action}d",
            entity="appointment_request",
            entity_id=appointment_request.id,
            details={
                "action": review_data.action,
                "patient_id": str(appointment_request.patient_id),
                "appointment_id": str(appointment_request.approved_appointment_id) if appointment_request.approved_appointment_id else None
            }
        )
        db.add(audit_log)
        await db.commit()
        
        # Send notification to patient
        try:
            from app.services.notification_service import notification_service
            import logging
            logger = logging.getLogger(__name__)
            
            # Get clinic name
            clinic_result = await db.execute(select(Clinic).where(Clinic.id == current_user.clinic_id))
            clinic = clinic_result.scalar_one_or_none()
            clinic_name = clinic.name if clinic else "Clínica"
            
            # Get patient for notification
            patient_for_notif = await db.execute(select(Patient).where(Patient.id == appointment_request.patient_id))
            patient_notif_obj = patient_for_notif.scalar_one_or_none()
            
            if patient_notif_obj:
                if review_data.action == "approve":
                    # Get doctor name
                    doctor_id = appointment_request.doctor_id or current_user.id
                    doctor_result = await db.execute(select(User).where(User.id == doctor_id))
                    doctor = doctor_result.scalar_one_or_none()
                    
                    await notification_service.send_appointment_request_notification(
                        patient_email=patient_notif_obj.email,
                        patient_phone=patient_notif_obj.phone,
                        patient_name=patient_notif_obj.name,
                        action="approved",
                        appointment_datetime=review_data.start_time,
                        doctor_name=doctor.name if doctor else "Médico",
                        clinic_name=clinic_name
                    )
                else:
                    await notification_service.send_appointment_request_notification(
                        patient_email=patient_notif_obj.email,
                        patient_phone=patient_notif_obj.phone,
                        patient_name=patient_notif_obj.name,
                        action="rejected",
                        rejection_reason=review_data.rejection_reason,
                        clinic_name=clinic_name
                    )
        except Exception as notif_error:
            # Log notification error but don't fail the request
            logger.error(f"Failed to send notification: {str(notif_error)}")
        
        # Build response
        patient_result = await db.execute(
            select(Patient).where(Patient.id == appointment_request.patient_id)
        )
        patient = patient_result.scalar_one()
        
        doctor_name = None
        if appointment_request.doctor_id:
            doctor_result = await db.execute(
                select(User).where(User.id == appointment_request.doctor_id)
            )
            doctor = doctor_result.scalar_one_or_none()
            if doctor:
                doctor_name = doctor.name
        
        response = AppointmentRequestResponse(
            id=appointment_request.id,
            patient_id=appointment_request.patient_id,
            patient_name=patient.name,
            doctor_id=appointment_request.doctor_id,
            doctor_name=doctor_name,
            preferred_date=appointment_request.preferred_date,
            preferred_time=appointment_request.preferred_time,
            reason=appointment_request.reason,
            notes=appointment_request.notes,
            status=appointment_request.status,
            requested_at=appointment_request.requested_at,
            reviewed_at=appointment_request.reviewed_at,
            reviewed_by=appointment_request.reviewed_by,
            reviewer_name=current_user.name,
            rejection_reason=appointment_request.rejection_reason,
            approved_appointment_id=appointment_request.approved_appointment_id,
            approved_start_time=appointment_request.approved_start_time,
            approved_end_time=appointment_request.approved_end_time
        )
        
        return response
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        print(f"Error reviewing appointment request: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao revisar solicitação: {str(e)}"
        )


@router.delete("/{request_id}")
async def cancel_appointment_request(
    request_id: str,
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Cancel an appointment request (patient-facing).
    
    Patients can only cancel their own pending requests.
    """
    try:
        # Get appointment request
        result = await db.execute(
            select(AppointmentRequest).where(
                AppointmentRequest.id == request_id,
                AppointmentRequest.clinic_id == current_user.clinic_id
            )
        )
        appointment_request = result.scalar_one_or_none()
        
        if not appointment_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação não encontrada"
            )
        
        # Check permissions
        user_role = getattr(current_user, "role", "").lower()
        if user_role == "patient":
            # Verify patient owns this request
            patient_result = await db.execute(
                select(Patient).where(
                    Patient.email == current_user.email,
                    Patient.clinic_id == current_user.clinic_id
                )
            )
            patient = patient_result.scalar_one_or_none()
            
            if not patient or patient.id != appointment_request.patient_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Você só pode cancelar suas próprias solicitações"
                )
        
        if appointment_request.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Somente solicitações pendentes podem ser canceladas"
            )
        
        # Mark as cancelled
        appointment_request.status = "cancelled"
        await db.commit()
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="appointment_request_cancelled",
            entity="appointment_request",
            entity_id=appointment_request.id,
            details={"patient_id": str(appointment_request.patient_id)}
        )
        db.add(audit_log)
        await db.commit()
        
        return {"message": "Solicitação cancelada com sucesso"}
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao cancelar solicitação: {str(e)}"
        )


@router.get("/stats")
async def get_appointment_request_stats(
    current_user = Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get statistics for appointment requests."""
    try:
        from sqlalchemy import func, cast, String
        from datetime import date
        
        clinic_id = current_user.clinic_id
        today = date.today()
        
        # Total requests
        total_requests = await db.scalar(
            select(func.count(AppointmentRequest.id))
            .where(AppointmentRequest.clinic_id == clinic_id)
        ) or 0
        
        # Pending requests
        pending_requests = await db.scalar(
            select(func.count(AppointmentRequest.id))
            .where(
                and_(
                    AppointmentRequest.clinic_id == clinic_id,
                    cast(AppointmentRequest.status, String) == "pending"
                )
            )
        ) or 0
        
        # Approved requests
        approved_requests = await db.scalar(
            select(func.count(AppointmentRequest.id))
            .where(
                and_(
                    AppointmentRequest.clinic_id == clinic_id,
                    cast(AppointmentRequest.status, String) == "approved"
                )
            )
        ) or 0
        
        # Rejected requests
        rejected_requests = await db.scalar(
            select(func.count(AppointmentRequest.id))
            .where(
                and_(
                    AppointmentRequest.clinic_id == clinic_id,
                    cast(AppointmentRequest.status, String) == "rejected"
                )
            )
        ) or 0
        
        # Requests today
        requests_today = await db.scalar(
            select(func.count(AppointmentRequest.id))
            .where(
                and_(
                    AppointmentRequest.clinic_id == clinic_id,
                    func.date(AppointmentRequest.requested_at) == today
                )
            )
        ) or 0
        
        # Pending from today
        pending_today = await db.scalar(
            select(func.count(AppointmentRequest.id))
            .where(
                and_(
                    AppointmentRequest.clinic_id == clinic_id,
                    cast(AppointmentRequest.status, String) == "pending",
                    func.date(AppointmentRequest.requested_at) == today
                )
            )
        ) or 0
        
        # Approved this week
        week_start = today - timedelta(days=today.weekday())
        approved_this_week = await db.scalar(
            select(func.count(AppointmentRequest.id))
            .where(
                and_(
                    AppointmentRequest.clinic_id == clinic_id,
                    cast(AppointmentRequest.status, String) == "approved",
                    func.date(AppointmentRequest.reviewed_at) >= week_start
                )
            )
        ) or 0
        
        return {
            "total_requests": total_requests,
            "pending_requests": pending_requests,
            "approved_requests": approved_requests,
            "rejected_requests": rejected_requests,
            "requests_today": requests_today,
            "pending_today": pending_today,
            "approved_this_week": approved_this_week
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting appointment request stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao buscar estatísticas: {str(e)}"
        )