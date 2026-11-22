"""Pure decision policy function.

Follows docs/BLUEPRINT.md section 8 and AGENTS.md:
- Pure function: zero I/O, zero network, zero DB access, deterministic with injected seed.
- Three exits only: AUTO, ASK, HUMAN. There is NO reject exit in the type system.
- Break-even threshold tau = 1 - (human_cost / wrong_approval_cost), risk-bounded.
- Hard guards must ALL hold for AUTO.
- Next-Best-Evidence VOI calculation for targeted ASK.
- 5% random audit sample of AUTO cases routed to HUMAN for oversight.
- Absolute fail-closed safety: any exception inside policy returns HUMAN.
"""
import random
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field
from api.decision_engine.calibration import IsotonicCalibrator

RouteType = Literal["AUTO", "ASK", "HUMAN"]


class PolicyHardGuards(BaseModel):
    amount_within_cap: bool = True
    identity_match_exact: bool = True
    no_duplicate_or_anomaly: bool = True
    all_required_fields_confirmed: bool = True
    no_rule_returned_unknown: bool = True
    document_authenticity_above_limit: bool = True
    account_title_matches_claimant: bool = True
    account_not_newly_changed: bool = True
    rule_set_published: bool = True
    all_mock_services_healthy: bool = True

    def all_pass(self) -> bool:
        return (
            self.amount_within_cap
            and self.identity_match_exact
            and self.no_duplicate_or_anomaly
            and self.all_required_fields_confirmed
            and self.no_rule_returned_unknown
            and self.document_authenticity_above_limit
            and self.account_title_matches_claimant
            and self.account_not_newly_changed
            and self.rule_set_published
            and self.all_mock_services_healthy
        )


class PolicyInput(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    c_identity: float = Field(ge=0.0, le=1.0)
    c_document: float = Field(ge=0.0, le=1.0)
    c_rules: float = Field(ge=0.0, le=1.0)
    c_account: float = Field(ge=0.0, le=1.0)
    r_fraud: float = Field(ge=0.0, le=1.0)
    hard_guards: PolicyHardGuards
    ask_rounds_so_far: int = 0
    rule_set_def: Dict[str, Any]
    calibrator: Optional[IsotonicCalibrator] = None
    candidate_evidence: Optional[List[Dict[str, Any]]] = None
    seed: int = 42
    audit_sample_rate: float = 0.05


class PolicyOutput(BaseModel):
    route: RouteType
    c: float
    p: float
    tau: float
    expected_cost: float
    ask_target: Optional[str] = None
    citizen_reason: Dict[str, str]
    is_audit_sample: bool = False
    trace: Dict[str, Any]


def compute_break_even_tau(cost_table: Dict[str, Any]) -> float:
    """Break-even tau derivation: 1 - (human_cost / wrong_approval_cost)."""
    wrong_approval = float(cost_table.get("wrong_approval", 100))
    human_review = float(cost_table.get("human_review", 4))
    return 1.0 - (human_review / wrong_approval)


def calculate_next_best_evidence(
    candidates: List[Dict[str, Any]],
    human_cost: float,
    ask_cost: float,
    unit_pkr: float
) -> Tuple[Optional[str], float]:
    """Computes VOI = q_e * (human_cost - cost_after) - ask_cost for each candidate.
    
    Returns (best_candidate_id, highest_voi).
    """
    best_target = None
    max_voi = -float("inf")

    cost_after = 0.5  # Expected residual review cost in units if resolved
    for cand in candidates:
        target_id = cand.get("id") or cand.get("name")
        q_e = float(cand.get("q_e", 0.80))
        voi = q_e * (human_cost - cost_after) - ask_cost
        if voi > max_voi:
            max_voi = voi
            best_target = target_id

    return best_target, max_voi


def evaluate_decision_policy(policy_input: PolicyInput) -> PolicyOutput:
    """Pure decision policy evaluating input scores, hard guards, cost thresholds, and VOI.
    
    Fails closed: Any unhandled exception strictly routes to HUMAN.
    """
    try:
        cost_table = policy_input.rule_set_def.get("cost_table", {})
        unit_pkr = float(cost_table.get("unit_pkr", 250))
        wrong_approval_cost = float(cost_table.get("wrong_approval", 100))
        human_review_cost = float(cost_table.get("human_review", 4))
        ask_round_cost = float(cost_table.get("ask_round", 1))

        # 1. Composite Raw Score c
        # c = min(c_identity, c_document, c_rules, c_account) * (1 - r_fraud)
        min_comp = min(
            policy_input.c_identity,
            policy_input.c_document,
            policy_input.c_rules,
            policy_input.c_account
        )
        c = max(0.0, min(1.0, min_comp * (1.0 - policy_input.r_fraud)))

        # 2. Isotonic Calibration c -> p
        if policy_input.calibrator:
            p = policy_input.calibrator.calibrate(c)
        else:
            # Default linear mapping if calibrator is not injected
            p = c

        # 3. Cost Break-even Threshold tau
        # (1 - p) * wrong_cost < human_cost => 1 - p < human_cost / wrong_cost => p > 1 - (human_cost / wrong_cost)
        tau_break_even = 1.0 - (human_review_cost / wrong_approval_cost)
        thresholds_cfg = policy_input.rule_set_def.get("thresholds", {})
        tau = max(tau_break_even, float(thresholds_cfg.get("auto_approval_p_min", tau_break_even)))

        # 4. Check Hard Guards
        hard_guards_pass = policy_input.hard_guards.all_pass()

        # 5. Route Selection (AUTO, ASK, HUMAN)
        reason_codes = policy_input.rule_set_def.get("reason_codes", {})
        is_audit_sample = False
        ask_target = None
        route: RouteType = "HUMAN"

        # Check AUTO eligibility: p >= tau AND every hard guard passes
        if p >= tau and hard_guards_pass:
            # 5% random audit sample routed to officer
            prng = random.Random(policy_input.seed)
            if prng.random() < policy_input.audit_sample_rate:
                route = "HUMAN"
                is_audit_sample = True
                selected_reason_code = "AUDIT_SAMPLE"
            else:
                route = "AUTO"
                selected_reason_code = "ELIGIBLE_AUTO"
        else:
            # Case cannot be AUTO-approved. Check if eligible for ASK via Next-Best-Evidence
            # Needs: fewer than 2 ask rounds so far, no hard fraud/tamper, and candidate evidence with VOI > 0
            candidate_list = policy_input.candidate_evidence or []
            if not candidate_list:
                # Build default candidate evidence items
                candidate_list = [
                    {"id": "doc:cnic_back", "q_e": 0.85},
                    {"id": "retake_photo", "q_e": 0.70},
                    {"id": "father_name_voice", "q_e": 0.80},
                ]

            best_item, highest_voi = calculate_next_best_evidence(
                candidate_list,
                human_review_cost,
                ask_round_cost,
                unit_pkr
            )

            # Route to ASK if VOI > 0, within allowed ask rounds, and no fraud/tamper/anomaly flag
            account_mismatch = not policy_input.hard_guards.account_title_matches_claimant
            has_anomaly = (not policy_input.hard_guards.no_duplicate_or_anomaly) or (policy_input.r_fraud > 0.40)
            thresholds_cfg = policy_input.rule_set_def.get("thresholds", {})
            # Name/identity variation has exactly ONE ASK round per Blueprint 12.4 Step 4; general missing docs have max 2
            max_rounds = 1 if not policy_input.hard_guards.identity_match_exact else int(thresholds_cfg.get("max_ask_rounds", 2))
            if (
                highest_voi > 0
                and policy_input.ask_rounds_so_far < max_rounds
                and not account_mismatch
                and not has_anomaly
                and policy_input.hard_guards.rule_set_published
            ):
                route = "ASK"
                ask_target = best_item
                selected_reason_code = "MISSING_EVIDENCE"
            else:
                route = "HUMAN"
                if account_mismatch:
                    selected_reason_code = "FRAUD_ACCOUNT_MISMATCH"
                elif has_anomaly:
                    selected_reason_code = "FRAUD_ANOMALY"
                elif policy_input.ask_rounds_so_far >= max_rounds:
                    selected_reason_code = "MAX_ASK_ROUNDS_REACHED"
                else:
                    selected_reason_code = "ESCALATED_HUMAN"

        # 6. Expected Cost Calculation
        if route == "AUTO":
            expected_cost = round((1.0 - p) * wrong_approval_cost * unit_pkr, 2)
        elif route == "ASK":
            expected_cost = round(ask_round_cost * unit_pkr, 2)
        else:
            expected_cost = round(human_review_cost * unit_pkr, 2)

        # 7. Citizen Reason Formatting
        template = reason_codes.get(selected_reason_code, {
            "en": f"Application status: {route}.",
            "ur": f"درخواست کی صورتحال: {route}۔"
        })
        citizen_reason = {
            "en": template.get("en", "Application processed."),
            "ur": template.get("ur", "درخواست کا جائزہ لیا گیا ہے۔")
        }
        if route == "ASK" and ask_target:
            citizen_reason["en"] += f" Next step: Please provide {ask_target}."
            citizen_reason["ur"] += f" اگلا قدم: براہ کرم {ask_target} فراہم کریں۔"

        trace = {
            "component_scores": {
                "c_identity": policy_input.c_identity,
                "c_document": policy_input.c_document,
                "c_rules": policy_input.c_rules,
                "c_account": policy_input.c_account,
                "r_fraud": policy_input.r_fraud,
            },
            "raw_c": c,
            "calibrated_p": p,
            "tau": tau,
            "tau_break_even": tau_break_even,
            "cost_weights": {
                "wrong_approval": wrong_approval_cost,
                "human_review": human_review_cost,
                "ask_round": ask_round_cost,
                "unit_pkr": unit_pkr,
            },
            "hard_guards": policy_input.hard_guards.model_dump(),
            "hard_guards_pass": hard_guards_pass,
            "ask_rounds_so_far": policy_input.ask_rounds_so_far,
            "ask_target": ask_target,
            "is_audit_sample": is_audit_sample,
            "selected_route": route,
            "selected_reason_code": selected_reason_code,
        }

        return PolicyOutput(
            route=route,
            c=c,
            p=p,
            tau=tau,
            expected_cost=expected_cost,
            ask_target=ask_target,
            citizen_reason=citizen_reason,
            is_audit_sample=is_audit_sample,
            trace=trace
        )

    except Exception as exc:
        # FAIL CLOSED: Any exception inside the policy strictly routes to HUMAN
        return PolicyOutput(
            route="HUMAN",
            c=0.0,
            p=0.0,
            tau=0.96,
            expected_cost=1000.0,
            ask_target=None,
            citizen_reason={
                "en": "Your case has been forwarded for human officer review due to an evaluation anomaly.",
                "ur": "درخواست کے جائزے میں غیر معمولی کیفیت کے باعث کیس کو افسر کے پاس بھیج دیا گیا ہے۔"
            },
            is_audit_sample=False,
            trace={
                "fail_closed_exception": str(exc),
                "selected_route": "HUMAN"
            }
        )
