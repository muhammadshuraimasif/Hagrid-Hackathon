import uuid
import hashlib
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import User, Case, CaseEvent, Person, HelperGrant
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
