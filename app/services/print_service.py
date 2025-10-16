"""
Print service for generating and printing medical documents.
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from sqlmodel import Session, select
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from app.models.print_models import PrintLog, PrintRequest, PrintResponse
from app.models.database import Consultation, Patient, User, Clinic
from app.services.pdf_generator import generate_prescription_pdf, generate_certificate_pdf


class PrintService:
    """Service for handling document printing."""
    
    def __init__(self):
        self.font_config = FontConfiguration()
        self.temp_dir = "temp_prints"
        os.makedirs(self.temp_dir, exist_ok=True)
    
    async def print_document(
        self, 
        db: Session, 
        consultation_id: uuid.UUID, 
        document_type: str, 
        printed_by: uuid.UUID,
        preview: bool = False,
        printer_name: Optional[str] = None
    ) -> PrintResponse:
        """Print a medical document."""
        
        # Get consultation data
        consultation = await db.get(Consultation, consultation_id)
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consulta não encontrada"
            )
        
        # Get patient data
        patient = await db.get(Patient, consultation.patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paciente não encontrado"
            )
        
        # Get doctor data
        doctor = await db.get(User, consultation.doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Médico não encontrado"
            )
        
        # Get clinic data
        clinic = await db.get(Clinic, consultation.clinic_id)
        if not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clínica não encontrada"
            )
        
        try:
            # Generate PDF content based on document type
            pdf_content = await self._generate_document_content(
                consultation, patient, doctor, clinic, document_type
            )
            
            if preview:
                # Return preview URL
                preview_url = await self._save_preview(pdf_content, document_type)
                return PrintResponse(
                    success=True,
                    message="Visualização gerada com sucesso",
                    preview_url=preview_url
                )
            else:
                # Print document
                print_id = await self._print_document(
                    db, consultation_id, document_type, printed_by, 
                    pdf_content, printer_name
                )
                return PrintResponse(
                    success=True,
                    message="Documento enviado para impressão",
                    print_id=print_id
                )
                
        except Exception as e:
            # Log error
            await self._log_print_error(
                db, consultation_id, document_type, printed_by, str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao imprimir documento: {str(e)}"
            )
    
    async def _generate_document_content(
        self, 
        consultation: Consultation, 
        patient: Patient, 
        doctor: User, 
        clinic: Clinic,
        document_type: str
    ) -> bytes:
        """Generate PDF content for the document."""
        
        # Get patient city from address or use default
        patient_city = "Não informado"
        if patient.address and isinstance(patient.address, dict):
            patient_city = patient.address.get("city", "Não informado")
        
        if document_type == "prescription":
            return await generate_prescription_pdf(
                consultation, patient, doctor, clinic, patient_city
            )
        elif document_type == "certificate":
            return await generate_certificate_pdf(
                consultation, patient, doctor, clinic, patient_city
            )
        elif document_type == "exam_request":
            return await self._generate_exam_request_pdf(
                consultation, patient, doctor, clinic, patient_city
            )
        elif document_type == "referral":
            return await self._generate_referral_pdf(
                consultation, patient, doctor, clinic, patient_city
            )
        else:
            raise ValueError(f"Tipo de documento não suportado: {document_type}")
    
    async def _generate_exam_request_pdf(
        self, consultation: Consultation, patient: Patient, 
        doctor: User, clinic: Clinic, patient_city: str
    ) -> bytes:
        """Generate exam request PDF."""
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Solicitação de Exame</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #2563eb; }}
                .clinic-info {{ font-size: 12px; color: #666; margin-top: 10px; }}
                .patient-info {{ margin-bottom: 20px; }}
                .patient-info h3 {{ color: #2563eb; margin-bottom: 10px; }}
                .exam-details {{ margin: 20px 0; }}
                .exam-details h4 {{ color: #374151; margin-bottom: 10px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 10px; color: #666; }}
                .signature {{ margin-top: 40px; }}
                .signature-line {{ border-bottom: 1px solid #000; width: 300px; margin: 20px 0 5px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">{clinic.name}</div>
                <div class="clinic-info">
                    <p><strong>Cidade:</strong> {patient_city}</p>
                    <p>CNPJ: {clinic.cnpj_cpf or 'Não informado'}</p>
                </div>
            </div>
            
            <div class="patient-info">
                <h3>Dados do Paciente</h3>
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            
            <div class="exam-details">
                <h4>Solicitação de Exame</h4>
                <p><strong>Data da Consulta:</strong> {consultation.created_at.strftime('%d/%m/%Y')}</p>
                <p><strong>Médico:</strong> Dr(a). {doctor.name}</p>
                <p><strong>CRM:</strong> {doctor.role}</p>
                
                <h4>Exames Solicitados:</h4>
                <p>{consultation.treatment_plan or 'Exames conforme prescrição médica'}</p>
                
                <h4>Observações:</h4>
                <p>{consultation.notes or 'Nenhuma observação adicional'}</p>
            </div>
            
            <div class="signature">
                <div class="signature-line"></div>
                <p>Dr(a). {doctor.name} - CRM: {doctor.role}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            
            <div class="footer">
                <p>Prontivus — Cuidado Inteligente</p>
            </div>
        </body>
        </html>
        """
        
        html = HTML(string=html_content)
        return html.write_pdf()
    
    async def _generate_referral_pdf(
        self, consultation: Consultation, patient: Patient, 
        doctor: User, clinic: Clinic, patient_city: str
    ) -> bytes:
        """Generate referral PDF."""
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Encaminhamento Médico</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #2563eb; }}
                .clinic-info {{ font-size: 12px; color: #666; margin-top: 10px; }}
                .patient-info {{ margin-bottom: 20px; }}
                .patient-info h3 {{ color: #2563eb; margin-bottom: 10px; }}
                .referral-details {{ margin: 20px 0; }}
                .referral-details h4 {{ color: #374151; margin-bottom: 10px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 10px; color: #666; }}
                .signature {{ margin-top: 40px; }}
                .signature-line {{ border-bottom: 1px solid #000; width: 300px; margin: 20px 0 5px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">{clinic.name}</div>
                <div class="clinic-info">
                    <p><strong>Cidade:</strong> {patient_city}</p>
                    <p>CNPJ: {clinic.cnpj_cpf or 'Não informado'}</p>
                </div>
            </div>
            
            <div class="patient-info">
                <h3>Dados do Paciente</h3>
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            
            <div class="referral-details">
                <h4>Encaminhamento</h4>
                <p><strong>Data da Consulta:</strong> {consultation.created_at.strftime('%d/%m/%Y')}</p>
                <p><strong>Médico Solicitante:</strong> Dr(a). {doctor.name}</p>
                <p><strong>CRM:</strong> {doctor.role}</p>
                
                <h4>Motivo do Encaminhamento:</h4>
                <p>{consultation.treatment_plan or 'Encaminhamento conforme avaliação médica'}</p>
                
                <h4>Observações:</h4>
                <p>{consultation.notes or 'Nenhuma observação adicional'}</p>
            </div>
            
            <div class="signature">
                <div class="signature-line"></div>
                <p>Dr(a). {doctor.name} - CRM: {doctor.role}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            
            <div class="footer">
                <p>Prontivus — Cuidado Inteligente</p>
            </div>
        </body>
        </html>
        """
        
        html = HTML(string=html_content)
        return html.write_pdf()
    
    async def _save_preview(self, pdf_content: bytes, document_type: str) -> str:
        """Save PDF preview and return URL."""
        filename = f"preview_{document_type}_{uuid.uuid4().hex[:8]}.pdf"
        filepath = os.path.join(self.temp_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(pdf_content)
        
        return f"/temp_prints/{filename}"
    
    async def _print_document(
        self, 
        db: Session, 
        consultation_id: uuid.UUID, 
        document_type: str, 
        printed_by: uuid.UUID,
        pdf_content: bytes,
        printer_name: Optional[str] = None
    ) -> uuid.UUID:
        """Print document and log the action."""
        
        # Create print log
        print_log = PrintLog(
            consultation_id=consultation_id,
            document_type=document_type,
            printed_by=printed_by,
            printer_name=printer_name,
            pages_count=1,
            status="success"
        )
        
        db.add(print_log)
        await db.commit()
        await db.refresh(print_log)
        
        # Here you would integrate with actual printer
        # For now, we'll just save to temp directory
        filename = f"print_{document_type}_{print_log.id}.pdf"
        filepath = os.path.join(self.temp_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(pdf_content)
        
        return print_log.id
    
    async def _log_print_error(
        self, 
        db: Session, 
        consultation_id: uuid.UUID, 
        document_type: str, 
        printed_by: uuid.UUID,
        error_message: str
    ):
        """Log print error."""
        print_log = PrintLog(
            consultation_id=consultation_id,
            document_type=document_type,
            printed_by=printed_by,
            status="error",
            error_message=error_message
        )
        
        db.add(print_log)
        await db.commit()


# Global print service instance
print_service = PrintService()
