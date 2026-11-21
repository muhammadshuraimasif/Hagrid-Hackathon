from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.models import User, ApiKey
from api.schemas import UserOut, ApiKeyCreate, ApiKeyOut, ApiKeyCreatedOut
from api.dependencies import require_roles
from api.security import generate_api_key
from api.audit import record_audit_event

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

@router.get("/users", response_model=List[UserOut])
async def list_tenant_users(
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.tenant_id == current_user.tenant_id).order_by(User.created_at.asc())
    )
    return result.scalars().all()

@router.post("/api-keys", response_model=ApiKeyCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    raw_key, key_prefix, key_hash = generate_api_key()

    new_key = ApiKey(
        tenant_id=current_user.tenant_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=payload.name,
        scopes=payload.scopes,
        is_active=True,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    await record_audit_event(
        actor_type="user",
        action="api_key.created",
        entity_type="api_key",
        actor_id=current_user.id,
        entity_id=new_key.id,
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )

    return ApiKeyCreatedOut(
        id=new_key.id,
        tenant_id=new_key.tenant_id,
        name=new_key.name,
        key_prefix=new_key.key_prefix,
        scopes=new_key.scopes,
        is_active=new_key.is_active,
        created_at=new_key.created_at,
        api_key=raw_key,
    )

@router.get("/api-keys", response_model=List[ApiKeyOut])
async def list_api_keys(
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.tenant_id == current_user.tenant_id).order_by(ApiKey.created_at.desc())
    )
    return result.scalars().all()

@router.delete("/api-keys/{key_id}", status_code=status.HTTP_200_OK)
async def revoke_api_key(
    key_id: str,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == current_user.tenant_id)
    )
    api_key = result.scalars().first()

    if not api_key:
        # Cross-tenant requests or nonexistent keys return 404
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    api_key.is_active = False
    api_key.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    await record_audit_event(
        actor_type="user",
        action="api_key.revoked",
        entity_type="api_key",
        actor_id=current_user.id,
        entity_id=api_key.id,
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )

    return {"status": "ok", "message": "API key revoked"}

from pydantic import BaseModel
from typing import Optional, Dict, Any
from mocks.chaos import chaos_controller

class AdminChaosRequest(BaseModel):
    service: Optional[str] = "nadra"  # "nadra", "raast", "sms"
    latency_ms: Optional[int] = None
    error_500: Optional[bool] = None
    timeout: Optional[bool] = None
    stale_data: Optional[bool] = None
    reset: Optional[bool] = False

@router.get("/chaos")
async def get_mock_chaos_status(
    current_user: User = Depends(require_roles("admin"))
):
    """Admin-only view of mock rails chaos injection settings."""
    return {
        "prototype": True,
        "chaos": chaos_controller.get_state()
    }

@router.post("/chaos")
async def update_mock_chaos(
    payload: AdminChaosRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin"))
):
    """Admin-only audited failure injection controller."""
    request_id = getattr(request.state, "request_id", None)
    
    if payload.reset:
        chaos_controller.reset()
        await record_audit_event(
            actor_type="user",
            action="admin.chaos_reset",
            entity_type="system",
            actor_id=current_user.id,
            request_id=request_id,
            tenant_id=current_user.tenant_id,
        )
        return {"prototype": True, "status": "reset", "chaos": chaos_controller.get_state()}

    service_name = payload.service or "nadra"
    updated = chaos_controller.update_service_chaos(
        service=service_name,
        latency_ms=payload.latency_ms,
        error_500=payload.error_500,
        timeout=payload.timeout,
        stale_data=payload.stale_data
    )

    await record_audit_event(
        actor_type="user",
        action="admin.chaos_update",
        entity_type="system",
        actor_id=current_user.id,
        entity_id=service_name,
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )

    return {"prototype": True, "service": service_name, "updated": updated}

