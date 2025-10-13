"""
Consultations API endpoints for medical consultations (Atendimento Médico).
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
import uuid

from app.core.auth import get_current_user
from app.db.session import get_db_session
from app.models import AuditLog

router = APIRouter()


# Schemas
class VitalSigns(BaseModel):
    blood_pressure: Optional[str] = None
    heart_rate: Optional[str] = None
    temperature: Optional[str] = None
    respiratory_rate: Optional[str] = None
    oxygen_saturation: Optional[str] = None
    weight: Optional[str] = None
    height: Optional[str] = None


class ConsultationCreate(BaseModel):
    patient_id: str
    appointment_id: str
    doctor_id: str
    
    # Anamnese
    chief_complaint: str
    history_present_illness: Optional[str] = None
    past_medical_history: Optional[str] = None
    family_history: Optional[str] = None
    social_history: Optional[str] = None
    medications_in_use: Optional[str] = None
    allergies: Optional[str] = None
    
    # Evolução e Conduta
    physical_examination: Optional[str] = None
    vital_signs: Optional[VitalSigns] = None
    diagnosis: str
    diagnosis_code: Optional[str] = None
    treatment_plan: Optional[str] = None
    follow_up: Optional[str] = None
    notes: Optional[str] = None
    
    # Lock status
    is_locked: bool = False
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None


class ConsultationUpdate(BaseModel):
    chief_complaint: Optional[str] = None
    history_present_illness: Optional[str] = None
    past_medical_history: Optional[str] = None
    family_history: Optional[str] = None
    social_history: Optional[str] = None
    medications_in_use: Optional[str] = None
    allergies: Optional[str] = None
    physical_examination: Optional[str] = None
    vital_signs: Optional[VitalSigns] = None
    diagnosis: Optional[str] = None
    diagnosis_code: Optional[str] = None
    treatment_plan: Optional[str] = None
    follow_up: Optional[str] = None
    notes: Optional[str] = None
    is_locked: Optional[bool] = None
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None


class ConsultationResponse(BaseModel):
    id: str
    patient_id: str
    appointment_id: str
    doctor_id: str
    chief_complaint: str
    history_present_illness: Optional[str]
    past_medical_history: Optional[str]
    family_history: Optional[str]
    social_history: Optional[str]
    medications_in_use: Optional[str]
    allergies: Optional[str]
    physical_examination: Optional[str]
    vital_signs: Optional[dict]
    diagnosis: str
    diagnosis_code: Optional[str]
    treatment_plan: Optional[str]
    follow_up: Optional[str]
    notes: Optional[str]
    is_locked: bool
    locked_at: Optional[datetime]
    locked_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    clinic_id: str
    
    class Config:
        from_attributes = True


@router.post("/", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
async def create_consultation(
    consultation_data: ConsultationCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new medical consultation."""
    try:
        from app.models.database import Consultation, Patient, Appointment
        
        # Verify patient exists and belongs to clinic
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == consultation_data.patient_id,
                Patient.clinic_id == current_user.clinic_id
            )
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
        
        # Verify appointment exists
        appointment_result = await db.execute(
            select(Appointment).where(
                Appointment.id == consultation_data.appointment_id,
                Appointment.clinic_id == current_user.clinic_id
            )
        )
        appointment = appointment_result.scalar_one_or_none()
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        # Create consultation
        consultation = Consultation(
            id=uuid.uuid4(),
            clinic_id=current_user.clinic_id,
            patient_id=uuid.UUID(consultation_data.patient_id),
            appointment_id=uuid.UUID(consultation_data.appointment_id),
            doctor_id=uuid.UUID(consultation_data.doctor_id),
            chief_complaint=consultation_data.chief_complaint,
            history_present_illness=consultation_data.history_present_illness,
            past_medical_history=consultation_data.past_medical_history,
            family_history=consultation_data.family_history,
            social_history=consultation_data.social_history,
            medications_in_use=consultation_data.medications_in_use,
            allergies=consultation_data.allergies,
            physical_examination=consultation_data.physical_examination,
            vital_signs=consultation_data.vital_signs.dict() if consultation_data.vital_signs else {},
            diagnosis=consultation_data.diagnosis,
            diagnosis_code=consultation_data.diagnosis_code,
            treatment_plan=consultation_data.treatment_plan,
            follow_up=consultation_data.follow_up,
            notes=consultation_data.notes,
            is_locked=consultation_data.is_locked,
            locked_at=consultation_data.locked_at,
            locked_by=uuid.UUID(consultation_data.locked_by) if consultation_data.locked_by else None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(consultation)
        await db.commit()
        await db.refresh(consultation)
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="consultation_created",
            entity="consultation",
            entity_id=consultation.id,
            details={"patient_id": str(consultation.patient_id), "diagnosis": consultation.diagnosis}
        )
        db.add(audit_log)
        await db.commit()
        
        return ConsultationResponse(
            id=str(consultation.id),
            patient_id=str(consultation.patient_id),
            appointment_id=str(consultation.appointment_id),
            doctor_id=str(consultation.doctor_id),
            chief_complaint=consultation.chief_complaint,
            history_present_illness=consultation.history_present_illness,
            past_medical_history=consultation.past_medical_history,
            family_history=consultation.family_history,
            social_history=consultation.social_history,
            medications_in_use=consultation.medications_in_use,
            allergies=consultation.allergies,
            physical_examination=consultation.physical_examination,
            vital_signs=consultation.vital_signs,
            diagnosis=consultation.diagnosis,
            diagnosis_code=consultation.diagnosis_code,
            treatment_plan=consultation.treatment_plan,
            follow_up=consultation.follow_up,
            notes=consultation.notes,
            is_locked=consultation.is_locked,
            locked_at=consultation.locked_at,
            locked_by=str(consultation.locked_by) if consultation.locked_by else None,
            created_at=consultation.created_at,
            updated_at=consultation.updated_at,
            clinic_id=str(consultation.clinic_id)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating consultation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create consultation: {str(e)}"
        )


@router.get("/", response_model=List[ConsultationResponse])
async def list_consultations(
    appointment_id: Optional[str] = Query(None, description="Filter by appointment ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    doctor_id: Optional[str] = Query(None, description="Filter by doctor ID"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List consultations with optional filters."""
    try:
        from app.models.database import Consultation
        
        query = select(Consultation).where(Consultation.clinic_id == current_user.clinic_id)
        
        if appointment_id:
            query = query.where(Consultation.appointment_id == uuid.UUID(appointment_id))
        
        if patient_id:
            query = query.where(Consultation.patient_id == uuid.UUID(patient_id))
        
        if doctor_id:
            query = query.where(Consultation.doctor_id == uuid.UUID(doctor_id))
        
        result = await db.execute(query.order_by(Consultation.created_at.desc()))
        consultations = result.scalars().all()
        
        return {
            "items": [
                ConsultationResponse(
                    id=str(c.id),
                    patient_id=str(c.patient_id),
                    appointment_id=str(c.appointment_id),
                    doctor_id=str(c.doctor_id),
                    chief_complaint=c.chief_complaint,
                    history_present_illness=c.history_present_illness,
                    past_medical_history=c.past_medical_history,
                    family_history=c.family_history,
                    social_history=c.social_history,
                    medications_in_use=c.medications_in_use,
                    allergies=c.allergies,
                    physical_examination=c.physical_examination,
                    vital_signs=c.vital_signs,
                    diagnosis=c.diagnosis,
                    diagnosis_code=c.diagnosis_code,
                    treatment_plan=c.treatment_plan,
                    follow_up=c.follow_up,
                    notes=c.notes,
                    is_locked=c.is_locked,
                    locked_at=c.locked_at,
                    locked_by=str(c.locked_by) if c.locked_by else None,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    clinic_id=str(c.clinic_id)
                )
                for c in consultations
            ]
        }
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error listing consultations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list consultations: {str(e)}"
        )


@router.get("/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(
    consultation_id: str,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get consultation by ID."""
    try:
        from app.models.database import Consultation
        
        result = await db.execute(
            select(Consultation).where(
                Consultation.id == uuid.UUID(consultation_id),
                Consultation.clinic_id == current_user.clinic_id
            )
        )
        consultation = result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation not found"
            )
        
        return ConsultationResponse(
            id=str(consultation.id),
            patient_id=str(consultation.patient_id),
            appointment_id=str(consultation.appointment_id),
            doctor_id=str(consultation.doctor_id),
            chief_complaint=consultation.chief_complaint,
            history_present_illness=consultation.history_present_illness,
            past_medical_history=consultation.past_medical_history,
            family_history=consultation.family_history,
            social_history=consultation.social_history,
            medications_in_use=consultation.medications_in_use,
            allergies=consultation.allergies,
            physical_examination=consultation.physical_examination,
            vital_signs=consultation.vital_signs,
            diagnosis=consultation.diagnosis,
            diagnosis_code=consultation.diagnosis_code,
            treatment_plan=consultation.treatment_plan,
            follow_up=consultation.follow_up,
            notes=consultation.notes,
            is_locked=consultation.is_locked,
            locked_at=consultation.locked_at,
            locked_by=str(consultation.locked_by) if consultation.locked_by else None,
            created_at=consultation.created_at,
            updated_at=consultation.updated_at,
            clinic_id=str(consultation.clinic_id)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting consultation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get consultation: {str(e)}"
        )


@router.patch("/{consultation_id}", response_model=ConsultationResponse)
async def update_consultation(
    consultation_id: str,
    update_data: ConsultationUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update consultation."""
    try:
        from app.models.database import Consultation
        
        result = await db.execute(
            select(Consultation).where(
                Consultation.id == uuid.UUID(consultation_id),
                Consultation.clinic_id == current_user.clinic_id
            )
        )
        consultation = result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation not found"
            )
        
        # Check if consultation is locked
        if consultation.is_locked and not update_data.is_locked == False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Consultation is locked and cannot be edited"
            )
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            if field == 'vital_signs' and value:
                setattr(consultation, field, value)
            else:
                setattr(consultation, field, value)
        
        consultation.updated_at = datetime.now()
        
        await db.commit()
        await db.refresh(consultation)
        
        # Create audit log
        audit_log = AuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            action="consultation_updated",
            entity="consultation",
            entity_id=consultation.id,
            details={"updated_fields": list(update_dict.keys())}
        )
        db.add(audit_log)
        await db.commit()
        
        return ConsultationResponse(
            id=str(consultation.id),
            patient_id=str(consultation.patient_id),
            appointment_id=str(consultation.appointment_id),
            doctor_id=str(consultation.doctor_id),
            chief_complaint=consultation.chief_complaint,
            history_present_illness=consultation.history_present_illness,
            past_medical_history=consultation.past_medical_history,
            family_history=consultation.family_history,
            social_history=consultation.social_history,
            medications_in_use=consultation.medications_in_use,
            allergies=consultation.allergies,
            physical_examination=consultation.physical_examination,
            vital_signs=consultation.vital_signs,
            diagnosis=consultation.diagnosis,
            diagnosis_code=consultation.diagnosis_code,
            treatment_plan=consultation.treatment_plan,
            follow_up=consultation.follow_up,
            notes=consultation.notes,
            is_locked=consultation.is_locked,
            locked_at=consultation.locked_at,
            locked_by=str(consultation.locked_by) if consultation.locked_by else None,
            created_at=consultation.created_at,
            updated_at=consultation.updated_at,
            clinic_id=str(consultation.clinic_id)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating consultation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update consultation: {str(e)}"
        )


# Prescription generation endpoint
class PrescriptionMedication(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str
    quantity: str
    instructions: str


class PrescriptionRequest(BaseModel):
    prescription_type: str
    medications: List[PrescriptionMedication]
    notes: Optional[str] = None


@router.post("/{consultation_id}/prescription")
async def generate_prescription(
    consultation_id: str,
    prescription_data: PrescriptionRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate prescription PDF for consultation."""
    try:
        from app.models.database import Consultation, Patient, Clinic, User
        from app.services.prescription_pdf import PrescriptionPDFGenerator
        import base64
        
        # Get consultation
        result = await db.execute(
            select(Consultation).where(
                Consultation.id == uuid.UUID(consultation_id),
                Consultation.clinic_id == current_user.clinic_id
            )
        )
        consultation = result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation not found"
            )
        
        # Get related data
        patient_result = await db.execute(select(Patient).where(Patient.id == consultation.patient_id))
        patient = patient_result.scalar_one_or_none()
        
        doctor_result = await db.execute(select(User).where(User.id == consultation.doctor_id))
        doctor = doctor_result.scalar_one_or_none()
        
        clinic_result = await db.execute(select(Clinic).where(Clinic.id == consultation.clinic_id))
        clinic = clinic_result.scalar_one_or_none()
        
        if not (patient and doctor and clinic):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Missing required data for prescription"
            )
        
        # Prepare prescription data
        prescription_dict = {
            "type": prescription_data.prescription_type,
            "medications": [
                {
                    "name": med.name,
                    "dosage": med.dosage,
                    "frequency": med.frequency,
                    "duration": med.duration,
                    "quantity": med.quantity,
                    "instructions": med.instructions
                }
                for med in prescription_data.medications
            ],
            "notes": prescription_data.notes or "",
            "date": datetime.now().isoformat()
        }
        
        clinic_dict = {
            "name": clinic.name,
            "cnpj": getattr(clinic, 'cnpj', ''),
            "address": getattr(clinic, 'address', ''),
            "phone": getattr(clinic, 'phone', ''),
            "email": getattr(clinic, 'email', '')
        }
        
        doctor_dict = {
            "name": doctor.name,
            "crm": getattr(doctor, 'crm', ''),
            "specialty": getattr(doctor, 'specialty', ''),
            "cpf": getattr(doctor, 'cpf', '')
        }
        
        patient_dict = {
            "name": patient.name,
            "birthdate": patient.birthdate.isoformat() if patient.birthdate else '',
            "cpf": patient.cpf or '',
            "address": patient.address if isinstance(patient.address, dict) else {}
        }
        
        # Generate verification URL (for QR code)
        verification_url = f"{settings.api_url}/prescription/verify/{consultation_id}"
        
        # Generate PDF
        generator = PrescriptionPDFGenerator()
        pdf_bytes = generator.generate_prescription_pdf(
            prescription_data=prescription_dict,
            clinic_data=clinic_dict,
            doctor_data=doctor_dict,
            patient_data=patient_dict,
            qr_code_data=verification_url
        )
        
        # Save to database or cloud storage (simplified for now)
        # In production, upload to S3/GCS and store URL
        
        return {
            "success": True,
            "consultation_id": consultation_id,
            "pdf_base64": base64.b64encode(pdf_bytes).decode('utf-8'),
            "verification_url": verification_url,
            "message": "Prescription PDF generated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating prescription: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate prescription: {str(e)}"
        )


# TISS XML generation endpoint
class SADTItem(BaseModel):
    procedure_code: str
    procedure_name: str
    quantity: int
    justification: str


class TISSRequest(BaseModel):
    items: List[SADTItem]
    justification: str


@router.post("/{consultation_id}/tiss")
async def generate_tiss(
    consultation_id: str,
    tiss_data: TISSRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate TISS XML for consultation."""
    try:
        from app.models.database import Consultation, Patient
        import xml.etree.ElementTree as ET
        
        # Get consultation
        result = await db.execute(
            select(Consultation).where(
                Consultation.id == uuid.UUID(consultation_id),
                Consultation.clinic_id == current_user.clinic_id
            )
        )
        consultation = result.scalar_one_or_none()
        
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation not found"
            )
        
        # Get patient
        patient_result = await db.execute(select(Patient).where(Patient.id == consultation.patient_id))
        patient = patient_result.scalar_one_or_none()
        
        # Generate TISS XML (simplified version)
        # In production, use proper TISS XML schema
        root = ET.Element("GuiaSADT")
        root.set("xmlns", "http://www.ans.gov.br/padroes/tiss/schemas")
        
        # Header
        header = ET.SubElement(root, "cabecalho")
        ET.SubElement(header, "registroANS").text = current_user.clinic_id[:6]
        ET.SubElement(header, "dataEmissao").text = datetime.now().strftime("%Y-%m-%d")
        
        # Patient data
        patient_elem = ET.SubElement(root, "beneficiario")
        ET.SubElement(patient_elem, "nome").text = patient.name
        ET.SubElement(patient_elem, "cpf").text = patient.cpf or ""
        
        # Procedures
        procedures = ET.SubElement(root, "procedimentos")
        for item in tiss_data.items:
            proc = ET.SubElement(procedures, "procedimento")
            ET.SubElement(proc, "codigo").text = item.procedure_code
            ET.SubElement(proc, "descricao").text = item.procedure_name
            ET.SubElement(proc, "quantidade").text = str(item.quantity)
            ET.SubElement(proc, "justificativa").text = item.justification
        
        # Justification
        ET.SubElement(root, "justificativaGeral").text = tiss_data.justification
        
        # Convert to string
        xml_string = ET.tostring(root, encoding='unicode', method='xml')
        
        # Save to database (simplified)
        # In production, submit to insurance APIs
        
        return {
            "success": True,
            "consultation_id": consultation_id,
            "xml_content": xml_string,
            "status": "pending_submission",
            "message": "TISS XML generated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating TISS: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate TISS: {str(e)}"
        )

