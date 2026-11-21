import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt
from api.config import settings

def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is offset-aware UTC (important for SQLite portability)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hash password using Argon2."""
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2 hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False

def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except Exception:
        return None

def generate_refresh_token() -> tuple[str, str, datetime]:
    """Generate secure plain refresh token, its sha256 hash, and expiry."""
    plain_token = f"art_{secrets.token_urlsafe(32)}"
    token_hash = hash_token(plain_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return plain_token, token_hash, expires_at

def hash_token(token: str) -> str:
    """SHA-256 hash a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def generate_api_key() -> tuple[str, str, str]:
    """
    Generate an API key with format amk_<random_hex>.
    Returns: (raw_key, key_prefix, key_hash)
    """
    random_part = secrets.token_hex(24)
    raw_key = f"amk_{random_part}"
    key_prefix = raw_key[:12]  # e.g. "amk_1a2b3c4d"
    key_hash = hash_token(raw_key)
    return raw_key, key_prefix, key_hash
