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

import os

def _get_hasher() -> PasswordHasher:
    if os.getenv("TESTING") == "1":
        return PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    return PasswordHasher()

ph = _get_hasher()

_cheap_ph = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)

def hash_password(password: str) -> str:
    """Hash password using Argon2."""
    if os.getenv("TESTING") == "1":
        return _cheap_ph.hash(password)
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

import hmac
import json
import base64

def mint_decision_token(
    case_id: str,
    amount: float,
    tenant_id: str,
    expires_in_seconds: int = 300
) -> str:
    """
    Mints a short-lived HMAC-signed decision capability token for a specific case.
    Required by Raast payment client to authorise holds.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=expires_in_seconds)
    payload = {
        "case_id": case_id,
        "amount": round(float(amount), 2),
        "tenant_id": tenant_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "nonce": secrets.token_hex(8)
    }
    payload_json = json.dumps(payload, sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8")
    signature = hmac.new(
        settings.DECISION_TOKEN_SECRET.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{signature}"

def verify_decision_token(
    token: str,
    expected_case_id: str,
    expected_amount: Optional[float] = None
) -> Dict[str, Any]:
    """
    Verifies the HMAC signature, expiration, and case capability of a decision token.
    Raises ValueError on any violation.
    """
    if not token or "." not in token:
        raise ValueError("Malformed decision token")
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed decision token format")
    payload_b64, signature = parts
    
    expected_sig = hmac.new(
        settings.DECISION_TOKEN_SECRET.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("Invalid decision token signature")

    try:
        payload_json = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)
    except Exception as e:
        raise ValueError(f"Failed to decode decision token payload: {e}")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if payload.get("exp", 0) < now_ts:
        raise ValueError("Decision token has expired")

    if payload.get("case_id") != expected_case_id:
        raise ValueError(f"Decision token was minted for case {payload.get('case_id')}, cannot be used for {expected_case_id}")

    if expected_amount is not None:
        token_amount = float(payload.get("amount", 0.0))
        if abs(token_amount - float(expected_amount)) > 0.01:
            raise ValueError(f"Decision token amount {token_amount} does not match expected amount {expected_amount}")

    return payload

