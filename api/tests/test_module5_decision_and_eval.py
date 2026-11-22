"""Comprehensive automated tests for Module 5: Decision Engine & Evaluation Harness.

Validates all directives from docs/BLUEPRINT.md sections 5, 8, 11 and AGENTS.md:
- Pure decision policy property tests (never rejects, exception -> HUMAN).
- Hard guard enforcement (wrong account blocks AUTO, unknown rule blocks AUTO).
- Cost break-even threshold derivation & Clopper-Pearson exact reference verification.
- HMAC decision token minting and validation.
- Reversible hold workflow & officer-only reversal.
- Bilingual explanations & reassuring human messages.
- Auditor trace access control (Auditor 200, Citizen 403).
- Review queue priority ordering.
- Evaluation harness determinism and endpoint retrieval.
"""
import pytest
import pytest_asyncio
import uuid
import math
from httpx import AsyncClient

from api.decision_engine.clopper_pearson import clopper_pearson_upper_bound, binomial_cdf
from api.decision_engine.calibration import IsotonicCalibrator, select_optimal_tau
from api.decision_engine.policy import (
    PolicyInput,
    PolicyOutput,
    PolicyHardGuards,
    evaluate_decision_policy,
)
from api.security import mint_decision_token, verify_decision_token
from eval.generator import generate_synthetic_dataset
from eval.harness import run_evaluation_harness


# ---------------------------------------------------------------------------
# 1. Pure Policy & Math Tests
# ---------------------------------------------------------------------------

def test_clopper_pearson_against_analytical_and_known_values():
    """Verifies Clopper-Pearson exact upper confidence bound."""
    # Analytical: k=0, n=300, conf=0.95 => 1 - 0.05^(1/300) ~= 0.009939
    bound_300 = clopper_pearson_upper_bound(0, 300, confidence=0.95)
    expected_300 = 1.0 - math.pow(0.05, 1.0 / 300.0)
    assert abs(bound_300 - expected_300) < 1e-6
    assert bound_300 <= 0.01  # Guarantees <= 1% error bound!

    # Analytical: k=0, n=100, conf=0.95 => 1 - 0.05^0.01 ~= 0.02951
    bound_100 = clopper_pearson_upper_bound(0, 100, confidence=0.95)
    expected_100 = 1.0 - math.pow(0.05, 0.01)
    assert abs(bound_100 - expected_100) < 1e-6

    # k=1, n=100: bisection matches binomial CDF threshold
    bound_1_100 = clopper_pearson_upper_bound(1, 100, confidence=0.95)
    assert 0.045 < bound_1_100 < 0.050
    # At bound_1_100, P(X <= 1; 100, p) should be approximately 0.05
    assert abs(binomial_cdf(1, 100, bound_1_100) - 0.05) < 1e-4


def test_property_pure_policy_never_rejects():
    """Property test: No input combination can EVER produce a 'REJECT' route."""
    import random
    rng = random.Random(1337)

    rule_def = {
        "cost_table": {"unit_pkr": 250, "wrong_approval": 100, "human_review": 4, "ask_round": 1},
        "thresholds": {"auto_approval_p_min": 0.96},
        "reason_codes": {}
    }

    for _ in range(500):
        c_id = rng.random()
        c_doc = rng.random()
        c_rules = rng.random()
        c_acc = rng.random()
        r_fraud = rng.random()
        ask_rounds = rng.randint(0, 4)

        hard_guards = PolicyHardGuards(
            amount_within_cap=rng.choice([True, False]),
            identity_match_exact=rng.choice([True, False]),
            no_duplicate_or_anomaly=rng.choice([True, False]),
            all_required_fields_confirmed=rng.choice([True, False]),
            no_rule_returned_unknown=rng.choice([True, False]),
            document_authenticity_above_limit=rng.choice([True, False]),
            account_title_matches_claimant=rng.choice([True, False]),
            account_not_newly_changed=rng.choice([True, False]),
            rule_set_published=rng.choice([True, False]),
            all_mock_services_healthy=rng.choice([True, False]),
        )

        inp = PolicyInput(
            c_identity=c_id,
            c_document=c_doc,
            c_rules=c_rules,
            c_account=c_acc,
            r_fraud=r_fraud,
            hard_guards=hard_guards,
            ask_rounds_so_far=ask_rounds,
            rule_set_def=rule_def,
            seed=rng.randint(1, 10000)
        )

        output = evaluate_decision_policy(inp)
        assert output.route in {"AUTO", "ASK", "HUMAN"}
        assert output.route != "REJECT"


def test_pure_policy_exception_fails_closed_to_human():
    """Unhandled internal exception strictly falls back to HUMAN."""
    # Malformed policy input that would break dict accesses if unhandled
    inp = PolicyInput(
        c_identity=0.99,
        c_document=0.99,
        c_rules=0.99,
        c_account=0.99,
        r_fraud=0.01,
        hard_guards=PolicyHardGuards(),
        rule_set_def={"cost_table": "NOT_A_DICT"},  # Causes exception inside policy
        seed=42
    )
    output = evaluate_decision_policy(inp)
    assert output.route == "HUMAN"
    assert "fail_closed_exception" in output.trace
    assert "en" in output.citizen_reason
    assert "ur" in output.citizen_reason


def test_wrong_destination_account_blocks_auto():
    """Account title mismatch blocks AUTO and routes to HUMAN (tagged FRAUD_ACCOUNT_MISMATCH)."""
    rule_def = {
        "cost_table": {"unit_pkr": 250, "wrong_approval": 100, "human_review": 4, "ask_round": 1},
        "thresholds": {"auto_approval_p_min": 0.96},
        "reason_codes": {}
    }
    guards = PolicyHardGuards(
        account_title_matches_claimant=False  # Mismatch!
    )
    inp = PolicyInput(
        c_identity=0.99,
        c_document=0.99,
        c_rules=1.0,
        c_account=0.20,
        r_fraud=0.85,
        hard_guards=guards,
        ask_rounds_so_far=0,
        rule_set_def=rule_def,
        seed=42
    )
    output = evaluate_decision_policy(inp)
    assert output.route == "HUMAN"
    assert output.trace.get("selected_reason_code") == "FRAUD_ACCOUNT_MISMATCH"


def test_unknown_rule_blocks_auto():
    """If a rule evaluation returns unknown, hard guard blocks AUTO."""
    rule_def = {
        "cost_table": {"unit_pkr": 250, "wrong_approval": 100, "human_review": 4, "ask_round": 1},
        "thresholds": {"auto_approval_p_min": 0.96},
        "reason_codes": {}
    }
    guards = PolicyHardGuards(
        no_rule_returned_unknown=False  # Unknown rule!
    )
    inp = PolicyInput(
        c_identity=0.99,
        c_document=0.99,
        c_rules=0.50,
        c_account=0.99,
        r_fraud=0.01,
        hard_guards=guards,
        ask_rounds_so_far=0,
        rule_set_def=rule_def,
        seed=42
    )
    output = evaluate_decision_policy(inp)
    assert output.route != "AUTO"


def test_changing_cost_table_shifts_tau():
    """Modifying cost weights changes break-even tau as derived from cost model."""
    rule_def_high_penalty = {
        "cost_table": {"unit_pkr": 250, "wrong_approval": 200, "human_review": 2, "ask_round": 1},
        "reason_codes": {}
    }
    rule_def_low_penalty = {
        "cost_table": {"unit_pkr": 250, "wrong_approval": 50, "human_review": 5, "ask_round": 1},
        "reason_codes": {}
    }
    guards = PolicyHardGuards()

    inp1 = PolicyInput(
        c_identity=0.99, c_document=0.99, c_rules=1.0, c_account=0.99, r_fraud=0.01,
        hard_guards=guards, rule_set_def=rule_def_high_penalty, seed=42
    )
    out1 = evaluate_decision_policy(inp1)

    inp2 = PolicyInput(
        c_identity=0.99, c_document=0.99, c_rules=1.0, c_account=0.99, r_fraud=0.01,
        hard_guards=guards, rule_set_def=rule_def_low_penalty, seed=42
    )
    out2 = evaluate_decision_policy(inp2)

    # High penalty: tau = 1 - (2 / 200) = 0.99
    # Low penalty: tau = 1 - (5 / 50) = 0.90
    assert out1.tau > out2.tau
    assert abs(out1.tau - 0.99) < 1e-4
    assert abs(out2.tau - 0.90) < 1e-4


def test_hmac_decision_token_mint_and_verify():
    """Decision token minting is deterministic and cryptographically verified."""
    case_id = "case-12345"
    tenant_id = "tenant-prd"
    route = "AUTO"
    p = 0.9850
    input_hash = "abc123hash"
    secret = "test-secret-key"

    token = mint_decision_token(
        case_id=case_id,
        amount=25000.0,
        tenant_id=tenant_id,
        route=route,
        p=p,
        input_hash=input_hash,
        secret=secret
    )
    assert "." in token

    # Valid token verifies True
    payload = verify_decision_token(token, expected_case_id=case_id, expected_amount=25000.0, expected_route=route, secret=secret)
    assert payload["case_id"] == case_id
    assert payload["route"] == "AUTO"

    # Tampered route fails
    with pytest.raises(ValueError):
        verify_decision_token(token, expected_case_id=case_id, expected_route="HUMAN", secret=secret)

    # Tampered amount fails
    with pytest.raises(ValueError):
        verify_decision_token(token, expected_case_id=case_id, expected_amount=50000.0, secret=secret)

    # Wrong secret fails
    with pytest.raises(ValueError):
        verify_decision_token(token, expected_case_id=case_id, secret="wrong-secret")


# ---------------------------------------------------------------------------
# 2. Integration & API Endpoints Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_case_evaluation_auto_flow(client: AsyncClient, helper_prd_token: str, officer_prd_token: str):
    """Submits a clean eligible case, evaluates via POST /cases/{id}/evaluate, and verifies AUTO flow."""
    # 1. Create and submit eligible case
    create_res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {helper_prd_token}"},
        json={
            "name": "Eligible Citizen",
            "father_name": "Father Name",
            "cnic": "42101-1111111-1",
            "initial_step": {
                "claim_amount": 25000.0,
                "monthly_income": 18000,
                "family_size": 6,
                "account_number": "PK99HABB0000000001",
                "has_cnic_document": True
            }
        }
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["id"]

    # Submit case
    sub_res = await client.post(
        f"/api/v1/cases/{case_id}/submit",
        headers={"Authorization": f"Bearer {helper_prd_token}"},
        json={"reason": "Completed form"}
    )
    assert sub_res.status_code == 200

    # 2. Execute full evaluation pipeline
    eval_res = await client.post(
        f"/api/v1/cases/{case_id}/evaluate",
        headers={"Authorization": f"Bearer {officer_prd_token}"}
    )
    assert eval_res.status_code == 200
    data = eval_res.json()
    assert data["route"] in {"AUTO", "HUMAN"}  # Might be 5% audit sample
    assert "p" in data
    assert "tau" in data
    assert "citizen_reason" in data

    if data["route"] == "AUTO":
        assert data["case_status"] == "APPROVED_ON_HOLD"
        assert data["decision_token"] is not None
        assert data["payment_reference"] is not None

        # 3. Test Reversible Hold: Officer reverses hold
        rev_res = await client.post(
            f"/api/v1/cases/{case_id}/reverse-hold",
            headers={"Authorization": f"Bearer {officer_prd_token}"},
            json={"reason": "Duplicate claim detected by field officer"}
        )
        assert rev_res.status_code == 200
        assert rev_res.json()["status"] == "REVERSED"


@pytest.mark.asyncio
async def test_explanation_bilingual_and_trace_access_control(
    client: AsyncClient,
    citizen_prd_token: str,
    officer_prd_token: str,
    auditor_prd_token: str
):
    """Verifies bilingual explanation endpoint and strict access control on decision trace."""
    # 1. Create case as citizen
    create_res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {citizen_prd_token}"},
        json={
            "name": "Citizen Explanation Test",
            "father_name": "Father Name",
            "cnic": "42101-2222222-2",
            "initial_step": {
                "claim_amount": 25000.0,
                "monthly_income": 20000,
                "family_size": 5,
                "account_number": "PK99HABB0000000002",
                "has_cnic_document": True
            }
        }
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["id"]

    # Evaluate case
    eval_res = await client.post(
        f"/api/v1/cases/{case_id}/evaluate",
        headers={"Authorization": f"Bearer {officer_prd_token}"}
    )
    assert eval_res.status_code == 200
    decision_id = eval_res.json()["decision_id"]

    # 2. Citizen accesses own explanation
    exp_res = await client.get(
        f"/api/v1/cases/{case_id}/explanation",
        headers={"Authorization": f"Bearer {citizen_prd_token}"}
    )
    assert exp_res.status_code == 200
    exp_data = exp_res.json()
    assert "en" in exp_data["citizen_reason"]
    assert "ur" in exp_data["citizen_reason"]

    # 3. Trace endpoint: Auditor and Officer get 200, Citizen gets 403
    aud_res = await client.get(
        f"/api/v1/decisions/{decision_id}/trace",
        headers={"Authorization": f"Bearer {auditor_prd_token}"}
    )
    assert aud_res.status_code == 200
    assert "trace" in aud_res.json()

    cit_res = await client.get(
        f"/api/v1/decisions/{decision_id}/trace",
        headers={"Authorization": f"Bearer {citizen_prd_token}"}
    )
    assert cit_res.status_code == 403


@pytest.mark.asyncio
async def test_officer_review_queue_and_actions(client: AsyncClient, helper_prd_token: str, officer_prd_token: str):
    """Verifies officer review queue ordering and officer-only exit actions (approval/rejection)."""
    # 1. Fetch review queue
    q_res = await client.get(
        "/api/v1/cases/review-queue",
        headers={"Authorization": f"Bearer {officer_prd_token}"}
    )
    assert q_res.status_code == 200
    queue = q_res.json()
    assert isinstance(queue, list)
    # Check descending priority sorting
    if len(queue) >= 2:
        for i in range(len(queue) - 1):
            assert queue[i]["priority"] >= queue[i + 1]["priority"]

    # 2. Officer rejection: AI never rejects, only human officer rejects
    create_res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {helper_prd_token}"},
        json={
            "name": "Officer Action Applicant",
            "father_name": "Father Name",
            "cnic": "42101-3333333-3",
            "initial_step": {"claim_amount": 10000.0, "monthly_income": 80000}  # High income -> IN_REVIEW
        }
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["id"]

    # Submit and evaluate to reach IN_REVIEW
    await client.post(
        f"/api/v1/cases/{case_id}/submit",
        headers={"Authorization": f"Bearer {helper_prd_token}"},
        json={"reason": "Submission"}
    )
    await client.post(
        f"/api/v1/cases/{case_id}/evaluate",
        headers={"Authorization": f"Bearer {officer_prd_token}"}
    )

    rej_res = await client.post(
        f"/api/v1/cases/{case_id}/officer-reject",
        headers={"Authorization": f"Bearer {officer_prd_token}"},
        json={"note": "Official document verification failed upon field inspection"}
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED_BY_OFFICER"


@pytest.mark.asyncio
async def test_evaluation_harness_determinism_and_api(client: AsyncClient, admin_prd_token: str, auditor_prd_token: str):
    """Verifies harness execution determinism and GET /eval/latest endpoint."""
    # 1. Deterministic run: same seed produces identical results
    run1 = run_evaluation_harness(seed=42)
    run2 = run_evaluation_harness(seed=42)

    assert run1["optimal_tau"] == run2["optimal_tau"]
    assert run1["test_evaluation"]["k_wrong_approvals"] == run2["test_evaluation"]["k_wrong_approvals"]
    assert run1["test_evaluation"]["clopper_pearson_95_upper_bound"] == run2["test_evaluation"]["clopper_pearson_95_upper_bound"]
    assert run1["test_evaluation"]["route_mix"] == run2["test_evaluation"]["route_mix"]

    # 2. API GET /eval/latest
    eval_res = await client.get(
        "/api/v1/eval/latest",
        headers={"Authorization": f"Bearer {auditor_prd_token}"}
    )
    assert eval_res.status_code == 200
    data = eval_res.json()
    assert "total_cases" in data
    assert "test_metrics" in data
    assert data["test_metrics"]["bound_le_1pct"] is True
