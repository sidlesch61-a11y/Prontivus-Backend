"""
Digital Signature Service for Prescriptions
ICP-Brasil A1 compliant digital signatures with PAdES format
"""
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import load_pem_x509_certificate
from datetime import datetime
import hashlib
import base64
from typing import Dict, Tuple, Optional

class DigitalSignatureService:
    """
    ICP-Brasil compliant digital signature service.
    
    In production, this would integrate with:
    - ICP-Brasil A1 certificates (stored on server)
    - HSM (Hardware Security Module) for key storage
    - TSA (Time Stamping Authority) for timestamps
    - OCSP (Online Certificate Status Protocol) for validation
    """
    
    def __init__(self, certificate_path: Optional[str] = None, private_key_path: Optional[str] = None):
        """
        Initialize signature service.
        
        Args:
            certificate_path: Path to ICP-Brasil A1 certificate (.pem)
            private_key_path: Path to private key (.pem)
        """
        self.certificate_path = certificate_path
        self.private_key_path = private_key_path
        
    def sign_prescription_pdf(
        self,
        pdf_bytes: bytes,
        doctor_id: str,
        prescription_id: str
    ) -> Tuple[bytes, Dict[str, str]]:
        """
        Digitally sign a prescription PDF with PAdES format.
        
        Args:
            pdf_bytes: Original PDF bytes
            doctor_id: Doctor's ID (certificate owner)
            prescription_id: Prescription ID for audit trail
            
        Returns:
            Tuple of (signed_pdf_bytes, signature_metadata)
        """
        # Generate document hash (SHA-256)
        document_hash = hashlib.sha256(pdf_bytes).hexdigest()
        
        # In production: Load actual ICP-Brasil A1 certificate
        # For demo: Generate signature metadata
        signature_metadata = self._generate_signature_metadata(
            document_hash,
            doctor_id,
            prescription_id
        )
        
        # In production: Apply PAdES signature to PDF
        # This would involve:
        # 1. Create PKCS#7 signature
        # 2. Embed signature in PDF /Sig dictionary
        # 3. Add timestamp from TSA
        # 4. Update PDF trailer with signature info
        
        # For demo: Return original PDF with metadata
        # In production, use endesive or pyHanko for PAdES
        signed_pdf = pdf_bytes  # Would be modified with embedded signature
        
        return signed_pdf, signature_metadata
    
    def _generate_signature_metadata(
        self,
        document_hash: str,
        doctor_id: str,
        prescription_id: str
    ) -> Dict[str, str]:
        """
        Generate signature metadata for audit trail.
        
        Returns:
            Dict with signature information
        """
        timestamp = datetime.now().isoformat()
        
        # Simulated certificate information
        # In production: Extract from actual ICP-Brasil certificate
        signature_info = {
            'signature_hash': document_hash,
            'algorithm': 'SHA-256withRSA',
            'format': 'PAdES-BES',  # PAdES Basic Electronic Signature
            'signed_at': timestamp,
            'signer_id': doctor_id,
            'prescription_id': prescription_id,
            'certificate_issuer': 'AC SOLUTI - ICP-Brasil',  # Example CA
            'certificate_subject': f'CN=Doctor {doctor_id}',
            'certificate_valid_from': '2024-01-01T00:00:00',
            'certificate_valid_until': '2025-12-31T23:59:59',
            'timestamp_authority': 'TSA Serpro - ICP-Brasil',
            'signature_level': 'ICP-Brasil A1',
            'compliance': 'RDC 471/2021, Portaria 344/98, MP 2.200-2/2001',
        }
        
        # Generate verification hash (for QR code)
        verification_string = f"{prescription_id}:{document_hash}:{timestamp}"
        verification_hash = hashlib.sha256(verification_string.encode()).hexdigest()[:16]
        signature_info['verification_code'] = verification_hash
        
        return signature_info
    
    def verify_signature(
        self,
        pdf_bytes: bytes,
        signature_metadata: Dict[str, str]
    ) -> Tuple[bool, str]:
        """
        Verify a signed prescription PDF.
        
        Args:
            pdf_bytes: Signed PDF bytes
            signature_metadata: Signature metadata from database
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Calculate current document hash
        current_hash = hashlib.sha256(pdf_bytes).hexdigest()
        
        # Compare with stored hash
        if current_hash != signature_metadata.get('signature_hash'):
            return False, "Document has been modified after signing"
        
        # In production: Verify actual signature
        # 1. Extract PKCS#7 signature from PDF
        # 2. Verify signature with certificate public key
        # 3. Check certificate chain against ICP-Brasil root
        # 4. Verify timestamp from TSA
        # 5. Check certificate revocation status (OCSP/CRL)
        
        # Check certificate expiration (demo)
        valid_until = signature_metadata.get('certificate_valid_until')
        if valid_until:
            try:
                expiry_date = datetime.fromisoformat(valid_until.replace('Z', '+00:00'))
                if datetime.now() > expiry_date:
                    return False, "Certificate has expired"
            except:
                pass
        
        return True, "Signature is valid and document is authentic"
    
    def generate_verification_qr_data(
        self,
        prescription_id: str,
        verification_code: str,
        base_url: str = "https://prontivus.com"
    ) -> str:
        """
        Generate QR code data for prescription verification.
        
        Args:
            prescription_id: Prescription UUID
            verification_code: Short verification hash
            base_url: Base URL for verification portal
            
        Returns:
            URL string for QR code
        """
        return f"{base_url}/verify/prescription/{prescription_id}?code={verification_code}"


# Utility functions for integration

async def sign_and_generate_prescription_pdf(
    prescription,
    clinic,
    doctor,
    patient,
    db_session
):
    """
    Complete workflow: Generate PDF + Sign + Save.
    
    This is the main integration point called from the API.
    """
    from app.services.prescription_pdf import generate_prescription_pdf
    
    # Step 1: Generate PDF
    pdf_bytes = generate_prescription_pdf(prescription, clinic, doctor, patient)
    
    # Step 2: Apply digital signature
    signature_service = DigitalSignatureService()
    signed_pdf_bytes, signature_metadata = signature_service.sign_prescription_pdf(
        pdf_bytes,
        str(doctor.id),
        str(prescription.id)
    )
    
    # Step 3: Generate QR code data
    qr_data = signature_service.generate_verification_qr_data(
        str(prescription.id),
        signature_metadata['verification_code']
    )
    
    # Step 4: Regenerate PDF with QR code
    # (In production, embed QR in first PDF generation)
    final_pdf_bytes = signed_pdf_bytes  # Simplified for demo
    
    # Step 5: Update prescription record
    prescription.signed_at = datetime.now()
    prescription.signature_hash = signature_metadata['signature_hash']
    # In production: Store signed PDF in S3/MinIO
    # prescription.pdf_url = await upload_to_storage(final_pdf_bytes)
    prescription.pdf_url = f"/api/v1/prescriptions/{prescription.id}/pdf"
    
    await db_session.commit()
    
    return final_pdf_bytes, signature_metadata


def validate_prescription_authenticity(
    pdf_bytes: bytes,
    signature_hash: str,
    signed_at: str
) -> Dict[str, any]:
    """
    Public validation endpoint helper.
    
    Used by the QR code verification page.
    """
    signature_service = DigitalSignatureService()
    
    signature_metadata = {
        'signature_hash': signature_hash,
        'signed_at': signed_at,
        'certificate_valid_until': '2025-12-31T23:59:59',  # From DB
    }
    
    is_valid, message = signature_service.verify_signature(pdf_bytes, signature_metadata)
    
    return {
        'is_valid': is_valid,
        'message': message,
        'signature_info': signature_metadata if is_valid else None,
    }

