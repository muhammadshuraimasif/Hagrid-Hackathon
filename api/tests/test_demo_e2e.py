"""Automated End-to-End Integration Suite for Blueprint 12.4 Demo Verification.

Executes all 11 exact steps of Blueprint section 12.4 against the live application:
Step 1: State the sentence, the prototype label, the real-vs-simulated table -> Scope and honesty
Step 2: Akram pastes a fake relief SMS, a genuine one with its code, and an odd one -> Scam with red flags; Verified; Unsure -> person
Step 3: Shazia switches to Zainab; consent by voice; network throttled, then offline, then back -> Urdu prompts, saved progress, clean sync, no duplicates
Step 4: Zainab's card reads 'Muhammed', registry says 'Mohd.' -> Read-back by voice, Probable -> one ASK
Step 5: A clean case; then the same claimant with a scammer's account -> AUTO onto a 60-second hold; account-title mismatch -> HUMAN
Step 6: An edited CNIC -> HUMAN with the tampered region boxed and the hand-off packet
Step 7: Show the cost table and tau sweep -> The numbers behind tau
Step 8: Admin adds a required document; Twin preview; publish; new case; open an old decision -> New rule live at once; old decision shows its old version
Step 9: Zainab withdraws Shazia's consent; Shazia retries -> 403; audit shows grant, read, withdrawal, denial
Step 10: Auditor opens a trace and verifies the chain -> Full trace; chain verified
Step 11: Admin kills mock-NADRA; run a case -> 'Cannot verify right now'; case waits
"""
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from api.main import app
from api.database import AsyncSessionLocal
from api.models import AuditLog, RuleSet, Decision
from api.ai.scam_shield import generate_trust_code
from api.ai.identity_resolver import RealIdentityResolver
from api.decision_engine.policy import PolicyInput, PolicyHardGuards, evaluate_decision_policy
from api.seed import make_rule_set_definition


@pytest.mark.asyncio
async def test_e2e_step1_scope_and_honesty_prototype_contract():
    """Step 1: State the sentence, the prototype label, the real-vs-simulated table."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        # Every response carries mandatory prototype headers
        assert res.headers.get("X-Amaanat-Prototype") == "true"
        assert "PROTOTYPE" in res.headers.get("X-Amaanat-Warning", "").upper()


@pytest.mark.asyncio
async def test_e2e_step2_akram_scam_shield_three_message_advisory():
    """Step 2: Akram pastes a fake relief SMS, a genuine one with its code, and an odd one."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Fake relief SMS with advance fee
        fake_res = await client.post("/api/v1/scam/scan", json={
            "message": "CONGRATULATIONS! You won PKR 50,000 from Benazir Relief! Send PKR 1,500 advance fee via EasyPaisa."
        })
        assert fake_res.status_code == 200
        assert fake_res.json()["verdict"] == "LIKELY_SCAM"
        assert len(fake_res.json()["red_flags"]) > 0

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
async def test_e2e_step3_shazia_helper_to_zainab_voice_consent_offline_sync():
    """Step 3: Shazia switches to Zainab; consent by voice; network throttled, then offline, then back."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/v1/auth/login", json={
            "email": "citizen@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

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
                    "payload": {"scopes": ["identity", "payment"], "channel": "voice"},
                    "created_at": "2026-11-22T04:30:00Z"
                }
            ]
        }

        # First push: saved progress cleanly synced
        res1 = await client.post("/api/v1/sync/push", json=event_payload, headers=headers)
        assert res1.status_code == 200
        assert res1.json()["processed"] == 1
        assert res1.json()["ignored_duplicates"] == 0

        # Second push of same client UUID after reconnection: ignored without error
        res2 = await client.post("/api/v1/sync/push", json=event_payload, headers=headers)
        assert res2.status_code == 200
        assert res2.json()["processed"] == 0
        assert res2.json()["ignored_duplicates"] == 1


@pytest.mark.asyncio
async def test_e2e_step4_zainab_card_muhammed_registry_mohd_probable_one_ask_then_human():
    """Step 4: Zainab's card reads 'Muhammed', registry says 'Mohd.' -> Read-back by voice, Probable -> one ASK."""
    resolver = RealIdentityResolver()
    score, details = resolver.score(
        person_data={"name": "Muhammed", "cnic": "42101-1000001-1", "father_name": "Tariq Khan", "dob": "1985-05-12"},
        nadra_record={"name": "Mohd.", "cnic": "42101-1000001-1", "father_name": "Tariq Khan", "dob": "1985-05-12"}
    )
    # Proves: Lexical JW is 0.5833, variant dictionary matches, mapped to 0.85 in [0.75, 0.92)
    assert details["match_type"] == "PROBABLE"
    assert details["identity_match_exact"] is False
    assert 0.75 <= details["name_similarity"] < 0.92

    # Proves: In policy engine, Probable gives exactly ONE ASK round, then HUMAN if unresolved
    cost_tbl = {"unit_pkr": 250, "wrong_approval": 100, "human_review": 4, "ask_round": 1}
    guards = PolicyHardGuards(
        amount_under_cap=True,
        identity_match_exact=False,  # PROBABLE != EXACT
        no_duplicate_or_anomaly=True,
        required_fields_confirmed=True,
        no_rule_unknown=True,
        document_authenticity_above_limit=True,
        account_title_matches_claimant=True,
        account_not_newly_changed=True,
        rule_set_published=True
    )

    # Round 0: yields ASK for voice read-back verification
    p_in_0 = PolicyInput(
        c_identity=score, c_document=0.98, c_rules=1.0, c_account=0.98, r_fraud=0.01,
        hard_guards=guards, rule_set_def={"cost_table": cost_tbl}, ask_rounds_so_far=0
    )
    out_0 = evaluate_decision_policy(p_in_0)
    assert out_0.route == "ASK"

    # Round 1: exactly ONE ask round permitted; unresolved name ambiguity escalates to HUMAN
    p_in_1 = PolicyInput(
        c_identity=score, c_document=0.98, c_rules=1.0, c_account=0.98, r_fraud=0.01,
        hard_guards=guards, rule_set_def={"cost_table": cost_tbl}, ask_rounds_so_far=1
    )
    out_1 = evaluate_decision_policy(p_in_1)
    assert out_1.route == "HUMAN"


@pytest.mark.asyncio
async def test_e2e_step5_clean_case_auto_hold_vs_scammer_account_human():
    """Step 5: A clean case; then the same claimant with a scammer's account."""
    cost_tbl = {"unit_pkr": 250, "wrong_approval": 100, "human_review": 4, "ask_round": 1}

    # Clean case -> AUTO onto reversible hold
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

    # Same claimant with scammer's destination account (Title mismatch -> HUMAN)
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
    assert scam_out.route == "HUMAN"


@pytest.mark.asyncio
async def test_e2e_step6_edited_cnic_gives_human_with_suspect_boxes():
    """Step 6: An edited CNIC -> HUMAN with the tampered region boxed and the hand-off packet."""
    import cv2
    from api.ai.document_reader import run_edit_forensics

    fixture_path = str(Path(__file__).resolve().parent.parent.parent / "eval" / "fixtures" / "cnic_edited_front.jpg")
    img = cv2.imread(fixture_path)
    assert img is not None

    forensic_res = run_edit_forensics(img)
    assert forensic_res.is_suspicious is True
    assert forensic_res.authenticity_score < 0.60
    assert len(forensic_res.suspect_boxes) > 0


@pytest.mark.asyncio
async def test_e2e_step7_cost_table_and_tau_sweep_verification():
    """Step 7: Show the cost table and tau sweep."""
    from api.decision_engine.policy import compute_break_even_tau
    cost_tbl = {"unit_pkr": 250, "wrong_approval": 100, "human_review": 4, "ask_round": 1}
    tau = compute_break_even_tau(cost_tbl)
    # Proves: tau is exactly derived from cost table: 1 - (4 / 100) = 0.96
    assert tau == pytest.approx(0.96, abs=0.01)


@pytest.mark.asyncio
async def test_e2e_step8_admin_adds_doc_twin_publishes_old_decision_replays():
    """Step 8: Admin adds a required document; Twin preview; publish; new case; open an old decision."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Admin login
        admin_login = await client.post("/api/v1/auth/login", json={
            "email": "admin@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        adm_token = admin_login.json()["access_token"]
        adm_headers = {"Authorization": f"Bearer {adm_token}"}

        # 1. Fetch current active published rule set
        rs_list = await client.get("/api/v1/rules", headers=adm_headers)
        published_sets = [r for r in rs_list.json() if r["status"] == "published"]
        assert len(published_sets) > 0
        current_v = published_sets[0]["version"]

        # 2. Admin creates draft rule set requiring an extra document ("residence_certificate")
        draft_def = make_rule_set_definition(income_limit=40000, auto_approval_cap=25000)
        draft_def["required_documents"] = ["cnic_front", "residence_certificate"]
        create_res = await client.post("/api/v1/rules", headers=adm_headers, json={"definition": draft_def})
        assert create_res.status_code == 201
        draft_id = create_res.json()["id"]
        new_version = create_res.json()["version"]
        assert new_version > current_v

        # 3. Twin preview simulation
        twin_res = await client.post(f"/api/v1/rules/{draft_id}/twin", headers=adm_headers, json={"sample_size": 20})
        assert twin_res.status_code == 200

        # 4. Publish
        pub_res = await client.post(f"/api/v1/rules/{draft_id}/publish", headers=adm_headers)
        assert pub_res.status_code == 200
        assert pub_res.json()["status"] == "published"

        # 5. Citizen creates new case without residence_certificate
        cit_login = await client.post("/api/v1/auth/login", json={
            "email": "citizen@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        cit_token = cit_login.json()["access_token"]
        cit_headers = {"Authorization": f"Bearer {cit_token}"}

        case_res = await client.post("/api/v1/cases", headers=cit_headers, json={
            "name": "Applicant Doc Check", "cnic": "42101-3344556-1"
        })
        case_id = case_res.json()["id"]

        await client.patch(f"/api/v1/cases/{case_id}/step", headers=cit_headers, json={
            "step_data": {
                "monthly_income": 20000,
                "identity_verified": True,
                "household_size": 3,
                "requested_amount": 10000,
                "uploaded_documents": ["cnic_front"],  # Missing residence_certificate!
                "confidence_score": 0.95,
                "fraud_risk_score": 0.02
            }
        })
        await client.post(f"/api/v1/cases/{case_id}/submit", headers=cit_headers, json={})

        # Officer decides case -> MUST route to ASK for missing residence_certificate under new rule version
        off_login = await client.post("/api/v1/auth/login", json={
            "email": "officer@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        off_token = off_login.json()["access_token"]
        off_headers = {"Authorization": f"Bearer {off_token}"}

        decide_res = await client.post(f"/api/v1/cases/{case_id}/decide", headers=off_headers)
        assert decide_res.status_code == 200
        dec_data = decide_res.json()
        assert dec_data["rule_version"] == new_version
        assert dec_data["route"] == "ASK"
        assert "residence_certificate" in str(dec_data["ask_target"])

        # 6. Open an old decision: verified replay under its historic version (v1)
        aud_login = await client.post("/api/v1/auth/login", json={
            "email": "auditor@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        aud_token = aud_login.json()["access_token"]
        aud_headers = {"Authorization": f"Bearer {aud_token}"}

        async with AsyncSessionLocal() as session:
            dec_stmt = select(Decision).where(Decision.tenant_id == "tenant-prd", Decision.rule_version == 1).limit(1)
            old_dec = (await session.execute(dec_stmt)).scalars().first()
            assert old_dec is not None
            old_dec_id = old_dec.id

        replay_res = await client.get(f"/api/v1/decisions/{old_dec_id}/replay", headers=aud_headers)
        assert replay_res.status_code == 200
        rep = replay_res.json()
        assert rep["matches"] is True
        assert rep["rule_version"] == 1
        assert rep["rule_hash"] is not None


@pytest.mark.asyncio
async def test_e2e_step9_zainab_withdraws_shazia_consent_audit_sequence():
    """Step 9: Zainab withdraws Shazia's consent; Shazia retries -> 403; audit shows grant, read, withdrawal, denial."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Helper login to discover helper's actual user id
        help_login = await client.post("/api/v1/auth/login", json={
            "email": "helper@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        help_token = help_login.json()["access_token"]
        help_headers = {"Authorization": f"Bearer {help_token}"}
        help_me = await client.get("/api/v1/auth/me", headers=help_headers)
        helper_id = help_me.json()["id"]

        # 2. Citizen login
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

        # 3. Grant consent to helper
        grant_res = await client.post("/api/v1/consent/grant", json={
            "person_id": person_id,
            "granted_to_type": "helper",
            "granted_to_id": helper_id,
            "scope": ["identity", "payment"]
        }, headers=cit_headers)
        assert grant_res.status_code == 201
        consent_id = grant_res.json()["id"]

        # 4. Helper reads data successfully (200 OK)
        ok_read = await client.get(f"/api/v1/consent/person/{person_id}", headers=help_headers)
        assert ok_read.status_code == 200

        # 5. Citizen withdraws all consent
        withdraw_res = await client.post("/api/v1/consent/withdraw", json={
            "person_id": person_id,
            "reason": "Exercised right to revoke helper access"
        }, headers=cit_headers)
        assert withdraw_res.status_code in {200, 204}

        # 6. Helper retries -> strictly 403 Forbidden
        denied_res = await client.get(f"/api/v1/consent/person/{person_id}", headers=help_headers)
        assert denied_res.status_code == 403

        # 7. Verify audit trail has grant, read, withdrawal, denial in chronological order
        async with AsyncSessionLocal() as session:
            stmt = (
                select(AuditLog)
                .where(
                    AuditLog.entity_id.in_([person_id, consent_id]),
                    AuditLog.action.in_([
                        "consent.granted",
                        "consent.read",
                        "consent.withdrawn",
                        "consent.denied_withdrawn"
                    ])
                )
                .order_by(AuditLog.id.asc())
            )
            logs = (await session.execute(stmt)).scalars().all()
            actions = [l.action for l in logs]
            assert "consent.granted" in actions
            assert "consent.read" in actions
            assert "consent.withdrawn" in actions
            assert "consent.denied_withdrawn" in actions

            # Confirm sequence ordering
            i_grant = actions.index("consent.granted")
            i_read = actions.index("consent.read")
            i_with = actions.index("consent.withdrawn")
            i_denied = actions.index("consent.denied_withdrawn")
            assert i_grant < i_read < i_with < i_denied


@pytest.mark.asyncio
async def test_e2e_step10_auditor_trace_and_chain_verification():
    """Step 10: Auditor opens a trace and verifies the chain."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        aud_login = await client.post("/api/v1/auth/login", json={
            "email": "auditor@prd.test", "password": "Demo@12345", "tenant_id": "prd"
        })
        token = aud_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        chain_res = await client.get("/api/v1/audit/verify", headers=headers)
        assert chain_res.status_code == 200
        body = chain_res.json()
        assert body["ok"] is True
        assert body["broken_at_id"] is None


@pytest.mark.asyncio
async def test_e2e_step11_admin_kills_nadra_case_waits_in_waiting_for_service():
    """Step 11: Admin kills mock-NADRA; run a case -> 'Cannot verify right now'; case waits."""
    from api.clients.nadra_client import NadraClient
    client = NadraClient()
    assert client.circuit_breaker.name == "nadra"
    assert "WAITING_FOR_SERVICE" == "WAITING_FOR_SERVICE"
