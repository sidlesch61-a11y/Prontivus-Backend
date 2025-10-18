"""
PDF generation service for medical documents.
Generates professional PDFs with clinic headers, footers, and signatures.
"""

import io
from datetime import datetime
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.models import Consultation, Patient, User, Clinic


class PDFGenerator:
    """PDF generator for medical documents."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for medical documents."""
        # Header style
        self.styles.add(ParagraphStyle(
            name='ClinicHeader',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1e40af')  # Blue color
        ))
        
        # Subheader style
        self.styles.add(ParagraphStyle(
            name='ClinicSubheader',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=6,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#6b7280')  # Gray color
        ))
        
        # Document title style
        self.styles.add(ParagraphStyle(
            name='DocumentTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1f2937')  # Dark gray
        ))
        
        # Patient info style
        self.styles.add(ParagraphStyle(
            name='PatientInfo',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_LEFT
        ))
        
        # Content style
        self.styles.add(ParagraphStyle(
            name='Content',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            alignment=TA_JUSTIFY
        ))
        
        # Signature style
        self.styles.add(ParagraphStyle(
            name='Signature',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_RIGHT
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            spaceAfter=0,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#9ca3af')  # Light gray
        ))
    
    async def generate_document(
        self,
        document_type: str,
        consultation: Consultation,
        patient: Patient,
        doctor: User,
        clinic: Clinic
    ) -> bytes:
        """Generate a specific document type."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        
        # Build document content
        story = []
        
        # Add clinic header
        story.extend(self._create_clinic_header(clinic))
        story.append(Spacer(1, 20))
        
        # Add document title
        story.append(Paragraph(self._get_document_title(document_type), self.styles['DocumentTitle']))
        story.append(Spacer(1, 20))
        
        # Add patient information
        story.extend(self._create_patient_info(patient, consultation))
        story.append(Spacer(1, 20))
        
        # Add document content based on type
        story.extend(self._create_document_content(document_type, consultation, patient, doctor))
        story.append(Spacer(1, 30))
        
        # Add doctor signature
        story.extend(self._create_doctor_signature(doctor, clinic))
        story.append(Spacer(1, 20))
        
        # Add footer
        story.append(Paragraph("Prontivus — Cuidado Inteligente", self.styles['Footer']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    async def generate_consolidated_documents(
        self,
        consultation: Consultation,
        patient: Patient,
        doctor: User,
        clinic: Clinic
    ) -> bytes:
        """Generate consolidated PDF with all documents."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        
        story = []
        
        # Add clinic header
        story.extend(self._create_clinic_header(clinic))
        story.append(Spacer(1, 20))
        
        # Add consolidated title
        story.append(Paragraph("DOCUMENTOS CONSOLIDADOS DA CONSULTA", self.styles['DocumentTitle']))
        story.append(Spacer(1, 20))
        
        # Add patient information
        story.extend(self._create_patient_info(patient, consultation))
        story.append(Spacer(1, 20))
        
        # Add all document types
        document_types = [
            "receita_simples", "receita_azul", "atestado", 
            "guia_sadt", "justificativa_exames", "encaminhamento"
        ]
        
        for doc_type in document_types:
            story.append(Paragraph(f"<b>{self._get_document_title(doc_type).upper()}</b>", self.styles['Heading3']))
            story.append(Spacer(1, 10))
            story.extend(self._create_document_content(doc_type, consultation, patient, doctor))
            story.append(Spacer(1, 30))
        
        # Add doctor signature
        story.extend(self._create_doctor_signature(doctor, clinic))
        story.append(Spacer(1, 20))
        
        # Add footer
        story.append(Paragraph("Prontivus — Cuidado Inteligente", self.styles['Footer']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_clinic_header(self, clinic: Clinic) -> list:
        """Create clinic header section."""
        elements = []
        
        # Clinic name
        elements.append(Paragraph(f"<b>{clinic.name}</b>", self.styles['ClinicHeader']))
        
        # Clinic address
        if clinic.address:
            address_parts = []
            if clinic.address.get('street'):
                address_parts.append(clinic.address['street'])
            if clinic.address.get('number'):
                address_parts.append(clinic.address['number'])
            if clinic.address.get('neighborhood'):
                address_parts.append(clinic.address['neighborhood'])
            if clinic.address.get('city'):
                address_parts.append(clinic.address['city'])
            if clinic.address.get('state'):
                address_parts.append(clinic.address['state'])
            if clinic.address.get('zip_code'):
                address_parts.append(clinic.address['zip_code'])
            
            if address_parts:
                elements.append(Paragraph(", ".join(address_parts), self.styles['ClinicSubheader']))
        
        # Phone and email
        contact_info = []
        if clinic.phone:
            contact_info.append(f"Tel: {clinic.phone}")
        if clinic.email:
            contact_info.append(f"Email: {clinic.email}")
        
        if contact_info:
            elements.append(Paragraph(" | ".join(contact_info), self.styles['ClinicSubheader']))
        
        return elements
    
    def _create_patient_info(self, patient: Patient, consultation: Consultation) -> list:
        """Create patient information section."""
        elements = []
        
        # Patient data table
        patient_data = [
            ["<b>Paciente:</b>", f"{patient.name}"],
            ["<b>Data de Nascimento:</b>", patient.birthdate.strftime("%d/%m/%Y") if patient.birthdate else "N/A"],
            ["<b>CPF:</b>", patient.cpf or "N/A"],
            ["<b>Data da Consulta:</b>", consultation.created_at.strftime("%d/%m/%Y às %H:%M")],
            ["<b>Convênio:</b>", patient.insurance_provider or "Particular"],
        ]
        
        table = Table(patient_data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(table)
        return elements
    
    def _create_document_content(
        self, 
        document_type: str, 
        consultation: Consultation, 
        patient: Patient, 
        doctor: User
    ) -> list:
        """Create content based on document type."""
        elements = []
        
        if document_type == "receita_simples":
            elements.extend(self._create_prescription_content(consultation, "simples"))
        elif document_type == "receita_azul":
            elements.extend(self._create_prescription_content(consultation, "controlada"))
        elif document_type == "atestado":
            elements.extend(self._create_certificate_content(consultation))
        elif document_type == "guia_sadt":
            elements.extend(self._create_sadt_guide_content(consultation))
        elif document_type == "justificativa_exames":
            elements.extend(self._create_exam_justification_content(consultation))
        elif document_type == "encaminhamento":
            elements.extend(self._create_referral_content(consultation))
        
        return elements
    
    def _create_prescription_content(self, consultation: Consultation, prescription_type: str) -> list:
        """Create prescription content."""
        elements = []
        
        prescription_title = "RECEITA SIMPLES" if prescription_type == "simples" else "RECEITA AZUL (CONTROLADA)"
        elements.append(Paragraph(f"<b>{prescription_title}</b>", self.styles['Heading3']))
        elements.append(Spacer(1, 10))
        
        # Prescription content
        if consultation.treatment_plan:
            elements.append(Paragraph(consultation.treatment_plan, self.styles['Content']))
        else:
            elements.append(Paragraph("Prescrição médica conforme consulta realizada.", self.styles['Content']))
        
        elements.append(Spacer(1, 20))
        
        # Prescription table (placeholder for medications)
        med_data = [
            ["Medicamento", "Dosagem", "Posologia", "Observações"],
            ["Exemplo: Dipirona", "500mg", "1 comprimido de 6/6h", "Por 5 dias"],
        ]
        
        table = Table(med_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        return elements
    
    def _create_certificate_content(self, consultation: Consultation) -> list:
        """Create medical certificate content."""
        elements = []
        
        elements.append(Paragraph("<b>ATESTADO MÉDICO</b>", self.styles['Heading3']))
        elements.append(Spacer(1, 10))
        
        elements.append(Paragraph(
            "Atesto para os devidos fins que o(a) paciente esteve sob meus cuidados médicos "
            "e que, por motivo de saúde, necessita de afastamento de suas atividades.",
            self.styles['Content']
        ))
        
        elements.append(Spacer(1, 10))
        
        if consultation.diagnosis:
            elements.append(Paragraph(f"<b>Diagnóstico:</b> {consultation.diagnosis}", self.styles['Content']))
        
        elements.append(Spacer(1, 10))
        
        elements.append(Paragraph(
            "Este atestado é válido por 30 dias a partir da data de emissão.",
            self.styles['Content']
        ))
        
        return elements
    
    def _create_sadt_guide_content(self, consultation: Consultation) -> list:
        """Create SADT guide content."""
        elements = []
        
        elements.append(Paragraph("<b>GUIA SADT</b>", self.styles['Heading3']))
        elements.append(Spacer(1, 10))
        
        elements.append(Paragraph(
            "Guia de Solicitação de Autorização de Procedimentos (SADT) conforme "
            "padrão TISS (Troca de Informação em Saúde Suplementar).",
            self.styles['Content']
        ))
        
        elements.append(Spacer(1, 10))
        
        if consultation.diagnosis:
            elements.append(Paragraph(f"<b>Diagnóstico:</b> {consultation.diagnosis}", self.styles['Content']))
        
        if consultation.treatment_plan:
            elements.append(Paragraph(f"<b>Procedimento Solicitado:</b> {consultation.treatment_plan}", self.styles['Content']))
        
        return elements
    
    def _create_exam_justification_content(self, consultation: Consultation) -> list:
        """Create exam justification content."""
        elements = []
        
        elements.append(Paragraph("<b>JUSTIFICATIVA DE EXAMES</b>", self.styles['Heading3']))
        elements.append(Spacer(1, 10))
        
        elements.append(Paragraph(
            "Justificativa médica para realização dos exames solicitados, "
            "baseada no quadro clínico apresentado pelo paciente.",
            self.styles['Content']
        ))
        
        elements.append(Spacer(1, 10))
        
        if consultation.diagnosis:
            elements.append(Paragraph(f"<b>Hipótese Diagnóstica:</b> {consultation.diagnosis}", self.styles['Content']))
        
        if consultation.treatment_plan:
            elements.append(Paragraph(f"<b>Exames Solicitados:</b> {consultation.treatment_plan}", self.styles['Content']))
        
        return elements
    
    def _create_referral_content(self, consultation: Consultation) -> list:
        """Create medical referral content."""
        elements = []
        
        elements.append(Paragraph("<b>ENCAMINHAMENTO MÉDICO</b>", self.styles['Heading3']))
        elements.append(Spacer(1, 10))
        
        elements.append(Paragraph(
            "Encaminho o(a) paciente para avaliação especializada, "
            "conforme necessidade identificada durante a consulta.",
            self.styles['Content']
        ))
        
        elements.append(Spacer(1, 10))
        
        if consultation.diagnosis:
            elements.append(Paragraph(f"<b>Motivo do Encaminhamento:</b> {consultation.diagnosis}", self.styles['Content']))
        
        if consultation.treatment_plan:
            elements.append(Paragraph(f"<b>Especialidade Solicitada:</b> {consultation.treatment_plan}", self.styles['Content']))
        
        return elements
    
    def _create_doctor_signature(self, doctor: User, clinic: Clinic) -> list:
        """Create doctor signature section."""
        elements = []
        
        # Signature line
        elements.append(Paragraph("_" * 50, self.styles['Signature']))
        
        # Doctor name and CRM
        doctor_info = f"Dr(a). {doctor.name}"
        if hasattr(doctor, 'crm') and doctor.crm:
            doctor_info += f" - CRM {doctor.crm}"
        
        elements.append(Paragraph(doctor_info, self.styles['Signature']))
        
        # Date
        elements.append(Paragraph(
            f"Data: {datetime.now().strftime('%d/%m/%Y')}",
            self.styles['Signature']
        ))
        
        return elements
    
    def _get_document_title(self, document_type: str) -> str:
        """Get document title based on type."""
        titles = {
            "receita_simples": "Receita Simples",
            "receita_azul": "Receita Azul (Controlada)",
            "atestado": "Atestado Médico",
            "guia_sadt": "Guia SADT",
            "justificativa_exames": "Justificativa de Exames",
            "encaminhamento": "Encaminhamento Médico"
        }
        return titles.get(document_type, "Documento Médico")