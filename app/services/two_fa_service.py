"""
Two-Factor Authentication Service
Handles TOTP generation, verification, and QR code creation
"""

import pyotp
import qrcode
import io
import base64
import secrets
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.two_fa import TwoFASecret, TwoFAStatus
from app.core.config import settings


class TwoFAService:
    """Service for handling two-factor authentication."""
    
    def __init__(self):
        # In production, get this from environment variable
        # For now, using a consistent key (CHANGE THIS IN PRODUCTION!)
        self.encryption_key = settings.SECRET_KEY[:32].ljust(32, '0').encode()
        self.fernet = Fernet(base64.urlsafe_b64encode(self.encryption_key))
    
    def generate_secret(self) -> str:
        """Generate a new TOTP secret."""
        return pyotp.random_base32()
    
    def generate_backup_codes(self, count: int = 8) -> List[str]:
        """Generate backup codes for 2FA recovery."""
        return [secrets.token_hex(4).upper() for _ in range(count)]
    
    def encrypt_secret(self, secret: str) -> str:
        """Encrypt a secret for storage."""
        return self.fernet.encrypt(secret.encode()).decode()
    
    def decrypt_secret(self, encrypted_secret: str) -> str:
        """Decrypt a stored secret."""
        return self.fernet.decrypt(encrypted_secret.encode()).decode()
    
    def encrypt_backup_codes(self, codes: List[str]) -> str:
        """Encrypt backup codes for storage."""
        codes_str = ','.join(codes)
        return self.fernet.encrypt(codes_str.encode()).decode()
    
    def decrypt_backup_codes(self, encrypted_codes: str) -> List[str]:
        """Decrypt stored backup codes."""
        codes_str = self.fernet.decrypt(encrypted_codes.encode()).decode()
        return codes_str.split(',')
    
    def verify_totp_code(self, secret: str, code: str) -> bool:
        """Verify a TOTP code against secret."""
        totp = pyotp.TOTP(secret)
        # Allow 1 time step tolerance (30 seconds before/after)
        return totp.verify(code, valid_window=1)
    
    def verify_backup_code(self, backup_codes: List[str], code: str) -> Tuple[bool, Optional[List[str]]]:
        """
        Verify a backup code and remove it if valid.
        Returns (is_valid, remaining_codes)
        """
        code_upper = code.upper().replace('-', '')
        
        if code_upper in backup_codes:
            remaining = [c for c in backup_codes if c != code_upper]
            return True, remaining
        
        return False, backup_codes
    
    def generate_qr_code(self, secret: str, user_email: str, issuer: str = "Prontivus") -> str:
        """
        Generate QR code for 2FA setup.
        Returns base64 encoded PNG image as data URI.
        """
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user_email,
            issuer_name=issuer
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    async def setup_2fa(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        user_email: str
    ) -> Tuple[str, str, List[str]]:
        """
        Setup 2FA for a user.
        Returns (secret, qr_code_data, backup_codes)
        """
        # Generate secret and backup codes
        secret = self.generate_secret()
        backup_codes = self.generate_backup_codes()
        
        # Encrypt for storage
        encrypted_secret = self.encrypt_secret(secret)
        encrypted_backup_codes = self.encrypt_backup_codes(backup_codes)
        
        # Check if user already has 2FA record
        result = await db.execute(
            select(TwoFASecret).where(TwoFASecret.user_id == user_id)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing
            existing.secret_encrypted = encrypted_secret
            existing.backup_codes_encrypted = encrypted_backup_codes
            existing.status = TwoFAStatus.PENDING
            existing.created_at = datetime.utcnow()
            existing.failed_attempts = 0
            existing.locked_until = None
        else:
            # Create new
            two_fa_secret = TwoFASecret(
                user_id=user_id,
                secret_encrypted=encrypted_secret,
                backup_codes_encrypted=encrypted_backup_codes,
                status=TwoFAStatus.PENDING
            )
            db.add(two_fa_secret)
        
        await db.commit()
        
        # Generate QR code
        qr_code_data = self.generate_qr_code(secret, user_email)
        
        return secret, qr_code_data, backup_codes
    
    async def verify_and_enable_2fa(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        code: str
    ) -> bool:
        """Verify code and enable 2FA if correct."""
        # Get 2FA record
        result = await db.execute(
            select(TwoFASecret).where(TwoFASecret.user_id == user_id)
        )
        two_fa = result.scalar_one_or_none()
        
        if not two_fa:
            return False
        
        # Check if locked
        if two_fa.locked_until and datetime.utcnow() < two_fa.locked_until:
            return False
        
        # Decrypt secret
        secret = self.decrypt_secret(two_fa.secret_encrypted)
        
        # Verify code
        if self.verify_totp_code(secret, code):
            # Enable 2FA
            two_fa.status = TwoFAStatus.ENABLED
            two_fa.enabled_at = datetime.utcnow()
            two_fa.failed_attempts = 0
            two_fa.locked_until = None
            
            # Update user record
            from app.models import User
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                user.two_fa_enabled = True
                user.two_fa_verified_at = datetime.utcnow()
            
            await db.commit()
            return True
        else:
            # Increment failed attempts
            two_fa.failed_attempts += 1
            if two_fa.failed_attempts >= 5:
                two_fa.locked_until = datetime.utcnow() + timedelta(minutes=15)
            await db.commit()
            return False
    
    async def verify_2fa_for_login(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        code: str
    ) -> bool:
        """Verify 2FA code during login."""
        result = await db.execute(
            select(TwoFASecret).where(
                TwoFASecret.user_id == user_id,
                TwoFASecret.status == TwoFAStatus.ENABLED
            )
        )
        two_fa = result.scalar_one_or_none()
        
        if not two_fa:
            return False
        
        # Check if locked
        if two_fa.locked_until and datetime.utcnow() < two_fa.locked_until:
            return False
        
        # Decrypt secret and backup codes
        secret = self.decrypt_secret(two_fa.secret_encrypted)
        
        # Try TOTP code first
        if self.verify_totp_code(secret, code):
            two_fa.last_used_at = datetime.utcnow()
            two_fa.failed_attempts = 0
            await db.commit()
            return True
        
        # Try backup codes
        if two_fa.backup_codes_encrypted:
            backup_codes = self.decrypt_backup_codes(two_fa.backup_codes_encrypted)
            is_valid, remaining_codes = self.verify_backup_code(backup_codes, code)
            
            if is_valid:
                # Update backup codes
                if remaining_codes:
                    two_fa.backup_codes_encrypted = self.encrypt_backup_codes(remaining_codes)
                else:
                    two_fa.backup_codes_encrypted = None
                
                two_fa.last_used_at = datetime.utcnow()
                two_fa.failed_attempts = 0
                await db.commit()
                return True
        
        # Invalid code
        two_fa.failed_attempts += 1
        if two_fa.failed_attempts >= 5:
            two_fa.locked_until = datetime.utcnow() + timedelta(minutes=15)
        await db.commit()
        return False
    
    async def disable_2fa(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> bool:
        """Disable 2FA for a user."""
        result = await db.execute(
            select(TwoFASecret).where(TwoFASecret.user_id == user_id)
        )
        two_fa = result.scalar_one_or_none()
        
        if two_fa:
            two_fa.status = TwoFAStatus.DISABLED
            
            # Update user record
            from app.models import User
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                user.two_fa_enabled = False
            
            await db.commit()
            return True
        
        return False
    
    async def check_2fa_required(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> bool:
        """Check if user has 2FA enabled."""
        result = await db.execute(
            select(TwoFASecret).where(
                TwoFASecret.user_id == user_id,
                TwoFASecret.status == TwoFAStatus.ENABLED
            )
        )
        return result.scalar_one_or_none() is not None


import uuid
# Create global service instance
two_fa_service = TwoFAService()

