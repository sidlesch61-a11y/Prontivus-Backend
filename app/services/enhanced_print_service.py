"""
Enhanced print service for generating and printing medical documents.
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlmodel import Session, select

# Conditional import for weasyprint
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    HTML = None
    CSS = None
    FontConfiguration = None

from app.models.print_models import PrintLog, PrintRequest, PrintResponse
from app.models.database import Consultation, Patient, User, Clinic


class EnhancedPrintService:
    """Enhanced service for handling document printing with all document types."""
    
    def __init__(self):
        if not WEASYPRINT_AVAILABLE:
            raise ImportError("weasyprint is not available. Please install it with: pip install weasyprint")
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
        
        patient = await db.get(Patient, consultation.patient_id)
        doctor = await db.get(User, consultation.doctor_id)
        clinic = await db.get(Clinic, consultation.clinic_id)

        if not patient or not doctor or not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dados de paciente, médico ou clínica incompletos."
            )

        try:
            pdf_content = b""
            filename = f"{document_type}_{patient.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            
            # Generate PDF based on document type
            if document_type == "prescription":
                pdf_content = await self._generate_prescription_pdf(patient, doctor, clinic, consultation)
            elif document_type == "prescription_controlled":
                pdf_content = await self._generate_controlled_prescription_pdf(patient, doctor, clinic, consultation)
            elif document_type == "certificate":
                pdf_content = await self._generate_certificate_pdf(patient, doctor, clinic, consultation)
            elif document_type == "exam_request":
                pdf_content = await self._generate_exam_request_pdf(patient, doctor, clinic, consultation)
            elif document_type == "referral":
                pdf_content = await self._generate_referral_pdf(patient, doctor, clinic, consultation)
            elif document_type == "sadt_guide":
                pdf_content = await self._generate_sadt_guide_pdf(patient, doctor, clinic, consultation)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tipo de documento não suportado para impressão."
                )

            file_path = os.path.join(self.temp_dir, filename)
            with open(file_path, "wb") as f:
                f.write(pdf_content)

            # Log print activity
            print_log = PrintLog(
                consultation_id=consultation_id,
                document_type=document_type,
                printed_by=printed_by,
                status="success",
                error_message=None
            )
            db.add(print_log)
            await db.commit()
            await db.refresh(print_log)

            return PrintResponse(
                status="success",
                message=f"Documento '{document_type}' gerado com sucesso.",
                file_url=f"/api/v1/print/download/{print_log.id}",
                preview_url=f"/api/v1/print/preview/{print_log.id}"
            )

        except Exception as e:
            # Log error
            print_log = PrintLog(
                consultation_id=consultation_id,
                document_type=document_type,
                printed_by=printed_by,
                status="failed",
                error_message=str(e)
            )
            db.add(print_log)
            await db.commit()
            await db.refresh(print_log)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao gerar documento: {str(e)}")

    async def print_consolidated_documents(
        self, 
        db: Session, 
        consultation_id: uuid.UUID, 
        printed_by: uuid.UUID,
        document_types: List[str] = None
    ) -> PrintResponse:
        """Print all documents in a single consolidated PDF."""
        
        if document_types is None:
            document_types = ["prescription", "certificate", "exam_request", "referral"]
        
        # Get consultation data
        consultation = await db.get(Consultation, consultation_id)
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consulta não encontrada"
            )
        
        patient = await db.get(Patient, consultation.patient_id)
        doctor = await db.get(User, consultation.doctor_id)
        clinic = await db.get(Clinic, consultation.clinic_id)

        if not patient or not doctor or not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dados de paciente, médico ou clínica incompletos."
            )

        try:
            # Generate consolidated HTML
            html_content = await self._generate_consolidated_html(patient, doctor, clinic, consultation, document_types)
            
            # Convert to PDF
            html = HTML(string=html_content, base_url=os.getcwd(), font_config=self.font_config)
            pdf_content = html.write_pdf()
            
            filename = f"consolidado_{patient.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            file_path = os.path.join(self.temp_dir, filename)
            
            with open(file_path, "wb") as f:
                f.write(pdf_content)

            # Log print activity
            print_log = PrintLog(
                consultation_id=consultation_id,
                document_type="consolidated",
                printed_by=printed_by,
                status="success",
                error_message=None
            )
            db.add(print_log)
            await db.commit()
            await db.refresh(print_log)

            return PrintResponse(
                status="success",
                message="Documentos consolidados gerados com sucesso.",
                file_url=f"/api/v1/print/download/{print_log.id}",
                preview_url=f"/api/v1/print/preview/{print_log.id}"
            )

        except Exception as e:
            # Log error
            print_log = PrintLog(
                consultation_id=consultation_id,
                document_type="consolidated",
                printed_by=printed_by,
                status="failed",
                error_message=str(e)
            )
            db.add(print_log)
            await db.commit()
            await db.refresh(print_log)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao gerar documentos consolidados: {str(e)}")

    async def _generate_prescription_pdf(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation) -> bytes:
        """Generate prescription PDF."""
        patient_city = patient.city or "Não informado"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Receita Médica</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #2563eb; padding-bottom: 20px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #2563eb; }}
                .patient-info {{ background-color: #f8fafc; padding: 15px; border-radius: 8px; margin-bottom: 30px; }}
                .prescription-content {{ margin-bottom: 25px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 10px; color: #666; }}
                .signature {{ margin-top: 40px; text-align: right; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">{clinic.name}</div>
                <h1>RECEITA MÉDICA</h1>
                <p><strong>Cidade:</strong> {patient_city}</p>
            </div>
            
            <div class="patient-info">
                <h2>Dados do Paciente</h2>
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            
            <div class="prescription-content">
                <h3>Medicação Prescrita</h3>
                <p>Conteúdo da prescrição será preenchido aqui...</p>
            </div>
            
            <div class="signature">
                <p>Dr(a). {doctor.name}</p>
                <p>CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            
            <div class="footer">
                <p>Prontivus — Cuidado Inteligente</p>
            </div>
        </body>
        </html>
        """
        
        html = HTML(string=html_content, base_url=os.getcwd(), font_config=self.font_config)
        return html.write_pdf()

    async def _generate_controlled_prescription_pdf(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation) -> bytes:
        """Generate controlled prescription (blue prescription) PDF."""
        patient_city = patient.city or "Não informado"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Receita de Controle Especial</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #1e40af; padding-bottom: 20px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #1e40af; }}
                .patient-info {{ background-color: #eff6ff; padding: 15px; border-radius: 8px; margin-bottom: 30px; border: 2px solid #1e40af; }}
                .prescription-content {{ margin-bottom: 25px; padding: 15px; border: 2px solid #1e40af; border-radius: 8px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 10px; color: #666; }}
                .signature {{ margin-top: 40px; text-align: right; }}
                .warning {{ background-color: #fef3c7; padding: 10px; border: 1px solid #f59e0b; border-radius: 4px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">{clinic.name}</div>
                <h1>RECEITA DE CONTROLE ESPECIAL</h1>
                <p><strong>Cidade:</strong> {patient_city}</p>
            </div>
            
            <div class="warning">
                <strong>ATENÇÃO:</strong> Esta receita é para medicamentos de controle especial. 
                Deve ser apresentada em farmácia autorizada.
            </div>
            
            <div class="patient-info">
                <h2>Dados do Paciente</h2>
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            
            <div class="prescription-content">
                <h3>Medicação de Controle Especial</h3>
                <p>Conteúdo da prescrição controlada será preenchido aqui...</p>
            </div>
            
            <div class="signature">
                <p>Dr(a). {doctor.name}</p>
                <p>CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            
            <div class="footer">
                <p>Prontivus — Cuidado Inteligente</p>
            </div>
        </body>
        </html>
        """
        
        html = HTML(string=html_content, base_url=os.getcwd(), font_config=self.font_config)
        return html.write_pdf()

    async def _generate_certificate_pdf(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation) -> bytes:
        """Generate medical certificate PDF."""
        patient_city = patient.city or "Não informado"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Atestado Médico</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #059669; padding-bottom: 20px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #059669; }}
                .patient-info {{ background-color: #f0fdf4; padding: 15px; border-radius: 8px; margin-bottom: 30px; }}
                .certificate-content {{ margin-bottom: 25px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 10px; color: #666; }}
                .signature {{ margin-top: 40px; text-align: right; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">{clinic.name}</div>
                <h1>ATESTADO MÉDICO</h1>
                <p><strong>Cidade:</strong> {patient_city}</p>
            </div>
            
            <div class="patient-info">
                <h2>Dados do Paciente</h2>
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            
            <div class="certificate-content">
                <h3>Atestado</h3>
                <p>Atesto para os devidos fins que o(a) paciente <strong>{patient.name}</strong> 
                esteve sob meus cuidados médicos em {datetime.now().strftime('%d/%m/%Y')}.</p>
                <p>Conteúdo do atestado será preenchido aqui...</p>
            </div>
            
            <div class="signature">
                <p>Dr(a). {doctor.name}</p>
                <p>CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            
            <div class="footer">
                <p>Prontivus — Cuidado Inteligente</p>
            </div>
        </body>
        </html>
        """
        
        html = HTML(string=html_content, base_url=os.getcwd(), font_config=self.font_config)
        return html.write_pdf()

    async def _generate_exam_request_pdf(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation) -> bytes:
        """Generate exam request PDF."""
        patient_city = patient.city or "Não informado"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Solicitação de Exame</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #7c3aed; padding-bottom: 20px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #7c3aed; }}
                .patient-info {{ background-color: #faf5ff; padding: 15px; border-radius: 8px; margin-bottom: 30px; }}
                .exam-content {{ margin-bottom: 25px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 10px; color: #666; }}
                .signature {{ margin-top: 40px; text-align: right; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">{clinic.name}</div>
                <h1>SOLICITAÇÃO DE EXAME</h1>
                <p><strong>Cidade:</strong> {patient_city}</p>
            </div>
            
            <div class="patient-info">
                <h2>Dados do Paciente</h2>
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            
            <div class="exam-content">
                <h3>Exames Solicitados</h3>
                <p>Lista de exames será preenchida aqui...</p>
            </div>
            
            <div class="signature">
                <p>Dr(a). {doctor.name}</p>
                <p>CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            
            <div class="footer">
                <p>Prontivus — Cuidado Inteligente</p>
            </div>
        </body>
        </html>
        """
        
        html = HTML(string=html_content, base_url=os.getcwd(), font_config=self.font_config)
        return html.write_pdf()

    async def _generate_referral_pdf(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation) -> bytes:
        """Generate medical referral PDF."""
        patient_city = patient.city or "Não informado"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Encaminhamento Médico</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #dc2626; padding-bottom: 20px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #dc2626; }}
                .patient-info {{ background-color: #fef2f2; padding: 15px; border-radius: 8px; margin-bottom: 30px; }}
                .referral-content {{ margin-bottom: 25px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 10px; color: #666; }}
                .signature {{ margin-top: 40px; text-align: right; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">{clinic.name}</div>
                <h1>ENCAMINHAMENTO MÉDICO</h1>
                <p><strong>Cidade:</strong> {patient_city}</p>
            </div>
            
            <div class="patient-info">
                <h2>Dados do Paciente</h2>
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            
            <div class="referral-content">
                <h3>Encaminhamento</h3>
                <p>O(a) paciente <strong>{patient.name}</strong> é encaminhado(a) para especialista.</p>
                <p>Detalhes do encaminhamento serão preenchidos aqui...</p>
            </div>
            
            <div class="signature">
                <p>Dr(a). {doctor.name}</p>
                <p>CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            
            <div class="footer">
                <p>Prontivus — Cuidado Inteligente</p>
            </div>
        </body>
        </html>
        """
        
        html = HTML(string=html_content, base_url=os.getcwd(), font_config=self.font_config)
        return html.write_pdf()

    async def _generate_sadt_guide_pdf(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation) -> bytes:
        """Generate SADT guide PDF."""
        patient_city = patient.city or "Não informado"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Guia SADT</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #0891b2; padding-bottom: 20px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #0891b2; }}
                .patient-info {{ background-color: #f0f9ff; padding: 15px; border-radius: 8px; margin-bottom: 30px; }}
                .sadt-content {{ margin-bottom: 25px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 10px; color: #666; }}
                .signature {{ margin-top: 40px; text-align: right; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">{clinic.name}</div>
                <h1>GUIA SADT</h1>
                <p><strong>Cidade:</strong> {patient_city}</p>
            </div>
            
            <div class="patient-info">
                <h2>Dados do Paciente</h2>
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            
            <div class="sadt-content">
                <h3>Guia SADT</h3>
                <p>Conteúdo do guia SADT será preenchido aqui...</p>
            </div>
            
            <div class="signature">
                <p>Dr(a). {doctor.name}</p>
                <p>CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            
            <div class="footer">
                <p>Prontivus — Cuidado Inteligente</p>
            </div>
        </body>
        </html>
        """
        
        html = HTML(string=html_content, base_url=os.getcwd(), font_config=self.font_config)
        return html.write_pdf()

    async def _generate_consolidated_html(
        self, 
        patient: Patient, 
        doctor: User, 
        clinic: Clinic, 
        consultation: Consultation,
        document_types: List[str]
    ) -> str:
        """Generate consolidated HTML with all documents."""
        patient_city = patient.city or "Não informado"
        
        html_parts = []
        
        for i, doc_type in enumerate(document_types):
            if doc_type == "prescription":
                html_parts.append(await self._get_prescription_html(patient, doctor, clinic, consultation, patient_city))
            elif doc_type == "certificate":
                html_parts.append(await self._get_certificate_html(patient, doctor, clinic, consultation, patient_city))
            elif doc_type == "exam_request":
                html_parts.append(await self._get_exam_request_html(patient, doctor, clinic, consultation, patient_city))
            elif doc_type == "referral":
                html_parts.append(await self._get_referral_html(patient, doctor, clinic, consultation, patient_city))
            
            # Add page break between documents (except for the last one)
            if i < len(document_types) - 1:
                html_parts.append('<div style="page-break-before: always;"></div>')
        
        consolidated_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Documentos Consolidados - {patient.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .document {{ margin-bottom: 40px; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #2563eb; padding-bottom: 20px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #2563eb; }}
                .patient-info {{ background-color: #f8fafc; padding: 15px; border-radius: 8px; margin-bottom: 30px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 10px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">{clinic.name}</div>
                <h1>DOCUMENTOS CONSOLIDADOS</h1>
                <p><strong>Paciente:</strong> {patient.name} | <strong>Data:</strong> {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            
            {''.join(html_parts)}
            
            <div class="footer">
                <p>Prontivus — Cuidado Inteligente</p>
                <p>Documentos gerados em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
            </div>
        </body>
        </html>
        """
        
        return consolidated_html

    async def _get_prescription_html(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation, patient_city: str) -> str:
        return f"""
        <div class="document">
            <h2>RECEITA MÉDICA</h2>
            <div class="patient-info">
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            <div style="margin: 20px 0; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <p>Medicação prescrita será preenchida aqui...</p>
            </div>
            <div style="margin-top: 40px; text-align: right;">
                <p>Dr(a). {doctor.name} - CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
        </div>
        """

    async def _get_certificate_html(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation, patient_city: str) -> str:
        return f"""
        <div class="document">
            <h2>ATESTADO MÉDICO</h2>
            <div class="patient-info">
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            <div style="margin: 20px 0; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <p>Atesto para os devidos fins que o(a) paciente <strong>{patient.name}</strong> 
                esteve sob meus cuidados médicos em {datetime.now().strftime('%d/%m/%Y')}.</p>
            </div>
            <div style="margin-top: 40px; text-align: right;">
                <p>Dr(a). {doctor.name} - CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
        </div>
        """

    async def _get_exam_request_html(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation, patient_city: str) -> str:
        return f"""
        <div class="document">
            <h2>SOLICITAÇÃO DE EXAME</h2>
            <div class="patient-info">
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            <div style="margin: 20px 0; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <p>Exames solicitados serão preenchidos aqui...</p>
            </div>
            <div style="margin-top: 40px; text-align: right;">
                <p>Dr(a). {doctor.name} - CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
        </div>
        """

    async def _get_referral_html(self, patient: Patient, doctor: User, clinic: Clinic, consultation: Consultation, patient_city: str) -> str:
        return f"""
        <div class="document">
            <h2>ENCAMINHAMENTO MÉDICO</h2>
            <div class="patient-info">
                <p><strong>Nome:</strong> {patient.name}</p>
                <p><strong>Data de Nascimento:</strong> {patient.birthdate or 'Não informado'}</p>
                <p><strong>CPF:</strong> {patient.cpf or 'Não informado'}</p>
            </div>
            <div style="margin: 20px 0; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <p>O(a) paciente <strong>{patient.name}</strong> é encaminhado(a) para especialista.</p>
            </div>
            <div style="margin-top: 40px; text-align: right;">
                <p>Dr(a). {doctor.name} - CRM: {doctor.crm or 'Não informado'}</p>
                <p>Data: {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
        </div>
        """


# Create service instance
enhanced_print_service = EnhancedPrintService()
