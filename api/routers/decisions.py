"""Decisions and Auditor replay endpoints."""
import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import require_roles
from api.models import User
from api.audit import record_audit_event
from api.rules.service import replay_decision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.get("/{decision_id}/replay")
async def replay_decision_endpoint(
    decision_id: str,
    request: Request,
    current_user: User = Depends(require_roles("auditor", "admin")),
    db: AsyncSession = Depends(get_db)
):
    """Auditor Replay: re-evaluates stored input snapshot against original rule set version."""
    replay_result = await replay_decision(db, decision_id, current_user.tenant_id)

    request_id = getattr(request.state, "request_id", None)
    await record_audit_event(
        tenant_id=current_user.tenant_id,
        actor_type="user",
        actor_id=current_user.id,
        action="DECISION_AUDIT_REPLAYED",
        entity_type="decision",
        entity_id=decision_id,
        request_id=request_id,
    )
    return replay_result

