from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.models import User, AuditLog
from api.schemas import AuditLogOut, AuditVerifyOut
from api.dependencies import require_roles
from api.audit import verify_audit_chain

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])

@router.get("", response_model=List[AuditLogOut])
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles("auditor")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == current_user.tenant_id)
        .order_by(AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()

@router.get("/verify", response_model=AuditVerifyOut)
async def verify_chain(
    current_user: User = Depends(require_roles("auditor")),
    db: AsyncSession = Depends(get_db)
):
    verification_result = await verify_audit_chain(db, tenant_id=current_user.tenant_id)
    return AuditVerifyOut(**verification_result)
