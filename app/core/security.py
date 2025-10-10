"""
Security utilities for authentication, authorization, and encryption.
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
import pyotp
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
import base64

from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SecurityManager:
    """Centralized security management for authentication and encryption."""
    
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.jwt_access_token_expire_minutes
        self.refresh_token_expire_days = settings.jwt_refresh_token_expire_days
        
        # Initialize encryption key from secret
        self._encryption_key = self._derive_encryption_key()
        self._cipher_suite = Fernet(self._encryption_key)
        
        # Load or generate RSA keys for JWT signing
        self._load_or_generate_rsa_keys()
    
    def _derive_encryption_key(self) -> bytes:
        """Derive encryption key from secret key."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'prontivus_salt',  # In production, use random salt per tenant
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self.secret_key.encode()))
    
    def _load_or_generate_rsa_keys(self):
        """Load RSA keys from settings or generate new ones."""
        if settings.jwt_private_key and settings.jwt_public_key:
            self.private_key = serialization.load_pem_private_key(
                settings.jwt_private_key.encode(),
                password=None
            )
            self.public_key = serialization.load_pem_public_key(
                settings.jwt_public_key.encode()
            )
        else:
            # Generate new RSA key pair
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            self.public_key = self.private_key.public_key()
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        # Bcrypt has a 72-byte limit, truncate if necessary
        password_bytes = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        return pwd_context.hash(password_bytes)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        # Bcrypt has a 72-byte limit, truncate if necessary
        password_bytes = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        return pwd_context.verify(password_bytes, hashed_password)
    
    def generate_totp_secret(self) -> str:
        """Generate a new TOTP secret for 2FA."""
        return pyotp.random_base32()
    
    def verify_totp(self, secret: str, token: str) -> bool:
        """Verify a TOTP token."""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)
    
    def generate_totp_qr_url(self, secret: str, user_email: str, app_name: str = "Prontivus") -> str:
        """Generate QR code URL for TOTP setup."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=user_email,
            issuer_name=app_name
        )
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        
        if self.algorithm == "RS256":
            return jwt.encode(to_encode, self.private_key, algorithm=self.algorithm)
        else:
            return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        
        if self.algorithm == "RS256":
            return jwt.encode(to_encode, self.private_key, algorithm=self.algorithm)
        else:
            return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        try:
            if self.algorithm == "RS256":
                payload = jwt.decode(token, self.public_key, algorithms=[self.algorithm])
            else:
                payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Verify token type
            if payload.get("type") != token_type:
                return None
            
            return payload
        except JWTError:
            return None
    
    def encrypt_field(self, data: str) -> str:
        """Encrypt sensitive field data."""
        if not data:
            return data
        encrypted_data = self._cipher_suite.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    
    def decrypt_field(self, encrypted_data: str) -> str:
        """Decrypt sensitive field data."""
        if not encrypted_data:
            return encrypted_data
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._cipher_suite.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception:
            return encrypted_data  # Return as-is if decryption fails
    
    def generate_idempotency_key(self) -> str:
        """Generate a unique idempotency key."""
        return secrets.token_urlsafe(32)
    
    def hash_idempotency_key(self, key: str) -> str:
        """Hash an idempotency key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def sign_license(self, license_data: Dict[str, Any]) -> str:
        """Sign license data with RSA private key."""
        if not settings.rsa_license_private:
            raise ValueError("License private key not configured")
        
        # Create license payload string
        payload = f"{license_data['license_id']}:{license_data['tenant_id']}:{license_data['plan']}:{license_data['end_at']}"
        
        # Sign with RSA private key
        signature = self.private_key.sign(
            payload.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.urlsafe_b64encode(signature).decode()
    
    def verify_license_signature(self, license_data: Dict[str, Any], signature: str) -> bool:
        """Verify license signature with RSA public key."""
        try:
            # Create license payload string
            payload = f"{license_data['license_id']}:{license_data['tenant_id']}:{license_data['plan']}:{license_data['end_at']}"
            
            # Decode signature
            signature_bytes = base64.urlsafe_b64decode(signature.encode())
            
            # Verify signature
            self.public_key.verify(
                signature_bytes,
                payload.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False


# Global security manager instance
security = SecurityManager()
