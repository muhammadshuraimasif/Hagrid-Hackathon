"""Comprehensive tests for Part 1: Versioned Rules, Digital Twin, and Auditor Replay.

Requirements tested:
1. Publishing version N+1 applies to the very next case without restart.
2. An old decision replays identically under its original version.
3. Publishing without running the twin fails.
4. Editing a published rule set fails at DB level AND API level.
5. An unknown input returns unknown and blocks AUTO.
6. Twin counts match expectations on a seeded set of 30 past decisions.
7. Auditor replay endpoint verifies a decision.
8. RBAC and tenant isolation.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from api.database import AsyncSessionLocal
from api.models import RuleSet, Decision, Case
from api.rules.evaluator import evaluate_rule, UNKNOWN
from api.rules.engine import evaluate_case, compute_content_hash
from api.seed import make_rule_set_definition

@pytest.mark.asyncio
async def test_unknown_input_returns_unknown_and_blocks_auto():
    """Missing fields evaluate to 'unknown' and strictly block AUTO routing."""
    rule_expr = {">=": [{"var": "monthly_income"}, 0]}
    
    # Missing field
    status = evaluate_rule(rule_expr, {})
    assert status == "unknown"

    # Present field
    status_pass = evaluate_rule(rule_expr, {"monthly_income": 25000})
    assert status_pass == "pass"

    # Evaluation of complete rule set where income is missing
    rule_def = make_rule_set_definition(income_limit=40000, auto_approval_cap=25000)
    
    # Input has valid identity, within cap, but income is missing (None)
    incomplete_input = {
        "monthly_income": None,
        "identity_verified": True,
        "household_size": 3,
        "requested_amount": 10000,
        "uploaded_documents": ["cnic_front", "salary_slip"],
        "confidence_score": 0.98,
        "fraud_risk_score": 0.02,
    }

    eval_result = evaluate_case(rule_def, incomplete_input)
    assert eval_result.route == "ASK"
    assert eval_result.route != "AUTO"
    assert eval_result.ask_target == "monthly_income"


@pytest.mark.asyncio
async def test_editing_published_rule_set_fails_at_db_and_api_level(
    client: AsyncClient,
    admin_prd_token: str
):
    """Published rule sets are immutable: updates/deletes fail at API (409) and DB trigger levels."""
    headers = {"Authorization": f"Bearer {admin_prd_token}"}

    # 1. Fetch published rule set v1 for prd
    async with AsyncSessionLocal() as session:
        rs_res = await session.execute(
            select(RuleSet).where(RuleSet.tenant_id == "tenant-prd", RuleSet.status == "published")
        )
        published_rs = rs_res.scalars().first()
        assert published_rs is not None
        rs_id = published_rs.id

    # 2. API Level Check: PUT on published rule set returns 409 Conflict
    new_def = make_rule_set_definition(income_limit=50000, auto_approval_cap=30000)
    api_res = await client.put(f"/api/v1/rules/{rs_id}", headers=headers, json={"definition": new_def})
    assert api_res.status_code == 409
    assert "immutable" in api_res.json()["message"].lower()

    # 3. DB Trigger Level Check: Direct SQL UPDATE is blocked
    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception) as exc_info:
            await session.execute(
                text("UPDATE rule_sets SET definition = '{\"hacked\": true}' WHERE id = :id"),
                {"id": rs_id}
            )
            await session.commit()
        assert "immutable" in str(exc_info.value).lower()

    # 4. DB Trigger Level Check: Direct SQL DELETE is blocked
    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception) as exc_info:
            await session.execute(
                text("DELETE FROM rule_sets WHERE id = :id"),
                {"id": rs_id}
            )
            await session.commit()
        assert "cannot be deleted" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_publishing_without_running_twin_fails(
    client: AsyncClient,
    admin_prd_token: str
):
    """Publishing a draft rule set is strictly blocked until Digital Twin simulation runs on exact content hash."""
    headers = {"Authorization": f"Bearer {admin_prd_token}"}

    # 1. Create a draft rule set
    draft_def = make_rule_set_definition(income_limit=38000, auto_approval_cap=22000)
    create_res = await client.post("/api/v1/rules", headers=headers, json={"definition": draft_def})
    assert create_res.status_code == 201
    draft_id = create_res.json()["id"]

    # 2. Attempt publish immediately -> 409 Conflict
    publish_res = await client.post(f"/api/v1/rules/{draft_id}/publish", headers=headers)
    assert publish_res.status_code == 409
    assert "digital twin simulation" in publish_res.json()["message"].lower()

    # 3. Run twin simulation
    twin_res = await client.post(f"/api/v1/rules/{draft_id}/twin", headers=headers, json={"sample_size": 30})
    assert twin_res.status_code == 200

    # 4. Modify draft definition after twin was run (invalidates twin report)
    modified_def = make_rule_set_definition(income_limit=37000, auto_approval_cap=21000)
    put_res = await client.put(f"/api/v1/rules/{draft_id}", headers=headers, json={"definition": modified_def})
    assert put_res.status_code == 200

    # 5. Attempt publish again without re-running twin -> 409 Conflict
    publish_res2 = await client.post(f"/api/v1/rules/{draft_id}/publish", headers=headers)
    assert publish_res2.status_code == 409


@pytest.mark.asyncio
async def test_twin_counts_match_expectations_on_seeded_30_decisions(
    client: AsyncClient,
    admin_prd_token: str
):
    """Digital Twin accurately simulates impact, cost deltas, and risk cases across 30 seeded decisions."""
    headers = {"Authorization": f"Bearer {admin_prd_token}"}

    # Create a draft rule set that tightens income limit from 40k down to 22k
    strict_def = make_rule_set_definition(income_limit=22000, auto_approval_cap=25000)
    create_res = await client.post("/api/v1/rules", headers=headers, json={"definition": strict_def})
    assert create_res.status_code == 201
    draft_id = create_res.json()["id"]

    # Run Digital Twin simulation
    twin_res = await client.post(f"/api/v1/rules/{draft_id}/twin", headers=headers, json={"sample_size": 30})
    assert twin_res.status_code == 200
    report = twin_res.json()

    assert report["sample_size"] == 30
    # Because income was lowered to 22k, cases previously AUTO with income 23k-29k must now transition to HUMAN (newly_human)
    assert report["newly_human"] > 0
    assert report["newly_ineligible"] > 0
    assert isinstance(report["change_in_expected_cost_per_case"], float)
    assert "risk_cases" in report


@pytest.mark.asyncio
async def test_publishing_version_n_plus_1_applies_to_very_next_case_without_restart(
    client: AsyncClient,
    admin_prd_token: str,
    officer_prd_token: str,
    citizen_prd_token: str
):
    """Publishing version N+1 activates immediately with zero restart and affects the next decision."""
    admin_headers = {"Authorization": f"Bearer {admin_prd_token}"}
    officer_headers = {"Authorization": f"Bearer {officer_prd_token}"}
    citizen_headers = {"Authorization": f"Bearer {citizen_prd_token}"}

    # Step 1: Query current active published rule set to get its active cap
    rs_list_res = await client.get("/api/v1/rules", headers=admin_headers)
    assert rs_list_res.status_code == 200
    published_sets = [r for r in rs_list_res.json() if r["status"] == "published"]
    assert len(published_sets) > 0
    current_active_rs = published_sets[0]
    current_version = current_active_rs["version"]
    current_cap = current_active_rs["definition"]["auto_approval_cap"]

    # Amount that strictly exceeds current active cap -> MUST be routed to HUMAN
    test_amount = current_cap + 3000

    case_res = await client.post(
        "/api/v1/cases",
        headers=citizen_headers,
        json={"name": "Test Applicant", "cnic": "42101-7777777-1"}
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # Save step data
    await client.patch(
        f"/api/v1/cases/{case_id}/step",
        headers=citizen_headers,
        json={
            "step_data": {
                "monthly_income": 25000,
                "identity_verified": True,
                "household_size": 4,
                "requested_amount": test_amount,  # Exceeds current cap
                "uploaded_documents": ["cnic_front", "salary_slip"],
                "confidence_score": 0.95,
                "fraud_risk_score": 0.04,
            }
        }
    )

    # Submit case
    await client.post(f"/api/v1/cases/{case_id}/submit", headers=citizen_headers, json={})

    # Decide under current active version
    decide_res1 = await client.post(f"/api/v1/cases/{case_id}/decide", headers=officer_headers)
    assert decide_res1.status_code == 200
    d1 = decide_res1.json()
    assert d1["rule_version"] == current_version
    assert d1["route"] == "HUMAN"  # Exceeds current cap

    # Step 2: Admin drafts Rule Set N+1 with a higher auto_approval_cap
    new_cap = test_amount + 5000
    v_next_def = make_rule_set_definition(income_limit=40000, auto_approval_cap=new_cap)
    create_v_next = await client.post("/api/v1/rules", headers=admin_headers, json={"definition": v_next_def})
    assert create_v_next.status_code == 201
    v_next_id = create_v_next.json()["id"]
    expected_new_version = create_v_next.json()["version"]
    assert expected_new_version > current_version

    # Run Digital Twin on draft
    await client.post(f"/api/v1/rules/{v_next_id}/twin", headers=admin_headers, json={"sample_size": 30})

    # Publish draft
    pub_res = await client.post(f"/api/v1/rules/{v_next_id}/publish", headers=admin_headers)
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "published"
    assert pub_res.json()["version"] == expected_new_version

    # Step 3: Create Case 2 with identical inputs (same test_amount)
    case_res2 = await client.post(
        "/api/v1/cases",
        headers=citizen_headers,
        json={"name": "Test Applicant 2", "cnic": "42101-8888888-1"}
    )
    case_id2 = case_res2.json()["id"]

    await client.patch(
        f"/api/v1/cases/{case_id2}/step",
        headers=citizen_headers,
        json={
            "step_data": {
                "monthly_income": 25000,
                "identity_verified": True,
                "household_size": 4,
                "requested_amount": test_amount,  # Now fits under new_cap!
                "uploaded_documents": ["cnic_front", "salary_slip"],
                "confidence_score": 0.95,
                "fraud_risk_score": 0.04,
            }
        }
    )
    await client.post(f"/api/v1/cases/{case_id2}/submit", headers=citizen_headers, json={})

    # Decide Case 2: Must immediately use new version with NO server restart
    decide_res2 = await client.post(f"/api/v1/cases/{case_id2}/decide", headers=officer_headers)
    assert decide_res2.status_code == 200
    d2 = decide_res2.json()
    assert d2["rule_version"] == expected_new_version
    assert d2["route"] == "AUTO"  # Fits under new cap!


@pytest.mark.asyncio
async def test_old_decision_replays_identically_under_original_version(
    client: AsyncClient,
    auditor_prd_token: str
):
    """An old decision decided under v1 replays identically under v1 even when later versions exist."""
    headers = {"Authorization": f"Bearer {auditor_prd_token}"}

    # Fetch a seeded decision for tenant-prd
    async with AsyncSessionLocal() as session:
        dec_res = await session.execute(
            select(Decision).where(Decision.tenant_id == "tenant-prd", Decision.rule_version == 1).limit(1)
        )
        decision = dec_res.scalars().first()
        assert decision is not None
        decision_id = decision.id
        orig_route = decision.route
        orig_cost = decision.expected_cost

    # Replay decision via auditor endpoint
    replay_res = await client.get(f"/api/v1/decisions/{decision_id}/replay", headers=headers)
    assert replay_res.status_code == 200
    rep = replay_res.json()

    assert rep["matches"] is True
    assert rep["original_outcome"]["route"] == orig_route
    assert rep["replayed_outcome"]["route"] == orig_route
    assert rep["original_outcome"]["expected_cost"] == orig_cost
    assert rep["replayed_outcome"]["expected_cost"] == orig_cost


@pytest.mark.asyncio
async def test_rules_rbac_and_tenant_isolation(
    client: AsyncClient,
    citizen_prd_token: str,
    helper_prd_token: str,
    officer_prd_token: str,
    admin_prd_token: str,
    admin_mao_token: str
):
    """Non-admin roles cannot modify rules, and tenants cannot see each other's rules."""
    cit_h = {"Authorization": f"Bearer {citizen_prd_token}"}
    hlp_h = {"Authorization": f"Bearer {helper_prd_token}"}
    off_h = {"Authorization": f"Bearer {officer_prd_token}"}
    adm_prd_h = {"Authorization": f"Bearer {admin_prd_token}"}
    adm_mao_h = {"Authorization": f"Bearer {admin_mao_token}"}

    rule_payload = {"definition": make_rule_set_definition(30000, 20000)}

    # Citizen, Helper, Officer get 403 on POST /rules
    for h in [cit_h, hlp_h, off_h]:
        res = await client.post("/api/v1/rules", headers=h, json=rule_payload)
        assert res.status_code == 403

    # PRD Admin creates draft
    res_prd = await client.post("/api/v1/rules", headers=adm_prd_h, json=rule_payload)
    assert res_prd.status_code == 201
    prd_rule_id = res_prd.json()["id"]

    # MAO Admin cannot access PRD's rule set (tenant isolation -> 404)
    res_mao = await client.get(f"/api/v1/rules/{prd_rule_id}", headers=adm_mao_h)
    assert res_mao.status_code == 404


@pytest.mark.asyncio
async def test_ruleset_version_threshold_update_changes_outcome_for_next_case(
    client: AsyncClient,
    admin_prd_token: str,
    officer_prd_token: str,
    citizen_prd_token: str
):
    """AGENTS.md rule 3: Thresholds are data in versioned immutable rule sets.
    Publishing a new rule set version with updated threshold dynamically changes
    the decision route for the next case without server restart.
    """
    admin_headers = {"Authorization": f"Bearer {admin_prd_token}"}
    officer_headers = {"Authorization": f"Bearer {officer_prd_token}"}
    citizen_headers = {"Authorization": f"Bearer {citizen_prd_token}"}

    # 1. Fetch current active published rule set
    rules_res = await client.get("/api/v1/rules", headers=admin_headers)
    assert rules_res.status_code == 200
    pub_list = [r for r in rules_res.json() if r["status"] == "published"]
    assert len(pub_list) > 0
    v1_id = pub_list[0]["id"]
    v1_def = dict(pub_list[0]["definition"])

    # Verify v1 definition has default variant_match_score = 0.85 (Probable)
    assert v1_def.get("thresholds", {}).get("variant_match_score") == 0.85

    # 2. Case 1 submitted under current version: name variant 'Muhammed' vs registry 'Mohd'
    c1_res = await client.post("/api/v1/cases", headers=citizen_headers, json={
        "name": "Muhammed Tariq",
        "father_name": "Tariq Mehmood",
        "dob": "1985-04-12",
        "cnic": "42101-1000004-1"  # Matches synthetic citizen 'Mohd Tariq'
    })
    c1_data = c1_res.json()
    c1_id = c1_data["id"]
    p1_id = c1_data["person_id"]

    # Citizen grants consent for officer evaluation
    await client.post("/api/v1/consent/grant", headers=citizen_headers, json={
        "person_id": p1_id,
        "granted_to_type": "officer",
        "scope": ["identity", "contact", "documents", "payment", "status"],
        "purpose": "Relief grant evaluation",
        "expiry_days": 30
    })

    await client.patch(f"/api/v1/cases/{c1_id}/step", headers=citizen_headers, json={
        "step_data": {
            "monthly_income": 20000,
            "identity_verified": True,
            "household_size": 4,
            "cnic": "42101-1000004-1",
            "claim_amount": 25000,
            "account_number": "PK36MOCK0000004210110000041",
            "has_cnic_document": True,
            "uploaded_documents": ["cnic_front", "salary_slip"]
        }
    })
    await client.post(f"/api/v1/cases/{c1_id}/submit", headers=citizen_headers, json={})

    # Case 1 evaluates under active rule set: score 0.85 in [0.75, 0.92) -> ASK
    eval1_res = await client.post(f"/api/v1/cases/{c1_id}/evaluate", headers=officer_headers)
    assert eval1_res.status_code == 200
    assert eval1_res.json()["route"] == "ASK"

    # 3. Admin creates draft rule set N+1 modifying threshold: variant_match_score = 0.65 (< 0.75 probable min)
    v2_def = dict(v1_def)
    v2_def["thresholds"] = dict(v2_def.get("thresholds", {}))
    v2_def["thresholds"]["variant_match_score"] = 0.65  # Stricter: variant drops to CONFLICT

    create_v2 = await client.post("/api/v1/rules", headers=admin_headers, json={"definition": v2_def})
    assert create_v2.status_code == 201
    v2_id = create_v2.json()["id"]

    # Run Digital Twin simulation required before publishing
    await client.post(f"/api/v1/rules/{v2_id}/twin", headers=admin_headers, json={"sample_size": 30})

    # Publish version N+1
    pub_v2 = await client.post(f"/api/v1/rules/{v2_id}/publish", headers=admin_headers)
    assert pub_v2.status_code == 200
    v2_version = pub_v2.json()["version"]

    # 4. Case 2 submitted with IDENTICAL inputs after rule set update
    c2_res = await client.post("/api/v1/cases", headers=citizen_headers, json={
        "name": "Muhammed Tariq",
        "father_name": "Tariq Mehmood",
        "dob": "1985-04-12",
        "cnic": "42101-1000004-1"
    })
    c2_data = c2_res.json()
    c2_id = c2_data["id"]
    p2_id = c2_data["person_id"]

    await client.post("/api/v1/consent/grant", headers=citizen_headers, json={
        "person_id": p2_id,
        "granted_to_type": "officer",
        "scope": ["identity", "contact", "documents", "payment", "status"],
        "purpose": "Relief grant evaluation",
        "expiry_days": 30
    })

    await client.patch(f"/api/v1/cases/{c2_id}/step", headers=citizen_headers, json={
        "step_data": {
            "monthly_income": 20000,
            "identity_verified": True,
            "household_size": 4,
            "cnic": "42101-1000004-1",
            "claim_amount": 25000,
            "account_number": "PK36MOCK0000004210110000041",
            "has_cnic_document": True,
            "uploaded_documents": ["cnic_front", "salary_slip"]
        }
    })
    await client.post(f"/api/v1/cases/{c2_id}/submit", headers=citizen_headers, json={})

    # Case 2 evaluates under new active version: score 0.65 < 0.75 -> CONFLICT -> HUMAN
    eval2_res = await client.post(f"/api/v1/cases/{c2_id}/evaluate", headers=officer_headers)
    assert eval2_res.status_code == 200
    assert eval2_res.json()["rule_version"] == v2_version
    assert eval2_res.json()["route"] == "HUMAN"
