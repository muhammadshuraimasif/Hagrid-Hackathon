import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import User, Person, Consent, ConsentEvent, HelperGrant
from api.schemas import (
    ConsentGrantRequest,
    ConsentWithdrawRequest,
    ConsentCorrectionRequest,
    ConsentOut,
    ConsentEventOut,
)
from api.dependencies import get_current_user
from api.consent import read_person_data
from api.audit import record_audit_event

router = APIRouter(prefix="/api/v1/consent", tags=["Consent"])

@router.get("", response_model=List[ConsentOut])
async def list_consents(
    person_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Consent).where(Consent.tenant_id == current_user.tenant_id)
    if person_id:
        query = query.where(Consent.person_id == person_id)
    query = query.order_by(Consent.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/grant", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
async def grant_consent(
    payload: ConsentGrantRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    now = datetime.now(timezone.utc)
    receipt_id = f"CSNT-{uuid.uuid4().hex[:8].upper()}"

    expiry = now + timedelta(days=payload.expiry_days) if payload.expiry_days else None

    consent = Consent(
        tenant_id=current_user.tenant_id,
        person_id=payload.person_id,
        granted_to_type=payload.granted_to_type,
        granted_to_id=payload.granted_to_id,
        scope=payload.scope,
        purpose=payload.purpose,
        expiry=expiry,
        receipt_id=receipt_id,
        epoch=1,
        is_active=True,
    )
    db.add(consent)

    if payload.granted_to_type == "helper" and payload.granted_to_id:
        grant = HelperGrant(
            tenant_id=current_user.tenant_id,
            helper_user_id=payload.granted_to_id,
            person_id=payload.person_id,
            receipt_id=receipt_id,
            is_active=True,
        )
        db.add(grant)

    event = ConsentEvent(
        tenant_id=current_user.tenant_id,
        consent_id=consent.id,
        person_id=payload.person_id,
        event_type="granted",
        epoch=1,
        details={"scope": payload.scope, "purpose": payload.purpose, "granted_to": payload.granted_to_type}
    )
    db.add(event)
    await db.commit()
    await db.refresh(consent)

    await record_audit_event(
        actor_type="user",
        action="consent.granted",
        entity_type="consent",
        actor_id=current_user.id,
        entity_id=consent.id,
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )

    return consent

@router.post("/withdraw")
async def withdraw_consent(
    payload: ConsentWithdrawRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    ONE ATOMIC TRANSACTION:
    1. Flips active status on all consents for this person.
    2. Increments consent epoch.
    3. Invalidates all helper grants for this person.
    4. Appends a ConsentEvent.
    5. Commits atomically.
    After commit: logs audit event. Subsequent read immediately returns 403.
    """
    request_id = getattr(request.state, "request_id", None)
    now = datetime.now(timezone.utc)

    # 1. Fetch current consent to determine next epoch
    res = await db.execute(
        select(Consent).where(
            Consent.person_id == payload.person_id,
            Consent.tenant_id == current_user.tenant_id
        )
    )
    consents = res.scalars().all()
    max_epoch = max([c.epoch for c in consents], default=1)
    new_epoch = max_epoch + 1

    # 2. Deactivate consents and increment epoch
    await db.execute(
        update(Consent)
        .where(
            Consent.person_id == payload.person_id,
            Consent.tenant_id == current_user.tenant_id
        )
        .values(is_active=False, epoch=new_epoch, updated_at=now)
    )

    # 3. Invalidate helper grants
    await db.execute(
        update(HelperGrant)
        .where(
            HelperGrant.person_id == payload.person_id,
            HelperGrant.tenant_id == current_user.tenant_id,
            HelperGrant.is_active == True
        )
        .values(is_active=False, revoked_at=now)
    )

    # 4. Record consent event
    event = ConsentEvent(
        tenant_id=current_user.tenant_id,
        consent_id=None,
        person_id=payload.person_id,
        event_type="withdrawn",
        epoch=new_epoch,
        details={"reason": payload.reason, "revoked_by": current_user.id}
    )
    db.add(event)

    # Commit atomic transaction
    await db.commit()

    # 5. Tamper-evident audit entry post-commit
    await record_audit_event(
        actor_type="user",
        action="consent.withdrawn",
        entity_type="person",
        actor_id=current_user.id,
        entity_id=payload.person_id,
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )

    return {
        "status": "ok",
        "message": "Consent successfully withdrawn and helper access revoked",
        "epoch": new_epoch,
    }

@router.get("/person/{person_id}")
async def get_person_data(
    person_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Universal consent gateway read endpoint."""
    request_id = getattr(request.state, "request_id", None)
    return await read_person_data(
        db=db,
        principal=current_user,
        person_id=person_id,
        request_id=request_id
    )

@router.get("/log", response_model=List[ConsentEventOut])
async def get_consent_log(
    person_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(ConsentEvent).where(ConsentEvent.tenant_id == current_user.tenant_id)
    if person_id:
        query = query.where(ConsentEvent.person_id == person_id)
    query = query.order_by(ConsentEvent.id.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/correction")
async def request_correction(
    payload: ConsentCorrectionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    event = ConsentEvent(
        tenant_id=current_user.tenant_id,
        consent_id=None,
        person_id=payload.person_id,
        event_type="correction_requested",
        epoch=1,
        details={
            "field_name": payload.field_name,
            "suggested_value": payload.suggested_value,
            "reason": payload.reason
        }
    )
    db.add(event)
    await db.commit()

    await record_audit_event(
        actor_type="user",
        action="consent.correction_requested",
        entity_type="person",
        actor_id=current_user.id,
        entity_id=payload.person_id,
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )
    return {"status": "ok", "message": "Correction request filed for officer review"}
