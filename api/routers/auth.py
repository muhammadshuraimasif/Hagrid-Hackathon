from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.models import User, RefreshToken
from api.schemas import LoginRequest, TokenResponse, RefreshRequest, UserOut
from api.security import (
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_token,
    hash_password,
    ensure_utc,
)
from api.audit import record_audit_event
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

# Fixed dummy hash for constant-time comparison when email does not exist
DUMMY_HASH = hash_password("dummy-password-for-timing-mitigation")

@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    request_id = getattr(request.state, "request_id", None)
    now = datetime.now(timezone.utc)

    # Lookup user by email
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalars().first()

    if not user:
        # Prevent timing attacks and email enumeration
        verify_password(payload.password, DUMMY_HASH)
        await record_audit_event(
            actor_type="anonymous",
            action="auth.login_failed",
            entity_type="user",
            entity_id=None,
            request_id=request_id,
            tenant_id=None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Check if account is locked
    if user.locked_until and ensure_utc(user.locked_until) > now:
        await record_audit_event(
            actor_type="user",
            action="auth.login_blocked_locked",
            entity_type="user",
            actor_id=user.id,
            request_id=request_id,
            tenant_id=user.tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is locked due to multiple failed login attempts. Try again in 15 minutes."
        )

    # Verify password
    if not verify_password(payload.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
            await db.commit()
            await record_audit_event(
                actor_type="user",
                action="auth.account_locked",
                entity_type="user",
                actor_id=user.id,
                request_id=request_id,
                tenant_id=user.tenant_id,
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked due to 5 consecutive failed attempts. Try again in 15 minutes."
            )
        
        await db.commit()
        await record_audit_event(
            actor_type="user",
            action="auth.login_failed",
            entity_type="user",
            actor_id=user.id,
            request_id=request_id,
            tenant_id=user.tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Success: reset failed attempts & locked status
    user.failed_attempts = 0
    user.locked_until = None

    # Issue access token & rotating refresh token
    access_token = create_access_token(user.id)
    plain_refresh, refresh_hash, refresh_expires = generate_refresh_token()

    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_expires,
    )
    db.add(db_refresh)
    await db.commit()

    # Record audit entry AFTER transaction commit
    await record_audit_event(
        actor_type="user",
        action="auth.login_success",
        entity_type="user",
        actor_id=user.id,
        request_id=request_id,
        tenant_id=user.tenant_id,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=plain_refresh,
        token_type="bearer",
        expires_in=900,
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    request_id = getattr(request.state, "request_id", None)
    now = datetime.now(timezone.utc)
    incoming_hash = hash_token(payload.refresh_token)

    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == incoming_hash))
    stored_token = result.scalars().first()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Reuse detection: if token was already revoked, someone is replaying a stolen token!
    if stored_token.revoked_at is not None:
        user_id = stored_token.user_id
        # Revoke ALL active refresh tokens for this user immediately
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.commit()

        await record_audit_event(
            actor_type="user",
            action="auth.refresh_token_reuse_detected",
            entity_type="user",
            actor_id=user_id,
            request_id=request_id,
            tenant_id=None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token already rotated or revoked. All active sessions invalidated."
        )

    # Check expiry
    if ensure_utc(stored_token.expires_at) < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )

    # Rotate token: revoke current one and generate a fresh pair
    stored_token.revoked_at = now
    access_token = create_access_token(stored_token.user_id)
    plain_new_refresh, new_refresh_hash, new_refresh_expires = generate_refresh_token()

    new_token_row = RefreshToken(
        user_id=stored_token.user_id,
        token_hash=new_refresh_hash,
        expires_at=new_refresh_expires,
    )
    db.add(new_token_row)
    await db.commit()

    await record_audit_event(
        actor_type="user",
        action="auth.refresh_success",
        entity_type="refresh_token",
        actor_id=stored_token.user_id,
        request_id=request_id,
        tenant_id=None,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=plain_new_refresh,
        token_type="bearer",
        expires_in=900,
    )

@router.post("/logout")
async def logout(request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    request_id = getattr(request.state, "request_id", None)
    now = datetime.now(timezone.utc)

    # Invalidate all active refresh tokens for this user
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()

    await record_audit_event(
        actor_type="user",
        action="auth.logout",
        entity_type="user",
        actor_id=current_user.id,
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )
    return {"status": "ok", "message": "Successfully logged out"}

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
