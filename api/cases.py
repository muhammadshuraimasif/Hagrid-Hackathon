import uuid
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from api.models import Case, CaseEvent, User
from api.audit import record_audit_event

VALID_TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "CLOSED"},
    "SUBMITTED": {"CHECKING", "CLOSED"},
    "CHECKING": {"NEEDS_INFO", "IN_REVIEW", "APPROVED_ON_HOLD", "WAITING_FOR_SERVICE", "CLOSED"},
    "WAITING_FOR_SERVICE": {"CHECKING", "IN_REVIEW", "CLOSED"},
    "NEEDS_INFO": {"CHECKING", "IN_REVIEW", "CLOSED"},
    "IN_REVIEW": {"APPROVED_ON_HOLD", "REJECTED_BY_OFFICER", "NEEDS_INFO", "CLOSED"},
    "APPROVED_ON_HOLD": {"PAID", "REVERSED", "CLOSED"},
    "PAID": {"CLOSED"},
    "REVERSED": {"IN_REVIEW", "CLOSED"},
    "REJECTED_BY_OFFICER": {"CLOSED"},
    "CLOSED": set(),
}

async def transition_case_status(
    db: AsyncSession,
    case: Case,
    target_status: str,
    actor: User,
    reason: Optional[str] = None,
    client_uuid: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Case:
    """
    Executes a validated state transition in the Case lifecycle.
    Raises 409 Conflict if transition is not permitted.
    Writes a case_event and post-commit audit entry.
    """
    current_status = case.status
    allowed_targets = VALID_TRANSITIONS.get(current_status, set())

    if target_status not in allowed_targets:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ILLEGAL_STATE_TRANSITION",
                "message": f"Cannot transition case from '{current_status}' to '{target_status}'. Allowed transitions: {sorted(list(allowed_targets))}"
            }
        )

    # Apply status change
    case.status = target_status
    
    # Record append-only CaseEvent
    evt_client_uuid = client_uuid or str(uuid.uuid4())
    event_payload = payload or {}
    if reason:
        event_payload["reason"] = reason
    event_payload["from_status"] = current_status
    event_payload["to_status"] = target_status
    event_payload["actor_id"] = actor.id
    event_payload["actor_role"] = actor.role

    case_event = CaseEvent(
        case_id=case.id,
        tenant_id=case.tenant_id,
        client_uuid=evt_client_uuid,
        event_type=f"status_changed.{target_status.lower()}",
        payload=event_payload,
    )
    db.add(case_event)
    await db.commit()
    await db.refresh(case)

    # Post-commit audit record
    await record_audit_event(
        actor_type="user",
        action=f"case.transition.{target_status.lower()}",
        entity_type="case",
        actor_id=actor.id,
        entity_id=case.id,
        acting_as=f"role:{actor.role}",
        request_id=request_id,
        tenant_id=case.tenant_id,
    )

    return case
