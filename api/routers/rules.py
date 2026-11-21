"""Rules management and Digital Twin endpoints for administrators."""
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import require_roles
from api.models import User
from api.audit import record_audit_event
from api.rules.service import (
    list_rule_sets,
    get_rule_set,
    create_draft_rule_set,
    update_draft_rule_set,
    publish_rule_set,
)
from api.rules.digital_twin import run_digital_twin
from api.rules.engine import evaluate_case

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


class CreateDraftRequest(BaseModel):
    definition: Dict[str, Any]


class UpdateDraftRequest(BaseModel):
    definition: Dict[str, Any]


class TwinSimulationRequest(BaseModel):
    sample_size: int = Field(default=30, ge=1, le=500)


class PreviewCaseRequest(BaseModel):
    input_data: Dict[str, Any]


def _rule_set_to_dict(rs) -> Dict[str, Any]:
    return {
        "id": rs.id,
        "tenant_id": rs.tenant_id,
        "version": rs.version,
        "status": rs.status,
        "author": rs.author,
        "effective_at": rs.effective_at.isoformat() if rs.effective_at else None,
        "content_hash": rs.content_hash,
        "definition": rs.definition,
        "twin_report": rs.twin_report,
        "created_at": rs.created_at.isoformat() if rs.created_at else None,
        "updated_at": rs.updated_at.isoformat() if rs.updated_at else None,
    }


@router.get("", response_model=List[Dict[str, Any]])
async def list_versions(
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Lists all rule sets for the admin's tenant."""
    rule_sets = await list_rule_sets(db, current_user.tenant_id)
    return [_rule_set_to_dict(rs) for rs in rule_sets]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_draft(
    req: CreateDraftRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new draft rule set for the tenant."""
    author = current_user.email or current_user.id
    rs = await create_draft_rule_set(db, current_user.tenant_id, author, req.definition)

    request_id = getattr(request.state, "request_id", None)
    await record_audit_event(
        tenant_id=current_user.tenant_id,
        actor_type="user",
        actor_id=current_user.id,
        action="RULE_SET_DRAFT_CREATED",
        entity_type="rule_set",
        entity_id=rs.id,
        request_id=request_id,
    )
    return _rule_set_to_dict(rs)


@router.get("/{rule_set_id}")
async def get_version(
    rule_set_id: str,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves a single rule set version by ID."""
    rs = await get_rule_set(db, rule_set_id, current_user.tenant_id)
    return _rule_set_to_dict(rs)


@router.put("/{rule_set_id}")
async def update_draft(
    rule_set_id: str,
    req: UpdateDraftRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Updates a draft rule set. Published rule sets reject updates with 409 Conflict."""
    rs = await update_draft_rule_set(db, rule_set_id, current_user.tenant_id, req.definition)

    request_id = getattr(request.state, "request_id", None)
    await record_audit_event(
        tenant_id=current_user.tenant_id,
        actor_type="user",
        actor_id=current_user.id,
        action="RULE_SET_DRAFT_UPDATED",
        entity_type="rule_set",
        entity_id=rs.id,
        request_id=request_id,
    )
    return _rule_set_to_dict(rs)


@router.post("/{rule_set_id}/twin")
async def run_twin(
    rule_set_id: str,
    req: TwinSimulationRequest = TwinSimulationRequest(),
    request: Request = None,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Runs the Digital Twin simulation on historical decisions for this tenant."""
    rs = await get_rule_set(db, rule_set_id, current_user.tenant_id)
    report = await run_digital_twin(db, rs, sample_size=req.sample_size)
    await db.commit()

    request_id = getattr(request.state, "request_id", None) if request else None
    await record_audit_event(
        tenant_id=current_user.tenant_id,
        actor_type="user",
        actor_id=current_user.id,
        action="DIGITAL_TWIN_SIMULATION_EXECUTED",
        entity_type="rule_set",
        entity_id=rs.id,
        request_id=request_id,
    )
    return report


@router.post("/{rule_set_id}/publish")
async def publish(
    rule_set_id: str,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Publishes a draft rule set. Blocks publishing if Digital Twin has not run."""
    actor_email = current_user.email or current_user.id
    rs = await publish_rule_set(db, rule_set_id, current_user.tenant_id, actor_email)

    request_id = getattr(request.state, "request_id", None)
    await record_audit_event(
        tenant_id=current_user.tenant_id,
        actor_type="user",
        actor_id=current_user.id,
        action="RULE_SET_PUBLISHED",
        entity_type="rule_set",
        entity_id=rs.id,
        request_id=request_id,
    )
    return _rule_set_to_dict(rs)


@router.post("/{rule_set_id}/preview")
async def preview_rule_set(
    rule_set_id: str,
    req: PreviewCaseRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Previews evaluation of arbitrary inputs under a candidate rule set without saving."""
    rs = await get_rule_set(db, rule_set_id, current_user.tenant_id)
    eval_result = evaluate_case(rs.definition, req.input_data)
    return {
        "rule_set_id": rs.id,
        "version": rs.version,
        "evaluation": {
            "route": eval_result.route,
            "p": eval_result.p,
            "expected_cost": eval_result.expected_cost,
            "citizen_reason": eval_result.citizen_reason,
            "trace": eval_result.trace,
        }
    }
