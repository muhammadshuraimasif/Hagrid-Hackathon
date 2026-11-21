from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import User, Person, Consent, ConsentEvent, HelperGrant
from api.audit import record_audit_event
from api.security import ensure_utc

# Scope mappings to personal data fields
SCOPE_FIELD_MAP = {
    "identity": {"cnic", "name", "canonical_name", "father_name", "dob", "field_states"},
    "contact": {"phone", "address"},
    "documents": {"documents"},
    "payment": {"bank_account", "raast_id", "account_title"},
    "status": {"status", "case_status"},
}

def mask_cnic(cnic: str) -> str:
    """Mask CNIC: 42101-1234567-1 -> 42101-*******-1"""
    if not cnic or len(cnic) < 7:
        return "*******"
    parts = cnic.split("-")
    if len(parts) == 3:
        return f"{parts[0]}-*******-{parts[2]}"
    # Fallback masking
    return f"{cnic[:5]}*******{cnic[-1]}"

async def read_person_data(
    db: AsyncSession,
    principal: User,
    person_id: str,
    fields: Optional[List[str]] = None,
    unmask_cnic: bool = False,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    UNIVERSAL CONSENT GATEWAY.
    Every single read of personal data passes through this function.
    Checks consent directly from database at read time (ZERO caching).
    Returns only permitted fields with CNIC masked by default.
    Fails closed with 403 and writes an audit entry on any denial.
    """
    now = datetime.now(timezone.utc)

    # 1. Fetch Person record within principal's tenant
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.tenant_id == principal.tenant_id)
    )
    person = result.scalars().first()
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Person record not found"}
        )

    # 2. Check if principal is the citizen themselves
    is_self = (principal.role == "citizen" and person.user_id == principal.id)

    allowed_scopes = set()
    if is_self:
        # Self-access grants all scopes
        allowed_scopes = {"identity", "contact", "documents", "payment", "status"}
    else:
        # For non-self access (helper, officer, admin, auditor), verify active consent in DB
        query = select(Consent).where(
            Consent.person_id == person_id,
            Consent.tenant_id == principal.tenant_id,
            Consent.is_active == True
        )
        if principal.role == "helper":
            query = query.where(Consent.granted_to_id == principal.id)

        consent_res = await db.execute(query)
        consents = consent_res.scalars().all()

        valid_consents = []
        for c in consents:
            exp = ensure_utc(c.expiry)
            if exp is None or exp > now:
                valid_consents.append(c)

        if not valid_consents:
            # Universal Gate Enforcement: Consent withdrawn or missing
            await record_audit_event(
                actor_type="user",
                action="consent.denied_withdrawn",
                entity_type="person",
                actor_id=principal.id,
                entity_id=person_id,
                request_id=request_id,
                tenant_id=principal.tenant_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "CONSENT_WITHDRAWN", "message": "Consent has been withdrawn or is expired for this citizen"}
            )

        if principal.role == "helper":
            # Must also have active helper grant
            helper_res = await db.execute(
                select(HelperGrant).where(
                    HelperGrant.person_id == person_id,
                    HelperGrant.helper_user_id == principal.id,
                    HelperGrant.tenant_id == principal.tenant_id,
                    HelperGrant.is_active == True
                )
            )
            if not helper_res.scalars().first():
                await record_audit_event(
                    actor_type="user",
                    action="consent.denied_withdrawn",
                    entity_type="person",
                    actor_id=principal.id,
                    entity_id=person_id,
                    request_id=request_id,
                    tenant_id=principal.tenant_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "CONSENT_WITHDRAWN", "message": "Helper grant has been withdrawn or is inactive"}
                )

        for c in valid_consents:
            for s in (c.scope or []):
                allowed_scopes.add(s)

    # 3. Determine permitted fields
    all_permitted_fields = set()
    for sc in allowed_scopes:
        all_permitted_fields.update(SCOPE_FIELD_MAP.get(sc, set()))

    target_fields = set(fields) if fields else all_permitted_fields
    restricted_fields = target_fields.intersection(all_permitted_fields)

    # 4. Extract data
    response_data: Dict[str, Any] = {"id": person.id}
    if "cnic" in restricted_fields:
        raw_cnic = person.cnic_encrypted  # Stored encrypted/reversible format
        response_data["cnic"] = raw_cnic if (unmask_cnic and is_self) else mask_cnic(raw_cnic)
    if "name" in restricted_fields:
        response_data["name"] = person.name
    if "canonical_name" in restricted_fields:
        response_data["canonical_name"] = person.canonical_name
    if "father_name" in restricted_fields:
        response_data["father_name"] = person.father_name
    if "dob" in restricted_fields:
        response_data["dob"] = person.dob
    if "field_states" in restricted_fields:
        response_data["field_states"] = person.field_states or {}

    return response_data
