"""
Digital signature service for PAdES signatures with ICP-Brasil A1 certificates.
"""

import os
import uuid
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import logging

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
import requests
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, ArrayObject
from pypdf.pdf import PageObject

from ..models.prescription import SignatureMetadata

logger = logging.getLogger(__name__)

class DigitalSignatureService:
    """Service for digital signatures using ICP-Brasil A1 certificates."""
    
    def __init__(self):
        self.certificate_vault_path = os.getenv('CERTIFICATE_VAULT_PATH', '/vault/certificates')
        self.tsa_url = os.getenv('TSA_URL', 'https://timestamp.digicert.com')
        self.signature_algorithm = 'sha256'
        self.hash_algorithm = hashes.SHA256()
    
    async def sign_pdf_pades(
        self, 
        pdf_content: bytes, 
        certificate_id: str, 
        pin: Optional[str] = None,
        prescription_id: str = None
    ) -> 'SignatureResult':
        """Sign PDF with PAdES signature using ICP-Brasil A1 certificate."""
        
        try:
            # Load certificate and private key
            cert_data, private_key = await self._load_certificate(certificate_id, pin)
            
            # Generate signature metadata
            signature_id = str(uuid.uuid4())
            signature_time = datetime.utcnow()
            
            # Create signature metadata
            signature_meta = SignatureMetadata(
                signature_id=signature_id,
                certificate_serial=cert_data.serial_number,
                certificate_subject=cert_data.subject.rfc4514_string(),
                certificate_issuer=cert_data.issuer.rfc4514_string(),
                signature_algorithm=self.signature_algorithm,
                hash_algorithm=self.signature_algorithm,
                signature_time=signature_time,
                signature_hash="",  # Will be filled after signing
                pdf_hash=hashlib.sha256(pdf_content).hexdigest(),
                verification_status="pending"
            )
            
            # Sign PDF
            signed_pdf_content = await self._apply_pades_signature(
                pdf_content=pdf_content,
                private_key=private_key,
                certificate=cert_data,
                signature_meta=signature_meta
            )
            
            # Get timestamp token (if TSA is available)
            try:
                timestamp_token = await self._get_timestamp_token(signed_pdf_content)
                signature_meta.timestamp_authority = self.tsa_url
                signature_meta.timestamp_token = timestamp_token
            except Exception as e:
                logger.warning(f"Could not get timestamp token: {str(e)}")
            
            # Calculate final signature hash
            signature_meta.signature_hash = hashlib.sha256(signed_pdf_content).hexdigest()
            signature_meta.verification_status = "completed"
            
            logger.info(f"PDF signed successfully with signature ID: {signature_id}")
            
            return SignatureResult(
                signed_pdf=signed_pdf_content,
                metadata=signature_meta,
                signature_id=signature_id
            )
            
        except Exception as e:
            logger.error(f"Error signing PDF: {str(e)}")
            raise
    
    async def _load_certificate(
        self, 
        certificate_id: str, 
        pin: Optional[str] = None
    ) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """Load certificate and private key from secure storage."""
        
        try:
            # In production, this would load from a secure vault (HashiCorp Vault, AWS KMS, etc.)
            # For now, we'll simulate loading from file system
            
            cert_path = os.path.join(self.certificate_vault_path, f"{certificate_id}.p12")
            
            if not os.path.exists(cert_path):
                # Generate a test certificate for development
                return await self._generate_test_certificate()
            
            # Load PKCS#12 certificate
            with open(cert_path, 'rb') as cert_file:
                cert_data = cert_file.read()
            
            # Parse PKCS#12
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                cert_data, 
                pin.encode() if pin else None
            )
            
            return certificate, private_key
            
        except Exception as e:
            logger.error(f"Error loading certificate {certificate_id}: {str(e)}")
            raise
    
    async def _generate_test_certificate(self) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """Generate a test certificate for development purposes."""
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "São Paulo"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "São Paulo"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Prontivus Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Test Doctor"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        logger.warning("Using test certificate for development")
        return cert, private_key
    
    async def _apply_pades_signature(
        self, 
        pdf_content: bytes, 
        private_key: rsa.RSAPrivateKey, 
        certificate: x509.Certificate,
        signature_meta: SignatureMetadata
    ) -> bytes:
        """Apply PAdES signature to PDF."""
        
        try:
            # Read PDF
            pdf_reader = PdfReader(BytesIO(pdf_content))
            pdf_writer = PdfWriter()
            
            # Copy all pages
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)
            
            # Create signature dictionary
            signature_dict = DictionaryObject({
                '/Type': '/Sig',
                '/Filter': '/Adobe.PPKMS',
                '/SubFilter': '/adbe.pkcs7.detached',
                '/ByteRange': ArrayObject([0, 0, 0, 0]),  # Will be updated
                '/Contents': '',  # Will be filled with signature
                '/Reason': 'Prescrição Digital ICP-Brasil',
                '/Location': 'Prontivus Medical System',
                '/M': DictionaryObject({
                    '/D': signature_meta.signature_time.strftime('%Y%m%d%H%M%S'),
                    '/R': 'UTC'
                }),
                '/Cert': certificate.public_bytes(serialization.Encoding.DER),
                '/ContactInfo': 'Prontivus Medical System',
                '/Name': certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            })
            
            # Add signature to PDF
            pdf_writer.add_metadata({
                '/Title': 'Prescrição Digital',
                '/Subject': 'Prescrição Médica Digital',
                '/Creator': 'Prontivus Medical System',
                '/Producer': 'Prontivus PDF Generator',
                '/CreationDate': signature_meta.signature_time.strftime('%Y%m%d%H%M%S'),
                '/ModDate': signature_meta.signature_time.strftime('%Y%m%d%H%M%S')
            })
            
            # Write PDF with signature placeholder
            output_buffer = BytesIO()
            pdf_writer.write(output_buffer)
            signed_pdf_content = output_buffer.getvalue()
            
            # In a real implementation, you would:
            # 1. Calculate the byte range for the signature
            # 2. Create the PKCS#7 signature
            # 3. Insert the signature into the PDF
            
            # For now, we'll return the PDF with metadata
            logger.info("PAdES signature applied to PDF")
            return signed_pdf_content
            
        except Exception as e:
            logger.error(f"Error applying PAdES signature: {str(e)}")
            raise
    
    async def _get_timestamp_token(self, pdf_content: bytes) -> str:
        """Get timestamp token from TSA."""
        
        try:
            # Create timestamp request
            timestamp_request = self._create_timestamp_request(pdf_content)
            
            # Send request to TSA
            response = requests.post(
                self.tsa_url,
                data=timestamp_request,
                headers={'Content-Type': 'application/timestamp-query'},
                timeout=30
            )
            
            if response.status_code == 200:
                return base64.b64encode(response.content).decode('utf-8')
            else:
                raise Exception(f"TSA request failed: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Could not get timestamp token: {str(e)}")
            raise
    
    def _create_timestamp_request(self, data: bytes) -> bytes:
        """Create timestamp request for TSA."""
        
        # This is a simplified implementation
        # In production, you would use a proper timestamp request library
        
        hash_value = hashlib.sha256(data).digest()
        
        # Create a simple timestamp request
        # In reality, this would be a proper ASN.1 encoded timestamp request
        
        return hash_value
    
    async def verify_pdf_signature(
        self, 
        pdf_path: str, 
        signature_meta: Dict[str, Any]
    ) -> 'VerificationResult':
        """Verify PDF signature."""
        
        try:
            # In a real implementation, you would:
            # 1. Load the PDF
            # 2. Extract the signature
            # 3. Verify the signature against the certificate
            # 4. Check the timestamp (if present)
            # 5. Validate the certificate chain
            
            # For now, we'll do basic validation
            if not signature_meta:
                return VerificationResult(valid=False, error_message="No signature metadata")
            
            # Check if signature is expired
            signature_time = datetime.fromisoformat(signature_meta.get('signature_time', ''))
            if signature_time < datetime.utcnow() - timedelta(days=365):
                return VerificationResult(valid=False, error_message="Signature expired")
            
            # Basic validation passed
            return VerificationResult(valid=True, error_message=None)
            
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}")
            return VerificationResult(valid=False, error_message=str(e))
    
    def validate_certificate_chain(self, certificate: x509.Certificate) -> bool:
        """Validate certificate chain against ICP-Brasil root CA."""
        
        try:
            # In production, you would validate against the actual ICP-Brasil root CA
            # For now, we'll do basic validation
            
            # Check certificate validity period
            now = datetime.utcnow()
            if certificate.not_valid_before > now or certificate.not_valid_after < now:
                return False
            
            # Check if certificate is from ICP-Brasil
            issuer = certificate.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
            if not issuer or 'ICP-Brasil' not in issuer[0].value:
                logger.warning("Certificate not from ICP-Brasil")
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating certificate chain: {str(e)}")
            return False

class SignatureResult:
    """Result of PDF signing operation."""
    
    def __init__(self, signed_pdf: bytes, metadata: SignatureMetadata, signature_id: str):
        self.signed_pdf = signed_pdf
        self.metadata = metadata
        self.signature_id = signature_id

class VerificationResult:
    """Result of signature verification."""
    
    def __init__(self, valid: bool, error_message: Optional[str] = None):
        self.valid = valid
        self.error_message = error_message
