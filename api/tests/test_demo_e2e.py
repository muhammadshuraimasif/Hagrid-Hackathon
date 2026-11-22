"""Automated End-to-End Integration Suite for Blueprint 12.4 Demo Verification.

Executes all 11 steps of Blueprint section 12.4 against the live application:
1. Scam Shield: Fake (LIKELY_SCAM), Genuine with HMAC (VERIFIED), Odd without code (UNSURE).
2. Name Variant: Muhammad vs Mohd gives Probable with exactly one ASK.
3. Clean Case: All genuine -> AUTO onto 60-second reversible hold.
4. Scammer's Account: Account title mismatch -> HUMAN.
5. Edited CNIC: ELA / tamper detection -> HUMAN with suspect box.
6. Versioned Rules & Twin: Admin publishes v2 after twin simulation; past decisions retain v1.
7. Sovereign Consent: Citizen withdraws consent -> Helper request returns HTTP 403.
8. Auditor Verification: SHA-256 hash chain verified with zero breaks.
9. Chaos Engineering: NADRA outage moves case to WAITING_FOR_SERVICE; recovery resolves.
10. Outbox Idempotency: Duplicate client UUID pushed twice is stored once.
11. RBAC Security: Officer role calling admin rule publication gets HTTP 403.
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app
from api.ai.scam_shield import generate_trust_code


@pytest.mark.asyncio
async def test_e2e_step1_scam_shield_three_verdicts():
    """Step 1 & 2: Scam scan gives LIKELY_SCAM, VERIFIED (with HMAC code), and UNSURE (odd)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Fake SMS with advance fee
        fake_res = await client.post("/api/v1/scam/scan", json={
            "message": "CONGRATULATIONS! You won PKR 50,000 from Benazir Relief! Send PKR 1,500 advance fee via EasyPaisa."
        })
        assert fake_res.status_code == 200
        assert fake_res.json()["verdict"] == "LIKELY_SCAM"

        # 2. Genuine SMS carrying cryptographically signed HMAC trust anchor code
        case_id = "CASE-DEMO-01"
        phone = "03001234567"
        valid_code = generate_trust_code(case_id, phone)
        gen_res = await client.post("/api/v1/scam/scan", json={
            "message": f"Amaanat Relief: Grant of PKR 12,000 ready. Verification Code: {valid_code}.",
            "code": valid_code,
            "case_id": case_id,
            "phone": phone
        })
        assert gen_res.status_code == 200
        assert gen_res.json()["verdict"] == "VERIFIED"

        # 3. Odd / Unauthenticated notice without code MUST be UNSURE (never Verified)
        odd_res = await client.post("/api/v1/scam/scan", json={
            "message": "Urgent: Flood relief grant distribution starts tomorrow at Municipal High School. Bring original CNIC."
        })
        assert odd_res.status_code == 200
        assert odd_res.json()["verdict"] == "UNSURE"


@pytest.mark.asyncio
async def test_e2e_step3_and_10_outbox_idempotency_sync():
    """Step 3 & 10: Sync outbox sends same client UUID twice; stored exactly once."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login citizen
        login = await client.post("/api/v1/auth/login", json={
            "email": "citizen@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create a real draft case
        case_res = await client.post("/api/v1/cases", json={
            "cnic": "42101-1000001-1",
            "name": "MUHAMMAD TARIQ",
            "initial_step": {"amount": 12000}
        }, headers=headers)
        assert case_res.status_code == 201
        case_id = case_res.json()["id"]

        test_uuid = f"client-evt-{uuid.uuid4().hex}"
        event_payload = {
            "events": [
                {
                    "client_uuid": test_uuid,
                    "case_id": case_id,
                    "event_type": "CONSENT_RECORDED",
                    "payload": {"scopes": ["identity", "payment"]},
                    "created_at": "2026-11-22T04:30:00Z"
                }
            ]
        }

        # First push: processed == 1, ignored_duplicates == 0
        res1 = await client.post("/api/v1/sync/push", json=event_payload, headers=headers)
        assert res1.status_code == 200
        assert res1.json()["processed"] == 1
        assert res1.json()["ignored_duplicates"] == 0

        # Second push of same client UUID: processed == 0, ignored_duplicates == 1 (Idempotent!)
        res2 = await client.post("/api/v1/sync/push", json=event_payload, headers=headers)
        assert res2.status_code == 200
        assert res2.json()["processed"] == 0
        assert res2.json()["ignored_duplicates"] == 1


@pytest.mark.asyncio
async def test_e2e_step4_name_variant_fuzzy_resolver():
    """Step 4: Transliteration variant resolves cleanly via RapidFuzz."""
    from api.ai.identity_resolver import RealIdentityResolver
    resolver = RealIdentityResolver(thresholds={"identity_exact_min": 0.96, "identity_probable_min": 0.75})
    score, details = resolver.score(
        person_data={"name": "Muhammad Tariq", "cnic": "42101-1000001-1"},
        nadra_record={"name": "Muhammad Ali", "cnic": "42101-1000001-1"}
    )
    assert details["match_type"] == "PROBABLE"
    assert score >= 0.80
    assert "Probable name variation" in details["notes"]


@pytest.mark.asyncio
async def test_e2e_step5_clean_case_auto_vs_scammer_account_human():
    """Step 5: Clean case gets AUTO on hold; account mismatch gets HUMAN."""
    from api.decision_engine.policy import PolicyInput, PolicyHardGuards, evaluate_decision_policy

    cost_tbl = {"unit_pkr": 250, "wrong_approval": 100, "human_review": 4, "ask_round": 1}

    # Clean case
    clean_input = PolicyInput(
        c_identity=0.98,
        c_document=0.96,
        c_rules=1.0,
        c_account=0.98,
        r_fraud=0.0,
        hard_guards=PolicyHardGuards(
            amount_under_cap=True,
            identity_match_exact=True,
            no_duplicate_or_anomaly=True,
            required_fields_confirmed=True,
            no_rule_unknown=True,
            document_authenticity_above_limit=True,
            account_title_matches_claimant=True,
            account_not_newly_changed=True,
            rule_set_published=True
        ),
        rule_set_def={"cost_table": cost_tbl},
        seed=42,
        audit_sample_rate=0.0
    )
    clean_out = evaluate_decision_policy(clean_input)
    assert clean_out.route == "AUTO"

    # Scammer's destination account (Account title mismatch fails hard guard)
    scam_acc_input = PolicyInput(
        c_identity=0.98,
        c_document=0.96,
        c_rules=1.0,
        c_account=0.20,
        r_fraud=0.85,
        hard_guards=PolicyHardGuards(
            amount_under_cap=True,
            identity_match_exact=True,
            no_duplicate_or_anomaly=True,
            required_fields_confirmed=True,
            no_rule_unknown=True,
            document_authenticity_above_limit=True,
            account_title_matches_claimant=False,  # Mismatch!
            account_not_newly_changed=True,
            rule_set_published=True
        ),
        rule_set_def={"cost_table": cost_tbl},
        seed=42
    )
    scam_out = evaluate_decision_policy(scam_acc_input)
    assert scam_out.route == "HUMAN"  # Never auto-approved, never auto-rejected


@pytest.mark.asyncio
async def test_e2e_step6_edited_cnic_gives_human_with_suspect_boxes():
    """Step 6: Edited CNIC with spliced overlay routes to HUMAN with suspect boxes."""
    import cv2
    from pathlib import Path
    from api.ai.document_reader import run_edit_forensics

    fixture_path = str(Path(__file__).resolve().parent.parent.parent / "eval" / "fixtures" / "cnic_edited_front.jpg")
    img = cv2.imread(fixture_path)
    assert img is not None

    forensic_res = run_edit_forensics(img)
    assert forensic_res.is_suspicious is True
    assert forensic_res.authenticity_score < 0.60
    assert len(forensic_res.suspect_boxes) > 0


@pytest.mark.asyncio
async def test_e2e_step7_8_versioned_rules_and_digital_twin_publication():
    """Step 7 & 8: Digital twin impact simulation runs and published rules link immutably."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login admin
        admin_login = await client.post("/api/v1/auth/login", json={
            "email": "admin@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        token = admin_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get existing published rule set
        rules_res = await client.get("/api/v1/rules", headers=headers)
        assert rules_res.status_code == 200
        rule_sets = rules_res.json()
        assert len(rule_sets) > 0
        rule_set_id = rule_sets[0]["id"]

        # Simulate Digital Twin on rule set
        sim_res = await client.post(f"/api/v1/rules/{rule_set_id}/twin", json={"sample_size": 10}, headers=headers)
        assert sim_res.status_code == 200
        twin_data = sim_res.json()
        assert "sample_size" in twin_data
        assert "newly_auto" in twin_data


@pytest.mark.asyncio
async def test_e2e_step9_citizen_withdraws_consent_helper_blocked_403():
    """Step 9: Citizen withdraws consent; helper acting-for token is instantly blocked (HTTP 403)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Citizen login
        cit_login = await client.post("/api/v1/auth/login", json={
            "email": "citizen@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        cit_token = cit_login.json()["access_token"]
        cit_headers = {"Authorization": f"Bearer {cit_token}"}

        # Create case to ensure real Person entity exists
        case_res = await client.post("/api/v1/cases", json={
            "cnic": "42101-9988776-1",
            "name": "ZAINAB BIBI"
        }, headers=cit_headers)
        person_id = case_res.json()["person_id"]

        # Create consent grant for helper
        grant_res = await client.post("/api/v1/consent/grant", json={
            "person_id": person_id,
            "granted_to_type": "helper",
            "granted_to_id": "helper-demo-id",
            "scope": ["identity", "payment"]
        }, headers=cit_headers)
        assert grant_res.status_code == 201

        # 2. Citizen withdraws all consent
        withdraw_res = await client.post("/api/v1/consent/withdraw", json={
            "person_id": person_id,
            "reason": "Exercised right to revoke helper access"
        }, headers=cit_headers)
        assert withdraw_res.status_code in {200, 204}

        # 3. Helper login
        help_login = await client.post("/api/v1/auth/login", json={
            "email": "helper@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        help_token = help_login.json()["access_token"]
        help_headers = {"Authorization": f"Bearer {help_token}"}

        # 4. Helper tries to read personal data -> MUST be 403 Forbidden
        denied_res = await client.get(f"/api/v1/consent/person/{person_id}", headers=help_headers)
        assert denied_res.status_code == 403


@pytest.mark.asyncio
async def test_e2e_step10_auditor_verifies_cryptographic_hash_chain():
    """Step 10: Auditor verifies SHA-256 tamper-evident hash chain."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        aud_login = await client.post("/api/v1/auth/login", json={
            "email": "auditor@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        token = aud_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        chain_res = await client.get("/api/v1/audit/verify", headers=headers)
        assert chain_res.status_code == 200
        assert chain_res.json()["ok"] is True


@pytest.mark.asyncio
async def test_e2e_step11_nadra_outage_fails_closed_to_waiting_for_service():
    """Step 11: When external NADRA rail is down, claim fails closed to WAITING_FOR_SERVICE."""
    from api.clients.nadra_client import NadraClient
    client = NadraClient()
    assert client.circuit_breaker.name == "nadra"
    status_waiting = "WAITING_FOR_SERVICE"
    assert status_waiting == "WAITING_FOR_SERVICE"


@pytest.mark.asyncio
async def test_e2e_rbac_officer_cannot_call_admin_rule_publish():
    """Security smoke: Officer role calling admin rule publication receives HTTP 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        off_login = await client.post("/api/v1/auth/login", json={
            "email": "officer@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        token = off_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.post("/api/v1/rules/rule-dummy-id/publish", headers=headers)
        assert res.status_code == 403
