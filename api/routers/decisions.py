"""Decisions and Auditor replay endpoints."""
import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import require_roles
from api.models import User, Decision
from api.audit import record_audit_event
from api.rules.service import replay_decision
from sqlalchemy import select

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


@router.get("/{decision_id}/trace")
async def get_decision_trace_endpoint(
    decision_id: str,
    request: Request,
    current_user: User = Depends(require_roles("auditor", "officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    """Auditor and Officer Trace endpoint returning full telemetry and component breakdown.
    
    Access restricted: Citizens and Helpers receive HTTP 403.
    """
    res = await db.execute(
        select(Decision).where(Decision.id == decision_id, Decision.tenant_id == current_user.tenant_id)
    )
    dec = res.scalars().first()
    if not dec:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Decision not found"})

    request_id = getattr(request.state, "request_id", None)
    await record_audit_event(
        tenant_id=current_user.tenant_id,
        actor_type="user",
        actor_id=current_user.id,
        action="DECISION_TRACE_VIEWED",
        entity_type="decision",
        entity_id=decision_id,
        request_id=request_id,
    )

    return {
        "decision_id": dec.id,
        "case_id": dec.case_id,
        "rule_version": dec.rule_version,
        "rule_hash": dec.rule_hash,
        "route": dec.route,
        "p": dec.p,
        "tau": dec.tau,
        "expected_cost": dec.expected_cost,
        "input_hash": dec.input_hash,
        "decision_token": dec.decision_token,
        "payment_reference": dec.payment_reference,
        "trace": dec.trace,
        "input_snapshot": dec.input_snapshot,
        "created_at": dec.created_at.isoformat() if dec.created_at else None,
    }

