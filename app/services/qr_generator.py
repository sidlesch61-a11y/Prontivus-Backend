"""
QR Code generation service for prescription verification.
"""

import uuid
import hashlib
import base64
from datetime import datetime
from typing import Optional
import logging

import qrcode
from qrcode.image.pil import PilImage
from io import BytesIO
import os

logger = logging.getLogger(__name__)

class QRCodeGenerator:
    """Service for generating QR codes for prescription verification."""
    
    def __init__(self):
        self.base_url = os.getenv('BASE_URL', 'https://prontivus-backend-wnw2.onrender.com')
        self.qr_size = 10
        self.qr_border = 4
    
    def generate_qr_token(
        self, 
        prescription_id: uuid.UUID, 
        signature_id: str, 
        created_at: datetime
    ) -> str:
        """Generate QR token for prescription verification."""
        
        try:
            # Create token data
            token_data = f"{prescription_id}:{signature_id}:{created_at.isoformat()}"
            
            # Generate hash
            token_hash = hashlib.sha256(token_data.encode()).digest()
            
            # Encode as base64url (URL-safe base64)
            qr_token = base64.urlsafe_b64encode(token_hash).decode('utf-8').rstrip('=')
            
            logger.info(f"QR token generated for prescription {prescription_id}")
            return qr_token
            
        except Exception as e:
            logger.error(f"Error generating QR token: {str(e)}")
            raise
    
    def generate_qr_image(self, verification_url: str) -> str:
        """Generate QR code image file."""
        
        try:
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=self.qr_size,
                border=self.qr_border,
            )
            
            qr.add_data(verification_url)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save to temporary file
            temp_filename = f"qr_{uuid.uuid4().hex}.png"
            temp_path = os.path.join("/tmp", temp_filename)
            
            img.save(temp_path)
            
            logger.info(f"QR code image generated: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error generating QR code image: {str(e)}")
            raise
    
    def generate_qr_data(
        self, 
        prescription_id: uuid.UUID, 
        qr_token: str, 
        signature_hash: str,
        expires_at: Optional[datetime] = None
    ) -> dict:
        """Generate QR code data structure."""
        
        verification_url = f"{self.base_url}/public/prescriptions/verify/{qr_token}"
        
        return {
            "prescription_id": str(prescription_id),
            "qr_token": qr_token,
            "verification_url": verification_url,
            "signature_hash": signature_hash,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None
        }
    
    def generate_qr_svg(self, verification_url: str) -> str:
        """Generate QR code as SVG."""
        
        try:
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=self.qr_size,
                border=self.qr_border,
            )
            
            qr.add_data(verification_url)
            qr.make(fit=True)
            
            # Create SVG
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to SVG (simplified)
            svg_content = f"""
            <svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
                <rect width="200" height="200" fill="white"/>
                <text x="100" y="100" text-anchor="middle" font-family="Arial" font-size="12">
                    QR Code for Verification
                </text>
                <text x="100" y="120" text-anchor="middle" font-family="Arial" font-size="10">
                    {verification_url}
                </text>
            </svg>
            """
            
            return svg_content
            
        except Exception as e:
            logger.error(f"Error generating QR SVG: {str(e)}")
            raise
    
    def generate_qr_html(self, verification_url: str) -> str:
        """Generate HTML with embedded QR code."""
        
        try:
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=self.qr_size,
                border=self.qr_border,
            )
            
            qr.add_data(verification_url)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            html_content = f"""
            <div class="qr-code-container">
                <h3>Verificação de Prescrição Digital</h3>
                <div class="qr-code">
                    <img src="data:image/png;base64,{img_str}" alt="QR Code" />
                </div>
                <p class="verification-url">
                    <a href="{verification_url}" target="_blank">{verification_url}</a>
                </p>
                <p class="instructions">
                    Escaneie o QR Code ou acesse o link para verificar a autenticidade da prescrição.
                </p>
            </div>
            """
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error generating QR HTML: {str(e)}")
            raise
    
    def validate_qr_token(self, qr_token: str) -> bool:
        """Validate QR token format."""
        
        try:
            # Check if token is valid base64url
            if not qr_token:
                return False
            
            # Check length (should be 32 characters for base64url encoded SHA256)
            if len(qr_token) != 43:  # 32 bytes * 4/3 = 43 characters (rounded up)
                return False
            
            # Try to decode
            decoded = base64.urlsafe_b64decode(qr_token + '==')  # Add padding
            
            # Check if it's 32 bytes (SHA256 hash)
            if len(decoded) != 32:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating QR token: {str(e)}")
            return False
    
    def generate_qr_for_prescription(
        self, 
        prescription_id: uuid.UUID, 
        signature_hash: str,
        expires_at: Optional[datetime] = None
    ) -> dict:
        """Generate complete QR code data for a prescription."""
        
        # Generate QR token
        qr_token = self.generate_qr_token(
            prescription_id=prescription_id,
            signature_id=signature_hash,
            created_at=datetime.utcnow()
        )
        
        # Generate QR data
        qr_data = self.generate_qr_data(
            prescription_id=prescription_id,
            qr_token=qr_token,
            signature_hash=signature_hash,
            expires_at=expires_at
        )
        
        # Generate verification URL
        verification_url = f"{self.base_url}/public/prescriptions/verify/{qr_token}"
        
        return {
            "qr_token": qr_token,
            "verification_url": verification_url,
            "qr_data": qr_data,
            "qr_image_path": self.generate_qr_image(verification_url),
            "qr_html": self.generate_qr_html(verification_url)
        }
