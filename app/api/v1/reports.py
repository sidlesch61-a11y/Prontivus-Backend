"""
Reports and Analytics API endpoints for BI Dashboard.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Any
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, cast, String, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthDependencies
from app.db.session import get_db_session
from app.models.database import Patient, Appointment, Invoice, MedicalRecord

router = APIRouter(tags=["reports"])


@router.get("/appointments-by-week")
async def get_appointments_by_week(
    current_user=Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get appointment counts by week for the last 12 weeks."""
    clinic_id = current_user.clinic_id
    today = date.today()
    
    # Calculate last 12 weeks
    weeks_data = []
    for i in range(11, -1, -1):
        week_start = today - timedelta(days=today.weekday() + (i * 7))
        week_end = week_start + timedelta(days=6)
        
        # Count appointments in this week
        count = await db.scalar(
            select(func.count(Appointment.id))
            .where(Appointment.clinic_id == clinic_id)
            .where(func.date(Appointment.start_time) >= week_start)
            .where(func.date(Appointment.start_time) <= week_end)
        ) or 0
        
        week_label = f"Week {12-i}"
        weeks_data.append({
            "week": week_label,
            "appointments": count
        })
    
    return weeks_data


@router.get("/revenue-by-month")
async def get_revenue_by_month(
    current_user=Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get revenue by month for the last 12 months."""
    clinic_id = current_user.clinic_id
    today = date.today()
    
    months_data = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    for i in range(11, -1, -1):
        # Calculate month
        target_month = today.month - i
        target_year = today.year
        
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        while target_month > 12:
            target_month -= 12
            target_year += 1
        
        # Get first and last day of month
        first_day = date(target_year, target_month, 1)
        if target_month == 12:
            last_day = date(target_year, 12, 31)
        else:
            last_day = date(target_year, target_month + 1, 1) - timedelta(days=1)
        
        # Sum revenue for this month
        revenue = await db.scalar(
            select(func.sum(Invoice.amount))
            .where(Invoice.clinic_id == clinic_id)
            .where(cast(Invoice.status, String) == "paid")
            .where(func.date(Invoice.created_at) >= first_day)
            .where(func.date(Invoice.created_at) <= last_day)
        ) or 0.0
        
        months_data.append({
            "month": month_names[target_month - 1],
            "revenue": float(revenue)
        })
    
    return months_data


@router.get("/patient-demographics")
async def get_patient_demographics(
    current_user=Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get patient demographics by gender."""
    clinic_id = current_user.clinic_id
    
    # Count by gender
    result = await db.execute(
        select(Patient.gender, func.count(Patient.id).label('count'))
        .where(Patient.clinic_id == clinic_id)
        .group_by(Patient.gender)
    )
    
    gender_counts = result.all()
    
    demographics_data = []
    gender_labels = {
        "male": "Male",
        "female": "Female",
        "other": "Other",
        "unknown": "Not Specified"
    }
    
    for gender, count in gender_counts:
        demographics_data.append({
            "name": gender_labels.get(gender, gender.capitalize()),
            "value": count
        })
    
    return demographics_data


@router.get("/appointments-by-status")
async def get_appointments_by_status(
    current_user=Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get appointment counts by status."""
    clinic_id = current_user.clinic_id
    
    # Count by status
    result = await db.execute(
        select(
            cast(Appointment.status, String).label('status'),
            func.count(Appointment.id).label('count')
        )
        .where(Appointment.clinic_id == clinic_id)
        .group_by(cast(Appointment.status, String))
    )
    
    status_counts = result.all()
    
    status_data = []
    for status, count in status_counts:
        status_data.append({
            "name": status.capitalize(),
            "value": count
        })
    
    return status_data


@router.get("/top-doctors")
async def get_top_doctors(
    current_user=Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get top doctors by appointment count."""
    clinic_id = current_user.clinic_id
    
    # This month
    first_day_of_month = date.today().replace(day=1)
    
    result = await db.execute(
        select(
            Appointment.doctor_id,
            func.count(Appointment.id).label('count')
        )
        .where(Appointment.clinic_id == clinic_id)
        .where(func.date(Appointment.start_time) >= first_day_of_month)
        .group_by(Appointment.doctor_id)
        .order_by(func.count(Appointment.id).desc())
        .limit(5)
    )
    
    doctor_counts = result.all()
    
    # Get doctor names
    from app.models.database import User
    
    doctors_data = []
    for doctor_id, count in doctor_counts:
        doctor_result = await db.execute(
            select(User.name).where(User.id == doctor_id)
        )
        doctor_name = doctor_result.scalar()
        
        if doctor_name:
            doctors_data.append({
                "doctor": doctor_name,
                "appointments": count
            })
    
    return doctors_data


@router.get("/monthly-summary")
async def get_monthly_summary(
    current_user=Depends(AuthDependencies.get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get summary statistics for the current month."""
    clinic_id = current_user.clinic_id
    first_day_of_month = date.today().replace(day=1)
    
    # Total appointments this month
    appointments_count = await db.scalar(
        select(func.count(Appointment.id))
        .where(Appointment.clinic_id == clinic_id)
        .where(func.date(Appointment.start_time) >= first_day_of_month)
    ) or 0
    
    # New patients this month
    new_patients = await db.scalar(
        select(func.count(Patient.id))
        .where(Patient.clinic_id == clinic_id)
        .where(func.date(Patient.created_at) >= first_day_of_month)
    ) or 0
    
    # Revenue this month
    revenue = await db.scalar(
        select(func.sum(Invoice.amount))
        .where(Invoice.clinic_id == clinic_id)
        .where(cast(Invoice.status, String) == "paid")
        .where(func.date(Invoice.created_at) >= first_day_of_month)
    ) or 0.0
    
    # Medical records this month
    records_count = await db.scalar(
        select(func.count(MedicalRecord.id))
        .where(MedicalRecord.clinic_id == clinic_id)
        .where(func.date(MedicalRecord.created_at) >= first_day_of_month)
    ) or 0
    
    return {
        "appointments": appointments_count,
        "new_patients": new_patients,
        "revenue": float(revenue),
        "medical_records": records_count
    }

