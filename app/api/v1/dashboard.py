"""
Dashboard API endpoints for statistics and overview data.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Any
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthDependencies
from app.db.session import get_db_session
from app.models.database import Patient, Appointment, Invoice, MedicalRecord

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

require_dashboard_read = AuthDependencies.require_permission("dashboard:read")


@router.get("/stats", response_model=Dict[str, Any])
async def get_dashboard_stats(
    current_user=Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get dashboard statistics for the current user's clinic."""
    clinic_id = current_user.clinic_id
    today = date.today()
    
    # Total patients count
    patients_count = await db.scalar(
        select(func.count(Patient.id))
        .where(Patient.clinic_id == clinic_id)
    ) or 0
    
    # Today's appointments count
    today_appointments = await db.scalar(
        select(func.count(Appointment.id))
        .where(Appointment.clinic_id == clinic_id)
        .where(func.date(Appointment.start_time) == today)
    ) or 0
    
    # Completed appointments today
    completed_today = await db.scalar(
        select(func.count(Appointment.id))
        .where(Appointment.clinic_id == clinic_id)
        .where(func.date(Appointment.start_time) == today)
        .where(cast(Appointment.status, String) == "completed")
    ) or 0
    
    # Total medical records count
    records_count = await db.scalar(
        select(func.count(MedicalRecord.id))
        .where(MedicalRecord.clinic_id == clinic_id)
    ) or 0
    
    # This month's revenue (from invoices)
    first_day_of_month = today.replace(day=1)
    revenue = await db.scalar(
        select(func.sum(Invoice.amount))
        .where(Invoice.clinic_id == clinic_id)
        .where(cast(Invoice.status, String) == "paid")
        .where(func.date(Invoice.created_at) >= first_day_of_month)
    ) or 0.0
    
    # Last month's metrics for comparison
    last_month_start = (first_day_of_month - timedelta(days=1)).replace(day=1)
    last_month_end = first_day_of_month - timedelta(days=1)
    
    last_month_patients = await db.scalar(
        select(func.count(Patient.id))
        .where(Patient.clinic_id == clinic_id)
        .where(func.date(Patient.created_at) < first_day_of_month)
    ) or 1  # Avoid division by zero
    
    last_month_revenue = await db.scalar(
        select(func.sum(Invoice.amount))
        .where(Invoice.clinic_id == clinic_id)
        .where(cast(Invoice.status, String) == "paid")
        .where(func.date(Invoice.created_at) >= last_month_start)
        .where(func.date(Invoice.created_at) <= last_month_end)
    ) or 1.0  # Avoid division by zero
    
    # Calculate percentage changes
    patients_change = round(((patients_count - last_month_patients) / last_month_patients) * 100, 1) if last_month_patients > 0 else 0
    revenue_change = round(((revenue - last_month_revenue) / last_month_revenue) * 100, 1) if last_month_revenue > 0 else 0
    
    return {
        "total_patients": patients_count,
        "patients_change": f"+{patients_change}%" if patients_change > 0 else f"{patients_change}%",
        "today_appointments": today_appointments,
        "completed_appointments": completed_today,
        "total_records": records_count,
        "records_this_week": 0,  # Placeholder
        "monthly_revenue": float(revenue),
        "revenue_change": f"+{revenue_change}%" if revenue_change > 0 else f"{revenue_change}%"
    }


@router.get("/today-appointments", response_model=List[Dict[str, Any]])
async def get_today_appointments(
    current_user=Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get today's appointments for the dashboard."""
    clinic_id = current_user.clinic_id
    today = date.today()
    
    # Get today's appointments with patient information
    query = (
        select(Appointment, Patient)
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(Appointment.clinic_id == clinic_id)
        .where(func.date(Appointment.start_time) == today)
        .order_by(Appointment.start_time)
        .limit(5)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    appointments = []
    for appointment, patient in rows:
        appointments.append({
            "id": str(appointment.id),
            "patient": patient.name,
            "time": appointment.start_time.strftime("%H:%M"),
            "type": "Consulta",
            "status": appointment.status
        })
    
    return appointments


@router.get("/recent-patients", response_model=List[Dict[str, Any]])
async def get_recent_patients(
    current_user=Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get recently created or updated patients for the dashboard."""
    clinic_id = current_user.clinic_id
    
    # Get recent patients
    query = (
        select(Patient)
        .where(Patient.clinic_id == clinic_id)
        .order_by(Patient.updated_at.desc())
        .limit(5)
    )
    
    result = await db.execute(query)
    patients = result.scalars().all()
    
    recent_patients = []
    today = date.today()
    
    for patient in patients:
        # Calculate how long ago the patient was updated
        days_ago = (today - patient.updated_at.date()).days
        if days_ago == 0:
            last_visit = "Today"
        elif days_ago == 1:
            last_visit = "Yesterday"
        else:
            last_visit = f"{days_ago} days ago"
        
        recent_patients.append({
            "id": str(patient.id),
            "name": patient.name,
            "lastVisit": last_visit,
            "status": "Active"
        })
    
    return recent_patients
