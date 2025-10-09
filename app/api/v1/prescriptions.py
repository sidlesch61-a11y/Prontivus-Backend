"""
API endpoints for digital prescriptions with PAdES signatures.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, FileResponse
from sqlmodel import Session, select
from typing import List, Optional
import uuid
import hashlib
import base64
import json
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import logging

from ..models.prescription import (
    Prescription, PrescriptionCreateRequest, PrescriptionSignRequest,
    PrescriptionResponse, PrescriptionSignResponse, PrescriptionVerificationResponse,
    PrescriptionType, PrescriptionStatus, PrescriptionValidationRules,
    SignatureMetadata, QRCodeData
)
from ..core.auth import get_current_user, get_current_tenant
from ..db.session import get_db
from ..services.pdf_generator import PDFGenerator
from ..services.digital_signature import DigitalSignatureService
from ..services.qr_generator import QRCodeGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prescriptions", tags=["prescriptions"])

@router.post("/", response_model=PrescriptionResponse)
async def create_prescription(
    prescription_data: PrescriptionCreateRequest,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Create a new digital prescription."""
    
    try:
        # Validate prescription based on type
        validation_errors = []
        
        if prescription_data.prescription_type == PrescriptionType.ANTIMICROBIAL:
            validation_errors = PrescriptionValidationRules.validate_antimicrobial(prescription_data.items)
        elif prescription_data.prescription_type == PrescriptionType.C1:
            validation_errors = PrescriptionValidationRules.validate_c1(prescription_data.items)
        else:
            validation_errors = PrescriptionValidationRules.validate_simple(prescription_data.items)
        
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation errors: {', '.join(validation_errors)}"
            )
        
        # Convert items to dict format for storage
        items_dict = [item.dict() for item in prescription_data.items]
        
        # Create prescription record
        prescription = Prescription(
            clinic_id=current_tenant.id,
            patient_id=prescription_data.patient_id,
            doctor_id=prescription_data.doctor_id,
            items=items_dict,
            prescription_type=prescription_data.prescription_type,
            status=PrescriptionStatus.DRAFT,
            rx_meta=prescription_data.rx_meta,
            notes=prescription_data.notes,
            expires_at=datetime.utcnow() + timedelta(days=30)  # Default 30 days expiry
        )
        
        db.add(prescription)
        db.commit()
        db.refresh(prescription)
        
        logger.info(f"Prescription created: {prescription.id} by user {current_user.id}")
        
        return PrescriptionResponse.from_orm(prescription)
        
    except Exception as e:
        logger.error(f"Error creating prescription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create prescription"
        )

@router.get("/{prescription_id}", response_model=PrescriptionResponse)
async def get_prescription(
    prescription_id: uuid.UUID,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get a prescription by ID."""
    
    statement = select(Prescription).where(
        Prescription.id == prescription_id,
        Prescription.clinic_id == current_tenant.id
    )
    prescription = db.exec(statement).first()
    
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found"
        )
    
    return PrescriptionResponse.from_orm(prescription)

@router.post("/{prescription_id}/sign", response_model=PrescriptionSignResponse)
async def sign_prescription(
    prescription_id: uuid.UUID,
    sign_data: PrescriptionSignRequest,
    request: Request,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Sign a prescription with PAdES digital signature."""
    
    try:
        # Get prescription
        statement = select(Prescription).where(
            Prescription.id == prescription_id,
            Prescription.clinic_id == current_tenant.id
        )
        prescription = db.exec(statement).first()
        
        if not prescription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prescription not found"
            )
        
        if prescription.status != PrescriptionStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft prescriptions can be signed"
            )
        
        # Initialize services
        pdf_generator = PDFGenerator()
        signature_service = DigitalSignatureService()
        qr_generator = QRCodeGenerator()
        
        # Generate PDF from prescription
        pdf_content = await pdf_generator.generate_prescription_pdf(
            prescription=prescription,
            clinic=current_tenant,
            doctor=current_user
        )
        
        # Sign PDF with PAdES
        signature_result = await signature_service.sign_pdf_pades(
            pdf_content=pdf_content,
            certificate_id=sign_data.certificate_id,
            pin=sign_data.pin,
            prescription_id=str(prescription_id)
        )
        
        # Generate QR token
        qr_token = qr_generator.generate_qr_token(
            prescription_id=prescription_id,
            signature_id=signature_result.signature_id,
            created_at=prescription.created_at
        )
        
        # Upload signed PDF to S3
        signed_pdf_path = await pdf_generator.upload_signed_pdf(
            pdf_content=signature_result.signed_pdf,
            prescription_id=prescription_id,
            qr_token=qr_token
        )
        
        # Update prescription with signature data
        prescription.status = PrescriptionStatus.SIGNED
        prescription.signed_pdf_path = signed_pdf_path
        prescription.signature_meta = signature_result.metadata.dict()
        prescription.qr_token = qr_token
        prescription.signer_user_id = sign_data.signer_user_id
        prescription.certificate_id = sign_data.certificate_id
        prescription.signed_at = datetime.utcnow()
        
        db.add(prescription)
        db.commit()
        
        # Generate verification URL
        verification_url = f"/public/prescriptions/verify/{qr_token}"
        
        logger.info(f"Prescription signed: {prescription_id} by user {sign_data.signer_user_id}")
        
        return PrescriptionSignResponse(
            prescription_id=prescription_id,
            status=PrescriptionStatus.SIGNED,
            signed_pdf_path=signed_pdf_path,
            qr_token=qr_token,
            signature_meta=signature_result.metadata.dict(),
            verification_url=verification_url,
            message="Prescription signed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error signing prescription {prescription_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sign prescription: {str(e)}"
        )

@router.get("/{prescription_id}/pdf")
async def download_prescription_pdf(
    prescription_id: uuid.UUID,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Download prescription PDF."""
    
    statement = select(Prescription).where(
        Prescription.id == prescription_id,
        Prescription.clinic_id == current_tenant.id
    )
    prescription = db.exec(statement).first()
    
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found"
        )
    
    if not prescription.signed_pdf_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prescription not signed yet"
        )
    
    # Return PDF file
    return FileResponse(
        path=prescription.signed_pdf_path,
        filename=f"prescription_{prescription_id}.pdf",
        media_type="application/pdf"
    )

@router.get("/{prescription_id}/qr")
async def get_prescription_qr(
    prescription_id: uuid.UUID,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get QR code for prescription verification."""
    
    statement = select(Prescription).where(
        Prescription.id == prescription_id,
        Prescription.clinic_id == current_tenant.id
    )
    prescription = db.exec(statement).first()
    
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found"
        )
    
    if not prescription.qr_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prescription not signed yet"
        )
    
    qr_generator = QRCodeGenerator()
    qr_image = qr_generator.generate_qr_image(
        verification_url=f"/public/prescriptions/verify/{prescription.qr_token}"
    )
    
    return FileResponse(
        path=qr_image,
        filename=f"prescription_qr_{prescription_id}.png",
        media_type="image/png"
    )

@router.get("/", response_model=List[PrescriptionResponse])
async def list_prescriptions(
    patient_id: Optional[uuid.UUID] = None,
    doctor_id: Optional[uuid.UUID] = None,
    status: Optional[PrescriptionStatus] = None,
    prescription_type: Optional[PrescriptionType] = None,
    limit: int = 50,
    offset: int = 0,
    current_user = Depends(get_current_user),
    current_tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """List prescriptions with optional filters."""
    
    statement = select(Prescription).where(Prescription.clinic_id == current_tenant.id)
    
    if patient_id:
        statement = statement.where(Prescription.patient_id == patient_id)
    
    if doctor_id:
        statement = statement.where(Prescription.doctor_id == doctor_id)
    
    if status:
        statement = statement.where(Prescription.status == status)
    
    if prescription_type:
        statement = statement.where(Prescription.prescription_type == prescription_type)
    
    statement = statement.offset(offset).limit(limit).order_by(Prescription.created_at.desc())
    
    prescriptions = db.exec(statement).all()
    
    return [PrescriptionResponse.from_orm(prescription) for prescription in prescriptions]

# Public verification endpoint (no authentication required)
@router.get("/public/verify/{qr_token}", response_model=PrescriptionVerificationResponse)
async def verify_prescription(
    qr_token: str,
    db: Session = Depends(get_db)
):
    """Public endpoint to verify prescription signature."""
    
    try:
        # Find prescription by QR token
        statement = select(Prescription).where(Prescription.qr_token == qr_token)
        prescription = db.exec(statement).first()
        
        if not prescription:
            return PrescriptionVerificationResponse(
                valid=False,
                error_message="Prescription not found"
            )
        
        # Check if prescription is expired
        if prescription.expires_at and prescription.expires_at < datetime.utcnow():
            return PrescriptionVerificationResponse(
                valid=False,
                error_message="Prescription has expired"
            )
        
        # Verify signature
        signature_service = DigitalSignatureService()
        verification_result = await signature_service.verify_pdf_signature(
            pdf_path=prescription.signed_pdf_path,
            signature_meta=prescription.signature_meta
        )
        
        if verification_result.valid:
            return PrescriptionVerificationResponse(
                valid=True,
                prescription_id=prescription.id,
                doctor_name=prescription.doctor.name if prescription.doctor else None,
                doctor_crm=prescription.doctor.metadata.get('crm') if prescription.doctor and prescription.doctor.metadata else None,
                patient_name=prescription.patient.name if prescription.patient else None,
                clinic_name=prescription.clinic.name if prescription.clinic else None,
                signed_at=prescription.signed_at,
                prescription_type=prescription.prescription_type,
                signature_meta=prescription.signature_meta
            )
        else:
            return PrescriptionVerificationResponse(
                valid=False,
                error_message=verification_result.error_message
            )
            
    except Exception as e:
        logger.error(f"Error verifying prescription {qr_token}: {str(e)}")
        return PrescriptionVerificationResponse(
            valid=False,
            error_message="Verification failed"
        )

@router.get("/public/verify/{qr_token}/html", response_class=HTMLResponse)
async def verify_prescription_html(
    qr_token: str,
    db: Session = Depends(get_db)
):
    """Public HTML page for prescription verification."""
    
    verification_result = await verify_prescription(qr_token, db)
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verificação de Prescrição Digital</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .status {{
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                text-align: center;
                font-weight: bold;
            }}
            .valid {{
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }}
            .invalid {{
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }}
            .info {{
                margin: 10px 0;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 5px;
            }}
            .label {{
                font-weight: bold;
                color: #495057;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏥 Verificação de Prescrição Digital</h1>
                <p>Sistema de Verificação ICP-Brasil</p>
            </div>
            
            <div class="status {'valid' if verification_result.valid else 'invalid'}">
                {'✅ Prescrição Válida' if verification_result.valid else '❌ Prescrição Inválida'}
            </div>
            
            {f'''
            <div class="info">
                <div class="label">Médico:</div>
                <div>{verification_result.doctor_name or 'N/A'}</div>
            </div>
            
            <div class="info">
                <div class="label">CRM:</div>
                <div>{verification_result.doctor_crm or 'N/A'}</div>
            </div>
            
            <div class="info">
                <div class="label">Paciente:</div>
                <div>{verification_result.patient_name or 'N/A'}</div>
            </div>
            
            <div class="info">
                <div class="label">Clínica:</div>
                <div>{verification_result.clinic_name or 'N/A'}</div>
            </div>
            
            <div class="info">
                <div class="label">Data da Assinatura:</div>
                <div>{verification_result.signed_at.strftime('%d/%m/%Y %H:%M') if verification_result.signed_at else 'N/A'}</div>
            </div>
            
            <div class="info">
                <div class="label">Tipo de Prescrição:</div>
                <div>{verification_result.prescription_type.value if verification_result.prescription_type else 'N/A'}</div>
            </div>
            ''' if verification_result.valid else f'''
            <div class="info">
                <div class="label">Erro:</div>
                <div>{verification_result.error_message or 'Erro desconhecido'}</div>
            </div>
            '''}
            
            <div class="info">
                <div class="label">Verificado em:</div>
                <div>{verification_result.verification_timestamp.strftime('%d/%m/%Y %H:%M:%S')}</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)
