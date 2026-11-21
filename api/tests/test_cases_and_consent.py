import os
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from api.database import AsyncSessionLocal
from api.models import AuditLog, Case, Person, Consent, HelperGrant

@pytest.mark.asyncio
async def test_case_lifecycle_and_illegal_transition(client: AsyncClient, citizen_prd_token: str):
    headers = {"Authorization": f"Bearer {citizen_prd_token}"}

    # 1. Create a Case (starts in DRAFT)
    res_create = await client.post(
        "/api/v1/cases",
        json={"name": "Zainab Bibi", "cnic": "42101-1111111-1"},
        headers=headers
    )
    assert res_create.status_code == 201
    case_data = res_create.json()
    case_id = case_data["id"]
    assert case_data["status"] == "DRAFT"

    # 2. Attempt illegal transition directly from DRAFT to PAID -> must return 409 Conflict
    res_illegal = await client.post(
        f"/api/v1/cases/{case_id}/close",
        headers=headers,
        json={"reason": "Attempting illegal direct transition"}
    )
    # Note: DRAFT -> CLOSED is valid in our map for cancellation, but DRAFT -> PAID or other invalid transition
    # Let's test calling assign or escalate when invalid
    from api.cases import transition_case_status
    async with AsyncSessionLocal() as session:
        case_row = (await session.execute(select(Case).where(Case.id == case_id))).scalars().first()
        from api.models import User
        user_row = (await session.execute(select(User).where(User.email == "citizen@prd.test"))).scalars().first()
        with pytest.raises(Exception) as exc_info:
            await transition_case_status(session, case_row, "PAID", user_row)
        assert "Cannot transition case from 'DRAFT' to 'PAID'" in str(exc_info.value)

    # 3. Valid transition: DRAFT -> SUBMITTED
    res_sub = await client.post(f"/api/v1/cases/{case_id}/submit", headers=headers, json={"reason": "Ready"})
    assert res_sub.status_code == 200
    assert res_sub.json()["status"] == "SUBMITTED"

    # 4. Save step data
    res_step = await client.patch(
        f"/api/v1/cases/{case_id}/step",
        headers=headers,
        json={"step_data": {"step": 2, "voice_verified": True}}
    )
    assert res_step.status_code == 200
    assert res_step.json()["step_data"]["step"] == 2

    # 5. Timeline endpoint
    res_time = await client.get(f"/api/v1/cases/{case_id}/timeline", headers=headers)
    assert res_time.status_code == 200
    events = res_time.json()
    assert len(events) >= 3

@pytest.mark.asyncio
async def test_citizen_cannot_read_another_citizens_case(
    client: AsyncClient,
    citizen_prd_token: str,
    officer_prd_token: str
):
    headers_citizen = {"Authorization": f"Bearer {citizen_prd_token}"}
    headers_officer = {"Authorization": f"Bearer {officer_prd_token}"}

    # Citizen A creates case
    res_create = await client.post("/api/v1/cases", json={"name": "Citizen A Case"}, headers=headers_citizen)
    case_id = res_create.json()["id"]

    # Helper or another citizen should not be able to read this case without consent
    from api.tests.conftest import get_token_for
    other_citizen_token = await get_token_for(client, "helper@prd.test")
    res_read = await client.get(f"/api/v1/cases/{case_id}", headers={"Authorization": f"Bearer {other_citizen_token}"})
    assert res_read.status_code == 404

    # Officer in same tenant CAN read it
    res_officer_read = await client.get(f"/api/v1/cases/{case_id}", headers=headers_officer)
    assert res_officer_read.status_code == 200

@pytest.mark.asyncio
async def test_consent_universal_gate_and_withdrawal_revocation(
    client: AsyncClient,
    citizen_prd_token: str,
    helper_prd_token: str
):
    headers_citizen = {"Authorization": f"Bearer {citizen_prd_token}"}
    headers_helper = {"Authorization": f"Bearer {helper_prd_token}"}

    # 1. Citizen creates a person record via case
    res_case = await client.post("/api/v1/cases", json={"name": "Khadija Bibi", "cnic": "42101-9999999-1"}, headers=headers_citizen)
    person_id = res_case.json()["person_id"]

    # Get helper user id
    from api.models import User
    async with AsyncSessionLocal() as session:
        helper = (await session.execute(select(User).where(User.email == "helper@prd.test"))).scalars().first()
        helper_id = helper.id

    # 2. Grant consent to helper
    res_grant = await client.post(
        "/api/v1/consent/grant",
        headers=headers_citizen,
        json={
            "person_id": person_id,
            "granted_to_type": "helper",
            "granted_to_id": helper_id,
            "scope": ["identity", "status"],
            "purpose": "Helper filing assistance"
        }
    )
    assert res_grant.status_code == 201

    # 3. Helper can now read person data through universal gateway (CNIC is masked by default)
    res_read = await client.get(f"/api/v1/consent/person/{person_id}", headers=headers_helper)
    assert res_read.status_code == 200
    person_data = res_read.json()
    assert person_data["name"] == "Khadija Bibi"
    assert "42101-*******-1" in person_data["cnic"]  # Masked!

    # 4. Citizen WITHDRAWS consent in ONE transaction
    res_withdraw = await client.post(
        "/api/v1/consent/withdraw",
        headers=headers_citizen,
        json={"person_id": person_id, "reason": "No longer needed"}
    )
    assert res_withdraw.status_code == 200
    assert res_withdraw.json()["status"] == "ok"

    # 5. Helper's next read MUST IMMEDIATELY FAIL WITH 403 CONSENT_WITHDRAWN
    res_next_read = await client.get(f"/api/v1/consent/person/{person_id}", headers=headers_helper)
    assert res_next_read.status_code == 403
    envelope = res_next_read.json()
    assert envelope["code"] == "CONSENT_WITHDRAWN"

    # 6. Verify audit log recorded the withdrawal and denial
    async with AsyncSessionLocal() as session:
        withdrawn_audit = (await session.execute(
            select(AuditLog).where(AuditLog.action == "consent.withdrawn", AuditLog.entity_id == person_id)
        )).scalars().first()
        assert withdrawn_audit is not None

        denied_audit = (await session.execute(
            select(AuditLog).where(AuditLog.action == "consent.denied_withdrawn", AuditLog.entity_id == person_id)
        )).scalars().first()
        assert denied_audit is not None

@pytest.mark.asyncio
async def test_sync_push_idempotent_deduplication(client: AsyncClient, citizen_prd_token: str):
    headers = {"Authorization": f"Bearer {citizen_prd_token}"}

    # Create case
    res_case = await client.post("/api/v1/cases", json={"name": "Sync Test Case"}, headers=headers)
    case_id = res_case.json()["id"]

    client_uuid = str(uuid.uuid4())
    event_payload = {
        "events": [
            {
                "case_id": case_id,
                "client_uuid": client_uuid,
                "event_type": "offline_step_completed",
                "payload": {"step": 1, "offline": True}
            }
        ]
    }

    # 1. First sync push -> processed: 1
    res1 = await client.post("/api/v1/sync/push", headers=headers, json=event_payload)
    assert res1.status_code == 200
    assert res1.json()["processed"] == 1
    assert res1.json()["ignored_duplicates"] == 0

    # 2. Replay SAME event with same client_uuid -> must be ignored as duplicate (stored once)
    res2 = await client.post("/api/v1/sync/push", headers=headers, json=event_payload)
    assert res2.status_code == 200
    assert res2.json()["processed"] == 0
    assert res2.json()["ignored_duplicates"] == 1

@pytest.mark.asyncio
async def test_resumable_document_upload_and_magic_byte_validation(client: AsyncClient, citizen_prd_token: str):
    headers = {"Authorization": f"Bearer {citizen_prd_token}"}

    # 1. Valid PNG upload with 2 chunks
    png_header = b"\x89PNG\r\n\x1a\n"
    png_chunk_0 = png_header + b"\x00\x00\x00\rIHDR"
    png_chunk_1 = b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    total_size = len(png_chunk_0) + len(png_chunk_1)

    res_init = await client.post(
        "/api/v1/documents/init",
        headers=headers,
        json={
            "filename": "cnic_front.png",
            "mime_type": "image/png",
            "file_size": total_size,
            "chunk_count": 2
        }
    )
    assert res_init.status_code == 201
    doc_id = res_init.json()["id"]

    # Upload chunk 0
    res_c0 = await client.put(f"/api/v1/documents/{doc_id}/chunks/0", headers=headers, content=png_chunk_0)
    assert res_c0.status_code == 200
    assert 0 in res_c0.json()["received_chunks"]

    # Resume upload by sending chunk 1
    res_c1 = await client.put(f"/api/v1/documents/{doc_id}/chunks/1", headers=headers, content=png_chunk_1)
    assert res_c1.status_code == 200
    assert 1 in res_c1.json()["received_chunks"]

    # Complete upload
    res_comp = await client.post(f"/api/v1/documents/{doc_id}/complete", headers=headers)
    assert res_comp.status_code == 200
    doc_info = res_comp.json()
    assert doc_info["is_complete"] is True
    assert doc_info["sha256"] is not None

    # 2. Spoofed document: declares image/jpeg but content is invalid text -> rejected
    fake_jpeg = b"This is not a real JPEG image file at all"
    res_fake_init = await client.post(
        "/api/v1/documents/init",
        headers=headers,
        json={
            "filename": "spoofed.jpg",
            "mime_type": "image/jpeg",
            "file_size": len(fake_jpeg),
            "chunk_count": 1
        }
    )
    fake_doc_id = res_fake_init.json()["id"]
    await client.put(f"/api/v1/documents/{fake_doc_id}/chunks/0", headers=headers, content=fake_jpeg)

    res_fake_comp = await client.post(f"/api/v1/documents/{fake_doc_id}/complete", headers=headers)
    assert res_fake_comp.status_code == 400
    assert res_fake_comp.json()["code"] == "INVALID_FILE_TYPE"

@pytest.mark.asyncio
async def test_audit_chain_still_verifies(client: AsyncClient, auditor_prd_token: str):
    res = await client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {auditor_prd_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["checked"] > 0
    assert data["broken_at_id"] is None
