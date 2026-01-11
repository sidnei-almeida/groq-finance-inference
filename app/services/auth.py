"""
Authentication Service - JWT Token Management
Handles user authentication, token generation, and validation.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import bcrypt
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-minimum-32-characters")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


class AuthService:
    """Authentication service for JWT token management."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt(rounds=10)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.warning(f"Password verification error: {str(e)}")
            return False
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Dictionary containing user data (sub: user_id, email: user_email)
            expires_delta: Optional expiration time delta
        
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and verify a JWT access token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"JWT decode error: {str(e)}")
            return None
    
    @staticmethod
    def get_user_id_from_token(token: str) -> Optional[int]:
        """
        Extract user ID from JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            User ID or None if invalid
        """
        payload = AuthService.decode_access_token(token)
        if payload:
            user_id = payload.get("sub")
            if user_id:
                try:
                    return int(user_id)
                except (ValueError, TypeError):
                    return None
        return None


# Singleton instance
_auth_service = None

def get_auth_service() -> AuthService:
    """Get singleton AuthService instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
