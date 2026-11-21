import uuid
import hashlib
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import User, Case, CaseEvent, Person, HelperGrant, Decision
from api.schemas import (
    CaseCreate,
    CaseOut,
    CaseStepSave,
    CaseTransition,
    CaseAssign,
    CaseEventOut,
)
from api.dependencies import get_current_user, require_roles
from api.cases import transition_case_status
from api.audit import record_audit_event
from api.rules.service import decide_case
from api.decision_engine.service import (
    evaluate_case_full,
    reverse_held_payment,
    officer_review_decision,
    get_review_queue_sorted,
)

router = APIRouter(prefix="/api/v1/cases", tags=["Cases"])

async def can_access_case(case: Case, user: User, db: AsyncSession) -> bool:
    """Enforces tenant isolation and role-based case visibility."""
    if case.tenant_id != user.tenant_id:
        return False
    if user.role in ["officer", "admin", "auditor"]:
        return True
    if user.role == "citizen":
        return case.creator_user_id == user.id
    if user.role == "helper":
        # Check active helper grant for this person
        grant_res = await db.execute(
            select(HelperGrant).where(
                HelperGrant.helper_user_id == user.id,
                HelperGrant.person_id == case.person_id,
                HelperGrant.tenant_id == user.tenant_id,
                HelperGrant.is_active == True
            )
        )
        return grant_res.scalars().first() is not None
    return False

@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    request: Request,
    current_user: User = Depends(require_roles("citizen", "helper")),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)

    person_id = payload.person_id
    if not person_id:
        # Create person record for this citizen
        raw_cnic = payload.cnic or "42101-1234567-1"
        cnic_hash = hashlib.sha256(raw_cnic.encode("utf-8")).hexdigest()
        name = payload.name or "Citizen Applicant"
        person = Person(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id if current_user.role == "citizen" else None,
            cnic_encrypted=raw_cnic,
            cnic_hash=cnic_hash,
            name=name,
            canonical_name=name.strip().upper(),
            father_name=payload.father_name or "Father Name",
            dob=payload.dob or "1970-01-01",
            field_states={"cnic": "confirmed", "name": "confirmed"}
        )
        db.add(person)
        await db.flush()
        person_id = person.id

        if current_user.role == "helper":
            # Auto-link active helper grant for this created case
            grant = HelperGrant(
                tenant_id=current_user.tenant_id,
                helper_user_id=current_user.id,
                person_id=person_id,
                receipt_id=f"RCPT-{uuid.uuid4().hex[:8].upper()}",
                is_active=True
            )
            db.add(grant)
            await db.flush()

    new_case = Case(
        tenant_id=current_user.tenant_id,
        person_id=person_id,
        creator_user_id=current_user.id,
        status="DRAFT",
        step_data=payload.initial_step or {"step": 1, "channel": "web"}
    )
    db.add(new_case)
    await db.flush()

    # Create initial case event
    event = CaseEvent(
        case_id=new_case.id,
        tenant_id=new_case.tenant_id,
        client_uuid=str(uuid.uuid4()),
        event_type="case.created",
        payload={"creator_role": current_user.role, "creator_id": current_user.id}
    )
    db.add(event)
    await db.commit()
    await db.refresh(new_case)

    await record_audit_event(
        actor_type="user",
        action="case.created",
        entity_type="case",
        actor_id=current_user.id,
        entity_id=new_case.id,
        request_id=request_id,
        tenant_id=new_case.tenant_id,
    )

    return new_case

@router.get("", response_model=List[CaseOut])
async def list_cases(
    current_user: User = Depends(require_roles("citizen", "helper", "officer")),
    db: AsyncSession = Depends(get_db)
):
    query = select(Case).where(Case.tenant_id == current_user.tenant_id)
    if current_user.role == "citizen":
        query = query.where(Case.creator_user_id == current_user.id)
    elif current_user.role == "helper":
        # Consented families only
        grant_res = await db.execute(
            select(HelperGrant.person_id).where(
                HelperGrant.helper_user_id == current_user.id,
                HelperGrant.tenant_id == current_user.tenant_id,
                HelperGrant.is_active == True
            )
        )
        allowed_person_ids = grant_res.scalars().all()
        query = query.where(Case.person_id.in_(allowed_person_ids))

    query = query.order_by(Case.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/review-queue")
async def get_case_review_queue(
    current_user: User = Depends(require_roles("officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    """Returns officer review queue sorted by risk/vulnerability priority."""
    return await get_review_queue_sorted(db, current_user.tenant_id)

@router.get("/{case_id}", response_model=CaseOut)
async def get_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case or not await can_access_case(case, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Case not found"}
        )
    return case

@router.patch("/{case_id}/step", response_model=CaseOut)
async def save_step(
    case_id: str,
    payload: CaseStepSave,
    request: Request,
    current_user: User = Depends(require_roles("citizen", "helper")),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case or not await can_access_case(case, current_user, db):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Case not found"})

    current_data = dict(case.step_data or {})
    current_data.update(payload.step_data)
    case.step_data = current_data

    event = CaseEvent(
        case_id=case.id,
        tenant_id=case.tenant_id,
        client_uuid=payload.client_uuid or str(uuid.uuid4()),
        event_type="case.step_saved",
        payload=payload.step_data,
    )
    db.add(event)
    await db.commit()
    await db.refresh(case)

    await record_audit_event(
        actor_type="user",
        action="case.step_saved",
        entity_type="case",
        actor_id=current_user.id,
        entity_id=case.id,
        request_id=request_id,
        tenant_id=case.tenant_id,
    )
    return case

@router.post("/{case_id}/submit", response_model=CaseOut)
async def submit_case(
    case_id: str,
    payload: CaseTransition,
    request: Request,
    current_user: User = Depends(require_roles("citizen", "helper")),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case or not await can_access_case(case, current_user, db):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Case not found"})

    return await transition_case_status(
        db, case, "SUBMITTED", current_user,
        reason=payload.reason or "Citizen submission",
        client_uuid=payload.client_uuid,
        request_id=request_id
    )

@router.post("/{case_id}/assign", response_model=CaseOut)
async def assign_officer(
    case_id: str,
    payload: CaseAssign,
    request: Request,
    current_user: User = Depends(require_roles("officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    result = await db.execute(select(Case).where(Case.id == case_id, Case.tenant_id == current_user.tenant_id))
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Case not found"})

    case.assigned_officer_id = payload.officer_id
    event = CaseEvent(
        case_id=case.id,
        tenant_id=case.tenant_id,
        client_uuid=str(uuid.uuid4()),
        event_type="case.assigned",
        payload={"assigned_officer_id": payload.officer_id, "by": current_user.id}
    )
    db.add(event)
    await db.commit()
    await db.refresh(case)

    await record_audit_event(
        actor_type="user",
        action="case.assigned",
        entity_type="case",
        actor_id=current_user.id,
        entity_id=case.id,
        request_id=request_id,
        tenant_id=case.tenant_id,
    )
    return case

@router.post("/{case_id}/escalate", response_model=CaseOut)
async def escalate_case(
    case_id: str,
    payload: CaseTransition,
    request: Request,
    current_user: User = Depends(require_roles("officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case or not await can_access_case(case, current_user, db):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Case not found"})

    return await transition_case_status(
        db, case, "IN_REVIEW", current_user,
        reason=payload.reason or "Escalated to human officer",
        client_uuid=payload.client_uuid,
        request_id=request_id
    )

@router.post("/{case_id}/close", response_model=CaseOut)
async def close_case(
    case_id: str,
    payload: CaseTransition,
    request: Request,
    current_user: User = Depends(require_roles("officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    result = await db.execute(select(Case).where(Case.id == case_id, Case.tenant_id == current_user.tenant_id))
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Case not found"})

    return await transition_case_status(
        db, case, "CLOSED", current_user,
        reason=payload.reason or "Closed by officer",
        client_uuid=payload.client_uuid,
        request_id=request_id
    )

@router.get("/{case_id}/timeline", response_model=List[CaseEventOut])
async def get_case_timeline(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case or not await can_access_case(case, current_user, db):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Case not found"})

    events_res = await db.execute(
        select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.id.asc())
    )
    return events_res.scalars().all()


@router.post("/{case_id}/decide")
async def decide_case_endpoint(
    case_id: str,
    request: Request,
    current_user: User = Depends(require_roles("officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    """Evaluates case inputs against the active published rule set and assigns exit route."""
    request_id = getattr(request.state, "request_id", None)
    result = await db.execute(select(Case).where(Case.id == case_id, Case.tenant_id == current_user.tenant_id))
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Case not found"})

    raw_input = dict(case.step_data or {})
    decision = await decide_case(db, case.tenant_id, case.id, raw_input)

    # Determine target status from decision route
    if decision.route == "AUTO":
        target_status = "APPROVED_ON_HOLD"
    elif decision.route == "ASK":
        target_status = "NEEDS_INFO"
    else:
        target_status = "IN_REVIEW"

    # Transition case through CHECKING if currently SUBMITTED
    if case.status == "SUBMITTED":
        await transition_case_status(
            db, case, "CHECKING", current_user,
            reason="System rule evaluation initiated",
            client_uuid=str(uuid.uuid4()),
            request_id=request_id
        )

    if case.status == "CHECKING":
        await transition_case_status(
            db, case, target_status, current_user,
            reason=f"Decided route {decision.route}: {decision.citizen_reason.get('en')}",
            client_uuid=str(uuid.uuid4()),
            request_id=request_id
        )

    return {
        "decision_id": decision.id,
        "case_id": case.id,
        "rule_version": decision.rule_version,
        "rule_hash": decision.rule_hash,
        "route": decision.route,
        "p": decision.p,
        "expected_cost": decision.expected_cost,
        "citizen_reason": decision.citizen_reason,
        "trace": decision.trace,
        "case_status": case.status,
    }


@router.post("/{case_id}/evaluate")
async def evaluate_case_endpoint(
    case_id: str,
    request: Request,
    current_user: User = Depends(require_roles("helper", "officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    """Executes full decision engine pipeline (Module 5), persisting decision and updating status."""
    request_id = getattr(request.state, "request_id", None)
    res = await db.execute(select(Case).where(Case.id == case_id))
    case = res.scalars().first()
    if not case or not await can_access_case(case, current_user, db):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Case not found"})

    try:
        decision = await evaluate_case_full(db, case.id, current_user, request_id=request_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(ve)})

    return {
        "decision_id": decision.id,
        "case_id": case.id,
        "rule_version": decision.rule_version,
        "rule_hash": decision.rule_hash,
        "route": decision.route,
        "p": decision.p,
        "tau": decision.tau,
        "expected_cost": decision.expected_cost,
        "decision_token": decision.decision_token,
        "payment_reference": decision.payment_reference,
        "citizen_reason": decision.citizen_reason,
        "trace": decision.trace,
        "case_status": case.status,
    }


@router.get("/{case_id}/explanation")
async def get_case_explanation(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Bilingual explanation for citizen/helper: actionable next step for ASK, reassuring for HUMAN."""
    res = await db.execute(select(Case).where(Case.id == case_id))
    case = res.scalars().first()
    if not case or not await can_access_case(case, current_user, db):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Case not found"})

    dec_res = await db.execute(
        select(Decision).where(Decision.case_id == case.id).order_by(Decision.created_at.desc())
    )
    decision = dec_res.scalars().first()
    if not decision:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "No decision found for case"})

    reasons = dict(decision.citizen_reason or {})
    if decision.route == "HUMAN":
        reasons["reassurance"] = {
            "en": "Your application has been received safely and is being verified by a human officer. This is not a rejection.",
            "ur": "آپ کی درخواست موصول ہو چکی ہے اور افسر اس کا جائزہ لے رہے ہیں۔ یہ ہرگز مسترد نہیں کی گئی۔"
        }

    ask_target = decision.trace.get("ask_target") if decision.trace else None

    return {
        "case_id": case.id,
        "route": decision.route,
        "status": case.status,
        "citizen_reason": reasons,
        "actionable_next_step": ask_target if decision.route == "ASK" else None,
    }


@router.post("/{case_id}/reverse-hold")
async def reverse_case_hold_endpoint(
    case_id: str,
    payload: Optional[Dict[str, Any]] = None,
    request: Request = None,
    current_user: User = Depends(require_roles("officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    """Officer reversal of a held payment before the hold window expires."""
    request_id = getattr(request.state, "request_id", None) if request else None
    reason = (payload or {}).get("reason", "Payment hold reversed by officer review")
    try:
        case, rev_res = await reverse_held_payment(db, case_id, current_user, reason=reason, request_id=request_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(ve)})

    return {
        "case_id": case.id,
        "status": case.status,
        "reversal_details": rev_res,
        "message": "Payment hold successfully reversed"
    }


@router.post("/{case_id}/officer-approve")
async def officer_approve_case(
    case_id: str,
    payload: Optional[Dict[str, Any]] = None,
    request: Request = None,
    current_user: User = Depends(require_roles("officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    """Human officer approval of a case."""
    request_id = getattr(request.state, "request_id", None) if request else None
    note = (payload or {}).get("note", "Approved by human officer")
    try:
        case = await officer_review_decision(db, case_id, current_user, "approve", note, request_id=request_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(ve)})
    return {"case_id": case.id, "status": case.status, "message": "Case approved by officer"}


@router.post("/{case_id}/officer-reject")
async def officer_reject_case(
    case_id: str,
    payload: Optional[Dict[str, Any]] = None,
    request: Request = None,
    current_user: User = Depends(require_roles("officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    """Human officer rejection of a case (Human Supremacy: only humans reject)."""
    request_id = getattr(request.state, "request_id", None) if request else None
    note = (payload or {}).get("note", "Rejected by human officer")
    try:
        case = await officer_review_decision(db, case_id, current_user, "reject", note, request_id=request_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(ve)})
    return {"case_id": case.id, "status": case.status, "message": "Case rejected by officer"}


@router.post("/{case_id}/officer-request-info")
async def officer_request_info_case(
    case_id: str,
    payload: Optional[Dict[str, Any]] = None,
    request: Request = None,
    current_user: User = Depends(require_roles("officer", "admin")),
    db: AsyncSession = Depends(get_db)
):
    """Human officer requests additional information from applicant."""
    request_id = getattr(request.state, "request_id", None) if request else None
    note = (payload or {}).get("note", "Officer requested additional documents/clarification")
    try:
        case = await officer_review_decision(db, case_id, current_user, "request_info", note, request_id=request_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(ve)})
    return {"case_id": case.id, "status": case.status, "message": "Additional info requested by officer"}

