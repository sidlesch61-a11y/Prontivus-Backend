"""
PDF generation service for digital prescriptions.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from io import BytesIO
import logging

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class PDFGenerator:
    """Service for generating PDF documents from prescriptions."""
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'prontivus-prescriptions')
        self.font_config = FontConfiguration()
    
    async def generate_prescription_pdf(
        self, 
        prescription, 
        clinic, 
        doctor
    ) -> bytes:
        """Generate PDF content for a prescription."""
        
        try:
            # Generate HTML content
            html_content = self._generate_prescription_html(
                prescription=prescription,
                clinic=clinic,
                doctor=doctor
            )
            
            # Generate CSS styles
            css_content = self._generate_prescription_css()
            
            # Convert HTML to PDF
            html_doc = HTML(string=html_content)
            css_doc = CSS(string=css_content, font_config=self.font_config)
            
            pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])
            
            logger.info(f"PDF generated for prescription {prescription.id}")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating PDF for prescription {prescription.id}: {str(e)}")
            raise
    
    def _generate_prescription_html(
        self, 
        prescription, 
        clinic, 
        doctor
    ) -> str:
        """Generate HTML content for prescription."""
        
        # Format prescription items
        items_html = ""
        for i, item in enumerate(prescription.items, 1):
            items_html += f"""
            <div class="prescription-item">
                <div class="item-number">{i}.</div>
                <div class="item-content">
                    <div class="medication">{item['medication']}</div>
                    <div class="details">
                        <span class="dosage">{item['dosage']}</span>
                        <span class="frequency">{item['frequency']}</span>
                        <span class="duration">{item['duration']}</span>
                    </div>
                    {f'<div class="notes">{item["notes"]}</div>' if item.get('notes') else ''}
                </div>
            </div>
            """
        
        # Get doctor CRM from metadata
        doctor_crm = doctor.metadata.get('crm', 'N/A') if doctor.metadata else 'N/A'
        
        # Get clinic CNPJ
        clinic_cnpj = clinic.cnpj_cpf or 'N/A'
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Prescrição Digital</title>
        </head>
        <body>
            <div class="prescription-container">
                <!-- Header -->
                <div class="header">
                    <div class="clinic-info">
                        <h1>{clinic.name}</h1>
                        <p>CNPJ: {clinic_cnpj}</p>
                        <p>{clinic.contact_email}</p>
                        <p>{clinic.contact_phone}</p>
                    </div>
                    <div class="prescription-info">
                        <h2>PRESCRIÇÃO MÉDICA</h2>
                        <p class="prescription-id">ID: {prescription.id}</p>
                        <p class="prescription-type">Tipo: {prescription.prescription_type.value.upper()}</p>
                        <p class="prescription-date">Data: {prescription.created_at.strftime('%d/%m/%Y')}</p>
                    </div>
                </div>
                
                <!-- Patient Info -->
                <div class="patient-info">
                    <h3>DADOS DO PACIENTE</h3>
                    <div class="patient-details">
                        <p><strong>Nome:</strong> {prescription.patient.name}</p>
                        <p><strong>Data de Nascimento:</strong> {prescription.patient.birthdate.strftime('%d/%m/%Y') if prescription.patient.birthdate else 'N/A'}</p>
                        <p><strong>Gênero:</strong> {prescription.patient.gender.title() if prescription.patient.gender else 'N/A'}</p>
                        <p><strong>CPF:</strong> {prescription.patient.cpf or 'N/A'}</p>
                    </div>
                </div>
                
                <!-- Doctor Info -->
                <div class="doctor-info">
                    <h3>DADOS DO MÉDICO</h3>
                    <div class="doctor-details">
                        <p><strong>Nome:</strong> {doctor.name}</p>
                        <p><strong>CRM:</strong> {doctor_crm}</p>
                        <p><strong>Especialidade:</strong> {doctor.metadata.get('specialty', 'N/A') if doctor.metadata else 'N/A'}</p>
                    </div>
                </div>
                
                <!-- Prescription Items -->
                <div class="prescription-items">
                    <h3>MEDICAMENTOS PRESCRITOS</h3>
                    {items_html}
                </div>
                
                <!-- Notes -->
                {f'''
                <div class="prescription-notes">
                    <h3>OBSERVAÇÕES</h3>
                    <p>{prescription.notes}</p>
                </div>
                ''' if prescription.notes else ''}
                
                <!-- Signature Area -->
                <div class="signature-area">
                    <div class="signature-line">
                        <p>_________________________________</p>
                        <p>Assinatura Digital do Médico</p>
                    </div>
                    <div class="signature-info">
                        <p><strong>Dr(a). {doctor.name}</strong></p>
                        <p>CRM: {doctor_crm}</p>
                        <p>Data: {prescription.created_at.strftime('%d/%m/%Y %H:%M')}</p>
                    </div>
                </div>
                
                <!-- Footer -->
                <div class="footer">
                    <p>Este documento possui assinatura digital ICP-Brasil e pode ser verificado através do QR Code.</p>
                    <p>Prescrição gerada em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _generate_prescription_css(self) -> str:
        """Generate CSS styles for prescription PDF."""
        
        css_content = """
        @page {
            size: A4;
            margin: 2cm;
        }
        
        body {
            font-family: 'Times New Roman', serif;
            font-size: 12px;
            line-height: 1.4;
            color: #000;
            margin: 0;
            padding: 0;
        }
        
        .prescription-container {
            max-width: 100%;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 30px;
            border-bottom: 2px solid #000;
            padding-bottom: 15px;
        }
        
        .clinic-info h1 {
            font-size: 18px;
            font-weight: bold;
            margin: 0 0 5px 0;
        }
        
        .clinic-info p {
            margin: 2px 0;
            font-size: 10px;
        }
        
        .prescription-info {
            text-align: right;
        }
        
        .prescription-info h2 {
            font-size: 16px;
            font-weight: bold;
            margin: 0 0 10px 0;
            text-decoration: underline;
        }
        
        .prescription-info p {
            margin: 2px 0;
            font-size: 10px;
        }
        
        .patient-info, .doctor-info, .prescription-items, .prescription-notes {
            margin: 20px 0;
        }
        
        .patient-info h3, .doctor-info h3, .prescription-items h3, .prescription-notes h3 {
            font-size: 14px;
            font-weight: bold;
            margin: 0 0 10px 0;
            background-color: #f0f0f0;
            padding: 5px;
            border-left: 4px solid #000;
        }
        
        .patient-details, .doctor-details {
            margin-left: 10px;
        }
        
        .patient-details p, .doctor-details p {
            margin: 5px 0;
        }
        
        .prescription-item {
            display: flex;
            margin: 15px 0;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        
        .item-number {
            font-weight: bold;
            margin-right: 10px;
            min-width: 20px;
        }
        
        .item-content {
            flex: 1;
        }
        
        .medication {
            font-weight: bold;
            font-size: 13px;
            margin-bottom: 5px;
        }
        
        .details {
            margin-bottom: 5px;
        }
        
        .details span {
            margin-right: 15px;
            font-size: 11px;
        }
        
        .notes {
            font-style: italic;
            font-size: 10px;
            color: #666;
        }
        
        .signature-area {
            margin: 40px 0;
            text-align: center;
        }
        
        .signature-line {
            margin-bottom: 20px;
        }
        
        .signature-line p {
            margin: 5px 0;
        }
        
        .signature-info {
            margin-top: 20px;
        }
        
        .signature-info p {
            margin: 3px 0;
        }
        
        .footer {
            margin-top: 40px;
            font-size: 9px;
            text-align: center;
            color: #666;
            border-top: 1px solid #ddd;
            padding-top: 10px;
        }
        
        .footer p {
            margin: 2px 0;
        }
        
        /* Special styling for C1 prescriptions */
        .prescription-type.C1 {
            color: #d32f2f;
            font-weight: bold;
        }
        
        /* Special styling for antimicrobial prescriptions */
        .prescription-type.antimicrobial {
            color: #1976d2;
            font-weight: bold;
        }
        """
        
        return css_content
    
    async def upload_signed_pdf(
        self, 
        pdf_content: bytes, 
        prescription_id: uuid.UUID, 
        qr_token: str
    ) -> str:
        """Upload signed PDF to S3 storage."""
        
        try:
            # Generate S3 key
            s3_key = f"prescriptions/signed/{prescription_id}/{qr_token}.pdf"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=pdf_content,
                ContentType='application/pdf',
                Metadata={
                    'prescription_id': str(prescription_id),
                    'qr_token': qr_token,
                    'uploaded_at': datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"Signed PDF uploaded to S3: {s3_key}")
            return s3_key
            
        except ClientError as e:
            logger.error(f"Error uploading PDF to S3: {str(e)}")
            raise
    
    async def download_pdf_from_s3(self, s3_key: str) -> bytes:
        """Download PDF from S3 storage."""
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return response['Body'].read()
            
        except ClientError as e:
            logger.error(f"Error downloading PDF from S3: {str(e)}")
            raise
    
    def generate_prescription_template(
        self, 
        prescription_type: str
    ) -> str:
        """Generate HTML template for different prescription types."""
        
        templates = {
            'simple': self._generate_simple_template(),
            'antimicrobial': self._generate_antimicrobial_template(),
            'C1': self._generate_c1_template()
        }
        
        return templates.get(prescription_type, templates['simple'])
    
    def _generate_simple_template(self) -> str:
        """Generate template for simple prescriptions."""
        return """
        <div class="prescription-template simple">
            <h3>PRESCRIÇÃO SIMPLES</h3>
            <p>Medicamentos de uso comum sem restrições especiais.</p>
        </div>
        """
    
    def _generate_antimicrobial_template(self) -> str:
        """Generate template for antimicrobial prescriptions."""
        return """
        <div class="prescription-template antimicrobial">
            <h3>PRESCRIÇÃO DE ANTIMICROBIANOS</h3>
            <p><strong>ATENÇÃO:</strong> Esta prescrição contém antimicrobianos e deve seguir as diretrizes da RDC 471.</p>
            <ul>
                <li>Dosagem e frequência obrigatórias</li>
                <li>Duração do tratamento especificada</li>
                <li>Justificativa clínica necessária</li>
            </ul>
        </div>
        """
    
    def _generate_c1_template(self) -> str:
        """Generate template for C1 controlled substances."""
        return """
        <div class="prescription-template c1">
            <h3>PRESCRIÇÃO DE SUBSTÂNCIAS CONTROLADAS (C1)</h3>
            <p><strong>ATENÇÃO:</strong> Esta prescrição contém substâncias controladas e requer duas vias.</p>
            <ul>
                <li>Dosagem e frequência obrigatórias</li>
                <li>Duração do tratamento especificada</li>
                <li>Justificativa clínica detalhada</li>
                <li>Controle rigoroso de estoque</li>
            </ul>
        </div>
        """
