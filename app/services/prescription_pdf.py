"""
Digital Prescription PDF Generator
Generates standardized prescription PDFs with clinic branding, QR codes, and digital signatures.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from datetime import datetime
import io
import qrcode
from typing import Dict, List, Any

class PrescriptionPDFGenerator:
    """Generates professional prescription PDFs."""
    
    def __init__(self):
        self.page_width, self.page_height = A4
        self.margin = 20 * mm
        
    def generate_prescription_pdf(
        self,
        prescription_data: Dict[str, Any],
        clinic_data: Dict[str, Any],
        doctor_data: Dict[str, Any],
        patient_data: Dict[str, Any],
        qr_code_data: str = None
    ) -> bytes:
        """
        Generate a complete prescription PDF.
        
        Args:
            prescription_data: Prescription details (type, medications, notes)
            clinic_data: Clinic information (name, logo, contact)
            doctor_data: Doctor information (name, CRM, specialty)
            patient_data: Patient information (name, DOB, CPF)
            qr_code_data: Data to encode in QR code (verification URL)
            
        Returns:
            PDF bytes
        """
        buffer = io.BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin + 15*mm,  # Extra space for footer
        )
        
        # Build content
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2563eb'),
            spaceAfter=6,
            alignment=TA_CENTER,
        )
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#6b7280'),
            alignment=TA_CENTER,
            spaceAfter=12,
        )
        
        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=8,
            spaceBefore=12,
        )
        
        # Header with clinic branding
        story.extend(self._build_header(clinic_data, styles))
        
        # Prescription type badge
        story.extend(self._build_prescription_type_badge(prescription_data, styles))
        
        # Patient information
        story.extend(self._build_patient_section(patient_data, heading_style, styles))
        
        # Medications table
        story.extend(self._build_medications_section(prescription_data, heading_style))
        
        # Additional notes
        if prescription_data.get('notes'):
            story.extend(self._build_notes_section(prescription_data, heading_style, styles))
        
        # Doctor signature section
        story.extend(self._build_signature_section(doctor_data, prescription_data, heading_style, styles))
        
        # QR Code for verification
        if qr_code_data:
            story.extend(self._build_qr_code_section(qr_code_data, styles))
        
        # Build PDF with custom footer
        doc.build(story, onFirstPage=self._add_footer, onLaterPages=self._add_footer)
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    def _build_header(self, clinic_data: Dict, styles) -> List:
        """Build clinic header section."""
        elements = []
        
        # Clinic logo (if available)
        if clinic_data.get('logo_url'):
            try:
                # In production, download logo from URL
                # For now, placeholder
                pass
            except:
                pass
        
        # Clinic name
        clinic_name = Paragraph(
            f"<b>{clinic_data.get('name', 'Clinic Name')}</b>",
            ParagraphStyle(
                'ClinicName',
                parent=styles['Heading1'],
                fontSize=16,
                textColor=colors.HexColor('#1f2937'),
                alignment=TA_CENTER,
                spaceAfter=4,
            )
        )
        elements.append(clinic_name)
        
        # Clinic contact info
        contact_info = []
        if clinic_data.get('contact_phone'):
            contact_info.append(f"Tel: {clinic_data['contact_phone']}")
        if clinic_data.get('contact_email'):
            contact_info.append(f"Email: {clinic_data['contact_email']}")
        
        if contact_info:
            contact_text = Paragraph(
                " | ".join(contact_info),
                ParagraphStyle(
                    'Contact',
                    parent=styles['Normal'],
                    fontSize=9,
                    textColor=colors.HexColor('#6b7280'),
                    alignment=TA_CENTER,
                    spaceAfter=20,
                )
            )
            elements.append(contact_text)
        else:
            elements.append(Spacer(1, 10*mm))
        
        # Horizontal line
        elements.append(self._create_line())
        elements.append(Spacer(1, 5*mm))
        
        return elements
    
    def _build_prescription_type_badge(self, prescription_data: Dict, styles) -> List:
        """Build prescription type indicator."""
        elements = []
        
        prescription_type = prescription_data.get('prescription_type', 'simple')
        type_labels = {
            'simple': 'RECEITA SIMPLES',
            'antimicrobial': 'RECEITA ANTIMICROBIANO (RDC 471/2021)',
            'controlled_c1': 'RECEITA CONTROLADA - CLASSE C1 (Portaria 344/98)',
        }
        
        type_colors = {
            'simple': '#2563eb',
            'antimicrobial': '#ea580c',
            'controlled_c1': '#dc2626',
        }
        
        label = type_labels.get(prescription_type, 'RECEITA')
        color = type_colors.get(prescription_type, '#2563eb')
        
        badge = Paragraph(
            f"<b>{label}</b>",
            ParagraphStyle(
                'TypeBadge',
                parent=styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor(color),
                alignment=TA_CENTER,
                spaceAfter=15,
            )
        )
        elements.append(badge)
        
        return elements
    
    def _build_patient_section(self, patient_data: Dict, heading_style, styles) -> List:
        """Build patient information section."""
        elements = []
        
        elements.append(Paragraph("<b>DADOS DO PACIENTE</b>", heading_style))
        
        patient_info = [
            ['<b>Nome:</b>', patient_data.get('name', 'N/A')],
            ['<b>Data de Nascimento:</b>', patient_data.get('birthdate', 'N/A')],
        ]
        
        if patient_data.get('cpf'):
            patient_info.append(['<b>CPF:</b>', patient_data['cpf']])
        
        patient_table = Table(patient_info, colWidths=[40*mm, 130*mm])
        patient_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        elements.append(patient_table)
        elements.append(Spacer(1, 8*mm))
        
        return elements
    
    def _build_medications_section(self, prescription_data: Dict, heading_style) -> List:
        """Build medications table."""
        elements = []
        
        elements.append(Paragraph("<b>MEDICAMENTOS PRESCRITOS</b>", heading_style))
        
        medications = prescription_data.get('medications', [])
        
        # Build medications table
        table_data = []
        
        for i, med in enumerate(medications, 1):
            med_name = f"{i}. {med.get('name', 'N/A')} - {med.get('dosage', '')}"
            
            instructions = []
            if med.get('frequency'):
                instructions.append(f"Frequência: {med['frequency']}")
            if med.get('duration'):
                instructions.append(f"Duração: {med['duration']}")
            if med.get('quantity'):
                instructions.append(f"Quantidade: {med['quantity']}")
            if med.get('instructions'):
                instructions.append(med['instructions'])
            
            instructions_text = '<br/>'.join(instructions) if instructions else '-'
            
            table_data.append([
                Paragraph(f"<b>{med_name}</b>", ParagraphStyle('MedName', fontSize=10)),
                Paragraph(instructions_text, ParagraphStyle('MedInstr', fontSize=9)),
            ])
        
        med_table = Table(table_data, colWidths=[70*mm, 100*mm])
        med_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f9fafb')),
        ]))
        
        elements.append(med_table)
        elements.append(Spacer(1, 8*mm))
        
        return elements
    
    def _build_notes_section(self, prescription_data: Dict, heading_style, styles) -> List:
        """Build additional notes section."""
        elements = []
        
        elements.append(Paragraph("<b>OBSERVAÇÕES</b>", heading_style))
        notes = Paragraph(
            prescription_data.get('notes', ''),
            ParagraphStyle(
                'Notes',
                parent=styles['Normal'],
                fontSize=9,
                leading=12,
            )
        )
        elements.append(notes)
        elements.append(Spacer(1, 8*mm))
        
        return elements
    
    def _build_signature_section(self, doctor_data: Dict, prescription_data: Dict, heading_style, styles) -> List:
        """Build doctor signature section."""
        elements = []
        
        elements.append(Spacer(1, 10*mm))
        elements.append(self._create_line())
        elements.append(Spacer(1, 2*mm))
        
        # Doctor name and CRM
        doctor_name = Paragraph(
            f"<b>Dr(a). {doctor_data.get('name', 'N/A')}</b>",
            ParagraphStyle(
                'DoctorName',
                parent=styles['Normal'],
                fontSize=11,
                alignment=TA_CENTER,
            )
        )
        elements.append(doctor_name)
        
        crm = Paragraph(
            f"CRM: {doctor_data.get('crm', 'N/A')} | {doctor_data.get('specialty', '')}",
            ParagraphStyle(
                'DoctorCRM',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#6b7280'),
                alignment=TA_CENTER,
                spaceAfter=10,
            )
        )
        elements.append(crm)
        
        # Date and digital signature status
        created_at = prescription_data.get('created_at', datetime.now())
        if isinstance(created_at, str):
            date_str = created_at
        else:
            date_str = created_at.strftime('%d/%m/%Y %H:%M')
        
        date_para = Paragraph(
            f"Data de emissão: {date_str}",
            ParagraphStyle(
                'Date',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#6b7280'),
                alignment=TA_CENTER,
            )
        )
        elements.append(date_para)
        
        if prescription_data.get('signed_at'):
            signature_para = Paragraph(
                "<b>✓ Assinado Digitalmente (ICP-Brasil A1)</b>",
                ParagraphStyle(
                    'Signature',
                    parent=styles['Normal'],
                    fontSize=9,
                    textColor=colors.HexColor('#16a34a'),
                    alignment=TA_CENTER,
                    spaceAfter=10,
                )
            )
            elements.append(signature_para)
        
        return elements
    
    def _build_qr_code_section(self, qr_data: str, styles) -> List:
        """Build QR code for verification."""
        elements = []
        
        elements.append(Spacer(1, 5*mm))
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=3, border=1)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to ReportLab Image
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        qr_image = Image(qr_buffer, width=30*mm, height=30*mm)
        
        # Center the QR code
        qr_table = Table([[qr_image]], colWidths=[30*mm])
        qr_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(qr_table)
        
        qr_text = Paragraph(
            "Escaneie para verificar autenticidade",
            ParagraphStyle(
                'QRText',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#6b7280'),
                alignment=TA_CENTER,
            )
        )
        elements.append(qr_text)
        
        return elements
    
    def _create_line(self):
        """Create a horizontal line."""
        from reportlab.platypus import Flowable
        
        class HorizontalLine(Flowable):
            def __init__(self, width):
                Flowable.__init__(self)
                self.width = width
                
            def draw(self):
                self.canv.setStrokeColor(colors.HexColor('#e5e7eb'))
                self.canv.setLineWidth(0.5)
                self.canv.line(0, 0, self.width, 0)
        
        return HorizontalLine(170*mm)
    
    def _add_footer(self, canvas, doc):
        """Add footer to each page."""
        canvas.saveState()
        
        # Footer line
        canvas.setStrokeColor(colors.HexColor('#e5e7eb'))
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, 15*mm, doc.width + doc.leftMargin, 15*mm)
        
        # Prontivus branding
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#6b7280'))
        footer_text = "Prontivus — Cuidado inteligente"
        text_width = canvas.stringWidth(footer_text, 'Helvetica', 8)
        canvas.drawString((doc.width + doc.leftMargin + doc.rightMargin - text_width) / 2, 10*mm, footer_text)
        
        # Page number
        page_num = f"Página {doc.page}"
        canvas.drawRightString(doc.width + doc.leftMargin, 10*mm, page_num)
        
        canvas.restoreState()


# Utility function
def generate_prescription_pdf(prescription, clinic, doctor, patient) -> bytes:
    """
    Convenience function to generate prescription PDF.
    
    Args:
        prescription: Prescription model instance
        clinic: Clinic model instance
        doctor: User model instance (doctor)
        patient: Patient model instance
        
    Returns:
        PDF bytes
    """
    generator = PrescriptionPDFGenerator()
    
    prescription_data = {
        'id': str(prescription.id),
        'prescription_type': prescription.prescription_type,
        'medications': prescription.medications if hasattr(prescription, 'medications') else [],
        'notes': prescription.notes,
        'created_at': prescription.created_at,
        'signed_at': getattr(prescription, 'signed_at', None),
    }
    
    clinic_data = {
        'name': clinic.name,
        'logo_url': clinic.logo_url,
        'contact_phone': clinic.contact_phone,
        'contact_email': clinic.contact_email,
    }
    
    doctor_data = {
        'name': doctor.name,
        'crm': getattr(doctor, 'crm', 'N/A'),
        'specialty': getattr(doctor, 'specialty', ''),
    }
    
    patient_data = {
        'name': patient.name,
        'birthdate': patient.birthdate.strftime('%d/%m/%Y') if patient.birthdate else 'N/A',
        'cpf': patient.cpf,
    }
    
    qr_code_data = f"https://prontivus.com/verify/prescription/{prescription.id}"
    
    return generator.generate_prescription_pdf(
        prescription_data,
        clinic_data,
        doctor_data,
        patient_data,
        qr_code_data
    )

