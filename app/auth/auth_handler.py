"""
OpenHT - Authentication Handler
JWT token validation and user session management with Supabase Auth
"""

import os
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional

try:
    import jwt

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel

# ==================== Models ====================


class UserToken(BaseModel):
    """User token data"""

    user_id: str
    email: str
    name: Optional[str] = None
    exp: Optional[datetime] = None


class AuthResponse(BaseModel):
    """Authentication response"""

    access_token: str
    token_type: str = "bearer"
    user: dict


# ==================== Auth Handler ====================


class AuthHandler:
    """JWT Authentication handler"""

    security = HTTPBearer(auto_error=False)

    def __init__(self):
        self.secret = os.getenv("JWT_SECRET", "default-secret-change-in-production")
        self.algorithm = "HS256"
        self.expire_hours = 24 * 7  # 1 week

    def create_token(self, user_id: str, email: str, name: str = None) -> str:
        """Create JWT token"""
        if not JWT_AVAILABLE:
            raise HTTPException(status_code=500, detail="JWT library not available")

        expire = datetime.utcnow() + timedelta(hours=self.expire_hours)

        payload = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "exp": expire,
            "iat": datetime.utcnow(),
        }

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Optional[UserToken]:
        """Decode and validate JWT token"""
        if not JWT_AVAILABLE:
            return None

        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return UserToken(
                user_id=payload.get("user_id"),
                email=payload.get("email"),
                name=payload.get("name"),
                exp=datetime.fromtimestamp(payload.get("exp", 0)),
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def verify_supabase_token(self, token: str) -> Optional[dict]:
        """Verify Supabase JWT token"""
        if not JWT_AVAILABLE:
            return None

        try:
            # Supabase uses its own JWT secret (from SUPABASE_JWT_SECRET env)
            supabase_secret = os.getenv("SUPABASE_JWT_SECRET", self.secret)

            payload = jwt.decode(
                token, supabase_secret, algorithms=["HS256"], audience="authenticated"
            )
            return payload
        except Exception as e:
            logger.debug(f"Supabase token verification failed: {e}")
            # Try with our own secret as fallback
            return self.decode_token(token)


# Singleton instance
auth_handler = AuthHandler()


# ==================== Dependencies ====================


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(AuthHandler.security),
) -> Optional[UserToken]:
    """
    FastAPI dependency to get current user from JWT token.
    Returns None if no valid token (for optional auth).
    """
    # Check Authorization header
    if credentials and credentials.credentials:
        user = auth_handler.decode_token(credentials.credentials)
        if user:
            return user

    # Check cookie as fallback
    token = request.cookies.get("access_token")
    if token:
        return auth_handler.decode_token(token)

    return None


async def require_auth(
    user: Optional[UserToken] = Depends(get_current_user),
) -> UserToken:
    """
    FastAPI dependency that requires authentication.
    Raises HTTPException if not authenticated.
    """
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Giriş yapmanız gerekiyor",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ==================== Utility Functions ====================


def hash_password(password: str) -> str:
    """Hash password using bcrypt (if available)"""
    try:
        import bcrypt

        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        # Fallback: simple hash (NOT SECURE - only for development)
        import hashlib

        return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        import bcrypt

        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ImportError:
        # Fallback
        import hashlib

        return hashlib.sha256(password.encode()).hexdigest() == hashed
