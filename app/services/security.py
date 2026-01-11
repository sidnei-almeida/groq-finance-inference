"""
Security Service - Encryption and Security Utilities
Handles encryption of sensitive data like API keys.
"""

import os
import logging
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class SecurityService:
    """
    Security service for encrypting/decrypting sensitive data.
    Uses Fernet symmetric encryption with key derived from environment variable.
    """
    
    def __init__(self):
        """Initialize security service with encryption key."""
        # Get encryption key from environment or generate warning
        encryption_key = os.getenv("ENCRYPTION_KEY")
        
        if not encryption_key:
            logger.warning(
                "ENCRYPTION_KEY not found in environment. "
                "Using default key (INSECURE - change in production!). "
                "Set ENCRYPTION_KEY in .env file."
            )
            # Default key for development only - MUST be changed in production
            encryption_key = "default-encryption-key-change-in-production-32-chars!!"
        
        # Derive Fernet key from password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'finsight_salt_2024',  # In production, use random salt per user
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        self.cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt sensitive data.
        
        Args:
            plaintext: Plain text to encrypt
        
        Returns:
            Encrypted string (base64 encoded)
        """
        if not plaintext:
            return ""
        
        try:
            encrypted = self.cipher.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            raise ValueError(f"Failed to encrypt data: {str(e)}")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt sensitive data.
        
        Args:
            ciphertext: Encrypted string
        
        Returns:
            Decrypted plain text
        """
        if not ciphertext:
            return ""
        
        try:
            decrypted = self.cipher.decrypt(ciphertext.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}")
            raise ValueError(f"Failed to decrypt data: {str(e)}")
    
    @staticmethod
    def mask_sensitive_data(data: str, show_chars: int = 4) -> str:
        """
        Mask sensitive data for logging/display.
        
        Args:
            data: Data to mask
            show_chars: Number of characters to show at start/end
        
        Returns:
            Masked string (e.g., "sk_live_1234...5678")
        """
        if not data or len(data) <= show_chars * 2:
            return "***"
        
        return f"{data[:show_chars]}...{data[-show_chars:]}"
    
    @staticmethod
    def validate_api_key_format(api_key: str, exchange: str) -> bool:
        """
        Validate API key format (basic validation).
        
        Args:
            api_key: API key to validate
            exchange: Exchange name
        
        Returns:
            True if format looks valid
        """
        if not api_key or len(api_key) < 10:
            return False
        
        # Basic format validation per exchange
        exchange_formats = {
            "binance": lambda k: len(k) >= 64,  # Binance keys are typically 64 chars
            "alpaca": lambda k: k.startswith("PK") or k.startswith("AK"),  # Alpaca format
            "bybit": lambda k: len(k) >= 32,
        }
        
        validator = exchange_formats.get(exchange.lower())
        if validator:
            return validator(api_key)
        
        # Default: at least 20 characters
        return len(api_key) >= 20
    
    @staticmethod
    def generate_encryption_key() -> str:
        """
        Generate a new encryption key for .env file.
        
        Returns:
            Base64 encoded Fernet key
        """
        key = Fernet.generate_key()
        return key.decode()


def get_security_service() -> SecurityService:
    """Get security service instance (singleton pattern)."""
    global _security_instance
    if '_security_instance' not in globals():
        _security_instance = SecurityService()
    return _security_instance
