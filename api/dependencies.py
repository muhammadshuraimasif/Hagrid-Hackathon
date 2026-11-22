from datetime import datetime, timezone
from typing import List, Callable, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.models import User, ApiKey
from api.security import decode_access_token, hash_token, ensure_utc
from api.audit import record_audit_event

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    request_id = getattr(request.state, "request_id", None)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )
    
    user_id = payload["sub"]
    # Role and tenant are always read from DB, never trusted from token alone
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found"
        )

    # Check lockout
    now = datetime.now(timezone.utc)
    if user.locked_until and ensure_utc(user.locked_until) > now:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked due to multiple failed login attempts"
        )

    return user

async def get_optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    if not credentials:
        return None
    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        return None

def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory checking that user holds at least one of the allowed roles."""
    async def role_checker(
        request: Request,
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role not in allowed_roles:
            request_id = getattr(request.state, "request_id", None)
            # Record 403 denial in tamper-evident audit log
            await record_audit_event(
                actor_type="user",
                action="rbac.denied",
                entity_type="route",
                actor_id=current_user.id,
                entity_id=request.url.path,
                request_id=request_id,
                tenant_id=current_user.tenant_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires role '{','.join(allowed_roles)}'"
            )
        return current_user
    return role_checker

async def get_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> ApiKey:
    raw_key = request.headers.get("X-API-Key")
    if not raw_key and credentials and credentials.credentials.startswith("amk_"):
        raw_key = credentials.credentials

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required via X-API-Key header"
        )

    key_hash = hash_token(raw_key)
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active == True,
            ApiKey.revoked_at.is_(None)
        )
    )
    api_key = result.scalars().first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key"
        )

    return api_key

def require_scope(*required_scopes: str) -> Callable:
    """Dependency factory checking that API key possesses all required scopes."""
    async def scope_checker(
        request: Request,
        api_key: ApiKey = Depends(get_api_key)
    ) -> ApiKey:
        key_scopes = set(api_key.scopes or [])
        missing = [s for s in required_scopes if s not in key_scopes]
        if missing:
            request_id = getattr(request.state, "request_id", None)
            await record_audit_event(
                actor_type="api_key",
                action="rbac.denied_scope",
                entity_type="route",
                actor_id=api_key.id,
                entity_id=request.url.path,
                request_id=request_id,
                tenant_id=api_key.tenant_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope(s): {', '.join(missing)}"
            )
        return api_key
    return scope_checker
