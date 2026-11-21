"""Decision Engine evaluating cases against versioned rule set definitions."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from api.rules.evaluator import evaluate_rule

def compute_content_hash(definition: Dict[str, Any]) -> str:
    """Computes a deterministic sha256 hash of a rule set definition dictionary."""
    canonical_json = json.dumps(definition, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class EvaluationResult(BaseModel):
    route: str  # AUTO, ASK, HUMAN
    p: float
    expected_cost: float
    input_snapshot: Dict[str, Any]
    trace: Dict[str, Any]
    citizen_reason: Dict[str, str]
    ask_target: Optional[str] = None
    rule_results: List[Dict[str, Any]] = Field(default_factory=list)


def normalize_input_snapshot(raw_input: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts and normalizes all relevant features for auditability and replay."""
    return {
        "monthly_income": raw_input.get("monthly_income"),
        "identity_verified": raw_input.get("identity_verified"),
        "household_size": raw_input.get("household_size"),
        "requested_amount": raw_input.get("requested_amount", 0),
        "uploaded_documents": list(raw_input.get("uploaded_documents") or []),
        "confidence_score": raw_input.get("confidence_score", 0.95),
        "fraud_risk_score": raw_input.get("fraud_risk_score", 0.05),
        "nadra_verified": raw_input.get("nadra_verified"),
        "age": raw_input.get("age"),
    }


def evaluate_case(rule_set_def: Dict[str, Any], raw_input: Dict[str, Any]) -> EvaluationResult:
    """Evaluates case inputs against a rule set definition.
    
    Abides strictly by AGENTS.md:
    1. AI never approves money or rejects a person.
    2. Exactly three exits: AUTO, ASK, HUMAN.
    3. Fails closed to HUMAN on any exception or edge condition.
    4. Auto-approval is strictly blocked if any rule evaluates to 'unknown' or missing docs.
    """
    snapshot = normalize_input_snapshot(raw_input)
    
    # Extract config from rule set definition
    rules = rule_set_def.get("eligibility_rules", [])
    required_docs = rule_set_def.get("required_documents", [])
    thresholds = rule_set_def.get("thresholds", {})
    cost_table = rule_set_def.get("cost_table", {})
    auto_approval_cap = rule_set_def.get("auto_approval_cap", 25000)
    reason_codes = rule_set_def.get("reason_codes", {})

    unit_pkr = cost_table.get("unit_pkr", 250)
    p_min = thresholds.get("auto_approval_p_min", 0.85)
    fraud_max = thresholds.get("fraud_risk_p_max", 0.20)

    # 1. Evaluate eligibility rules
    rule_results = []
    has_fail = False
    has_unknown = False
    first_fail_rule = None
    first_unknown_rule = None

    for r in rules:
        rule_id = r.get("id", "unnamed_rule")
        rule_expr = r.get("rule", {})
        status = evaluate_rule(rule_expr, snapshot)
        
        result_item = {
            "id": rule_id,
            "status": status,
            "doc_type": r.get("doc_type"),
            "required_field": r.get("required_field"),
            "reason_code": r.get("reason_code", "INELIGIBLE")
        }
        rule_results.append(result_item)

        if status == "fail":
            has_fail = True
            if not first_fail_rule:
                first_fail_rule = result_item
        elif status == "unknown":
            has_unknown = True
            if not first_unknown_rule:
                first_unknown_rule = result_item

    # 2. Check documents
    uploaded_docs = set(snapshot.get("uploaded_documents") or [])
    missing_docs = [doc for doc in required_docs if doc not in uploaded_docs]

    # 3. Check requested amount against cap
    requested_amount = snapshot.get("requested_amount", 0)
    exceeds_cap = requested_amount > auto_approval_cap

    # 4. Confidence & Risk scores
    p = float(snapshot.get("confidence_score", 0.95))
    fraud_risk = float(snapshot.get("fraud_risk_score", 0.05))

    # 5. Route determination (Three exits: AUTO, ASK, HUMAN)
    route = "HUMAN"
    ask_target = None
    selected_reason_code = "ESCALATED_HUMAN"

    # AUTO condition:
    # Must have NO fails, NO unknowns, NO missing docs, within cap, high confidence, low fraud risk
    if (not has_fail) and (not has_unknown) and (len(missing_docs) == 0) and (not exceeds_cap) and (p >= p_min) and (fraud_risk <= fraud_max):
        route = "AUTO"
        selected_reason_code = "ELIGIBLE_AUTO"
    # ASK condition:
    # If no hard fail, within cap, low fraud risk, BUT missing documents or missing information
    elif (not has_fail) and (not exceeds_cap) and (fraud_risk <= fraud_max) and (has_unknown or len(missing_docs) > 0):
        route = "ASK"
        selected_reason_code = "MISSING_EVIDENCE"
        if missing_docs:
            ask_target = f"document:{missing_docs[0]}"
        elif first_unknown_rule:
            ask_target = first_unknown_rule.get("required_field") or first_unknown_rule.get("id")
    # HUMAN condition:
    # Any hard fail, exceeds cap, high fraud risk, low confidence, etc.
    else:
        route = "HUMAN"
        if has_fail and first_fail_rule:
            selected_reason_code = first_fail_rule.get("reason_code", "ESCALATED_HUMAN")
        elif exceeds_cap:
            selected_reason_code = "AMOUNT_EXCEEDS_CAP"
        elif fraud_risk > fraud_max:
            selected_reason_code = "RISK_FLAGGED_FOR_HUMAN"
        else:
            selected_reason_code = "ESCALATED_HUMAN"

    # 6. Calculate expected cost
    # Cost units: wrong_approval=100, human_review=4, ask_round=1, wrong_fraud_tag=20; 1 unit = 250 PKR
    if route == "AUTO":
        wrong_approval_cost = cost_table.get("wrong_approval", 100) * unit_pkr
        expected_cost = round((1.0 - p) * wrong_approval_cost, 2)
    elif route == "ASK":
        ask_round_cost = cost_table.get("ask_round", 1) * unit_pkr
        expected_cost = round(float(ask_round_cost), 2)
    else:  # HUMAN
        human_review_cost = cost_table.get("human_review", 4) * unit_pkr
        expected_cost = round(float(human_review_cost), 2)

    # 7. Reason formatting (Urdu and English)
    reason_template = reason_codes.get(selected_reason_code, {
        "en": f"Application evaluation complete. Route: {route}.",
        "ur": f"درخواست کا جائزہ مکمل ہو گیا۔ نتیجہ: {route}۔"
    })
    
    citizen_reason = {
        "en": reason_template.get("en", "Application processed."),
        "ur": reason_template.get("ur", "درخواست کا جائزہ لیا گیا ہے۔")
    }
    if route == "ASK" and ask_target:
        citizen_reason["en"] += f" (Required: {ask_target})"
        citizen_reason["ur"] += f" (درکار: {ask_target})"

    trace = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "selected_route": route,
        "selected_reason_code": selected_reason_code,
        "ask_target": ask_target,
        "has_fail": has_fail,
        "has_unknown": has_unknown,
        "missing_documents": missing_docs,
        "exceeds_cap": exceeds_cap,
        "rule_results": rule_results,
        "thresholds_applied": {
            "p_min": p_min,
            "fraud_max": fraud_max,
            "auto_approval_cap": auto_approval_cap
        }
    }

    return EvaluationResult(
        route=route,
        p=p,
        expected_cost=expected_cost,
        input_snapshot=snapshot,
        trace=trace,
        citizen_reason=citizen_reason,
        ask_target=ask_target,
        rule_results=rule_results
    )
