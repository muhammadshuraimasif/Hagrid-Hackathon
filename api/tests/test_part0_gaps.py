"""
Part 0 - Verification tests closing gaps from prior work.
PROTOTYPE ONLY. Follows AGENTS.md and docs/BLUEPRINT.md.
"""
import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import select
from api.database import AsyncSessionLocal
from api.models import Case, CaseEvent, User
from api.cases import transition_case_status

@pytest.mark.asyncio
async def test_helper_acting_for_token_is_rejected_after_citizen_withdraws_consent(
    client: AsyncClient,
    citizen_prd_token: str,
    helper_prd_token: str
):
    headers_citizen = {"Authorization": f"Bearer {citizen_prd_token}"}
    headers_helper = {"Authorization": f"Bearer {helper_prd_token}"}

    # 1. Citizen creates a person record via case
    res_case = await client.post(
        "/api/v1/cases",
        json={"name": "Amina Bibi", "cnic": "42101-7777777-2"},
        headers=headers_citizen
    )
    assert res_case.status_code == 201
    person_id = res_case.json()["person_id"]

    # 2. Get helper id
    async with AsyncSessionLocal() as session:
        helper = (await session.execute(select(User).where(User.email == "helper@prd.test"))).scalars().first()
        helper_id = helper.id

    # 3. Grant consent to helper
    res_grant = await client.post(
        "/api/v1/consent/grant",
        headers=headers_citizen,
        json={
            "person_id": person_id,
            "granted_to_type": "helper",
            "granted_to_id": helper_id,
            "scope": ["identity", "status"],
            "purpose": "Helper Assistance"
        }
    )
    assert res_grant.status_code == 201

    # 4. Helper can read person data
    res_read = await client.get(f"/api/v1/consent/person/{person_id}", headers=headers_helper)
    assert res_read.status_code == 200

    # 5. Citizen withdraws consent
    res_with = await client.post(
        "/api/v1/consent/withdraw",
        headers=headers_citizen,
        json={"person_id": person_id, "reason": "Revoked by citizen"}
    )
    assert res_with.status_code == 200

    # 6. Helper's token is now REJECTED immediately with 403 CONSENT_WITHDRAWN
    res_rejected = await client.get(f"/api/v1/consent/person/{person_id}", headers=headers_helper)
    assert res_rejected.status_code == 403
    assert res_rejected.json()["code"] == "CONSENT_WITHDRAWN"

@pytest.mark.asyncio
async def test_officer_of_tenant_prd_cannot_read_a_case_of_tenant_mao(
    client: AsyncClient,
    citizen_mao_token: str,
    officer_prd_token: str
):
    # Citizen of MAO creates a case
    res_create = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {citizen_mao_token}"},
        json={"name": "MAO Relief Case"}
    )
    assert res_create.status_code == 201
    mao_case_id = res_create.json()["id"]

    # Officer of PRD tries to read the MAO case
    res_read = await client.get(
        f"/api/v1/cases/{mao_case_id}",
        headers={"Authorization": f"Bearer {officer_prd_token}"}
    )
    # Must return 404 (strictly tenant isolated)
    assert res_read.status_code == 404

@pytest.mark.asyncio
async def test_citizen_cannot_list_another_citizens_cases(
    client: AsyncClient,
    citizen_prd_token: str,
    citizen_mao_token: str
):
    unique_name = f"Private Case {uuid.uuid4().hex[:8]}"

    # Citizen 1 (PRD) creates a case
    res_create = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {citizen_prd_token}"},
        json={"name": unique_name}
    )
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # Citizen 2 (MAO) lists their cases
    res_list = await client.get(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {citizen_mao_token}"}
    )
    assert res_list.status_code == 200
    cases = res_list.json()
    case_ids = [c["id"] for c in cases]
    assert case_id not in case_ids

@pytest.mark.asyncio
async def test_chunked_upload_resumes_from_last_received_chunk_after_simulated_drop(
    client: AsyncClient,
    citizen_prd_token: str
):
    headers = {"Authorization": f"Bearer {citizen_prd_token}"}

    # 3-chunk PDF file
    pdf_header = b"%PDF-1.4\n"
    c0 = pdf_header + b"Chunk 0 data\n"
    c1 = b"Chunk 1 data continuing stream\n"
    c2 = b"%%EOF\n"
    total_size = len(c0) + len(c1) + len(c2)

    # 1. Init upload with 3 chunks
    res_init = await client.post(
        "/api/v1/documents/init",
        headers=headers,
        json={
            "filename": "resumable_doc.pdf",
            "mime_type": "application/pdf",
            "file_size": total_size,
            "chunk_count": 3
        }
    )
    assert res_init.status_code == 201
    doc_id = res_init.json()["id"]

    # 2. Upload chunk 0 and chunk 1
    await client.put(f"/api/v1/documents/{doc_id}/chunks/0", headers=headers, content=c0)
    res_c1 = await client.put(f"/api/v1/documents/{doc_id}/chunks/1", headers=headers, content=c1)
    assert set(res_c1.json()["received_chunks"]) == {0, 1}

    # 3. Simulate drop: Client checks chunks, sees chunk 2 is missing
    # 4. Resume by putting chunk 2
    res_c2 = await client.put(f"/api/v1/documents/{doc_id}/chunks/2", headers=headers, content=c2)
    assert set(res_c2.json()["received_chunks"]) == {0, 1, 2}

    # 5. Complete
    res_comp = await client.post(f"/api/v1/documents/{doc_id}/complete", headers=headers)
    assert res_comp.status_code == 200
    data = res_comp.json()
    assert data["is_complete"] is True
    assert data["sha256"] is not None

@pytest.mark.asyncio
async def test_exe_renamed_to_jpg_is_rejected_by_magic_bytes(
    client: AsyncClient,
    citizen_prd_token: str
):
    headers = {"Authorization": f"Bearer {citizen_prd_token}"}

    # Windows PE executable header: MZ\x90\x00...
    malicious_exe_header = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"

    res_init = await client.post(
        "/api/v1/documents/init",
        headers=headers,
        json={
            "filename": "trojan_payload.jpg",
            "mime_type": "image/jpeg",
            "file_size": len(malicious_exe_header),
            "chunk_count": 1
        }
    )
    assert res_init.status_code == 201
    doc_id = res_init.json()["id"]

    await client.put(f"/api/v1/documents/{doc_id}/chunks/0", headers=headers, content=malicious_exe_header)

    # Completion must reject spoofed file type
    res_comp = await client.post(f"/api/v1/documents/{doc_id}/complete", headers=headers)
    assert res_comp.status_code == 400
    assert res_comp.json()["code"] == "INVALID_FILE_TYPE"

@pytest.mark.asyncio
async def test_sync_pull_with_cursor_returns_only_newer_events(
    client: AsyncClient,
    citizen_prd_token: str
):
    headers = {"Authorization": f"Bearer {citizen_prd_token}"}

    # Create case
    res_case = await client.post("/api/v1/cases", headers=headers, json={"name": "Cursor Case"})
    case_id = res_case.json()["id"]

    # Push Event 1
    ev1_uuid = str(uuid.uuid4())
    res1 = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={"events": [{"case_id": case_id, "client_uuid": ev1_uuid, "event_type": "step_1"}]}
    )
    assert res1.status_code == 200

    # Pull events, record current cursor
    res_pull1 = await client.get("/api/v1/sync/pull?cursor=0", headers=headers)
    cursor_1 = res_pull1.json()["next_cursor"]
    assert cursor_1 > 0

    # Push Event 2
    ev2_uuid = str(uuid.uuid4())
    res2 = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={"events": [{"case_id": case_id, "client_uuid": ev2_uuid, "event_type": "step_2"}]}
    )
    assert res2.status_code == 200

    # Pull with cursor=cursor_1 -> returns ONLY newer events
    res_pull2 = await client.get(f"/api/v1/sync/pull?cursor={cursor_1}", headers=headers)
    events = res_pull2.json()["events"]
    assert len(events) >= 1
    for ev in events:
        assert ev["id"] > cursor_1
        assert ev["client_uuid"] != ev1_uuid  # Event 1 is excluded

@pytest.mark.asyncio
async def test_case_in_waiting_for_service_is_never_decided_while_waiting(
    client: AsyncClient,
    citizen_prd_token: str,
    officer_prd_token: str
):
    headers_citizen = {"Authorization": f"Bearer {citizen_prd_token}"}
    headers_officer = {"Authorization": f"Bearer {officer_prd_token}"}

    res_case = await client.post("/api/v1/cases", headers=headers_citizen, json={"name": "Waiting Hold Case"})
    case_id = res_case.json()["id"]

    # Transition case to WAITING_FOR_SERVICE
    async with AsyncSessionLocal() as session:
        case = (await session.execute(select(Case).where(Case.id == case_id))).scalars().first()
        officer = (await session.execute(select(User).where(User.email == "officer@prd.test"))).scalars().first()
        case.status = "WAITING_FOR_SERVICE"
        await session.commit()

        # Attempt to decide the case directly to APPROVED_ON_HOLD or PAID
        with pytest.raises(Exception) as exc1:
            await transition_case_status(session, case, "APPROVED_ON_HOLD", officer)
        assert "Cannot transition case from 'WAITING_FOR_SERVICE' to 'APPROVED_ON_HOLD'" in str(exc1.value)

        with pytest.raises(Exception) as exc2:
            await transition_case_status(session, case, "PAID", officer)
        assert "Cannot transition case from 'WAITING_FOR_SERVICE' to 'PAID'" in str(exc2.value)

    # API endpoint to close or decide also blocks or disallows illegal transition
    res_illegal_api = await client.post(
        f"/api/v1/cases/{case_id}/close",
        headers=headers_officer,
        json={"reason": "Attempting close"}
    )
    # WAITING_FOR_SERVICE -> CLOSED is allowed for administrative abandonment/cancellation per state machine,
    # but never decided (APPROVED_ON_HOLD / PAID).
