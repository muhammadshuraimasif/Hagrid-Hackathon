"""Evaluation Harness for Project Amaanat.

Executes deterministic evaluation over 3,000 synthetic cases:
- 40% train / 30% calibration / 30% test split.
- Non-parametric isotonic regression via PAVA.
- Risk-bounded threshold selection using exact Clopper-Pearson 95% confidence bounds.
- Comprehensive metric collection:
  - Wrong-approval rate with 95% Clopper-Pearson upper bound.
  - Expected cost per case across candidate taus.
  - Route mix (% AUTO, % ASK, % HUMAN).
  - Average ask rounds per case.
  - Reliability curve & Expected Calibration Error (ECE).
  - Fairness slices across channels and name variant groups (gap > 5 points flagged).
- Persistence into database eval_runs and eval_results.
"""
import math
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.generator import generate_synthetic_dataset
from api.decision_engine.clopper_pearson import clopper_pearson_upper_bound
from api.decision_engine.calibration import IsotonicCalibrator, select_optimal_tau
from api.decision_engine.policy import (
    PolicyInput,
    PolicyOutput,
    PolicyHardGuards,
    evaluate_decision_policy,
)


def compute_case_scores(case: Dict[str, Any]) -> Dict[str, Any]:
    """Computes deterministic component scores and raw c for a synthetic case."""
    # Identity score
    if case.get("identity_match_exact"):
        c_identity = 0.98
    elif case.get("category") == "name_variant":
        c_identity = 0.88
    else:
        c_identity = 0.50

    # Document score
    doc_clarity = case.get("doc_clarity", "clear")
    if doc_clarity == "clear":
        c_document = float(case.get("doc_authenticity", 0.98))
    elif doc_clarity == "blurry":
        c_document = 0.65
    elif doc_clarity == "forged":
        c_document = 0.25
    else:
        c_document = 0.10

    # Rules score: monthly_income <= 25000 and family_size >= 4
    income = case.get("monthly_income", 20000)
    fam_size = case.get("family_size", 5)
    rules_passed = (income <= 25000 and fam_size >= 4)
    c_rules = 1.0 if rules_passed else 0.40

    # Account score
    acc_match = bool(case.get("account_title_match", True))
    c_account = 0.98 if acc_match else 0.20

    # Fraud risk
    has_anomaly = bool(case.get("anomaly_flag", False))
    is_forged = (doc_clarity == "forged")
    if not acc_match or has_anomaly or is_forged:
        r_fraud = 0.85
    else:
        r_fraud = 0.02

    # Composite score
    min_comp = min(c_identity, c_document, c_rules, c_account)
    c = max(0.0, min(1.0, min_comp * (1.0 - r_fraud)))

    # Hard guards
    hard_guards = PolicyHardGuards(
        amount_within_cap=(case.get("claim_amount", 25000.0) <= 25000.0),
        identity_match_exact=bool(case.get("identity_match_exact", False)),
        no_duplicate_or_anomaly=not has_anomaly,
        all_required_fields_confirmed=True,
        no_rule_returned_unknown=bool(case.get("no_rule_unknown", True)),
        document_authenticity_above_limit=(c_document >= 0.80),
        account_title_matches_claimant=acc_match,
        account_not_newly_changed=True,
        rule_set_published=True,
        all_mock_services_healthy=bool(case.get("services_healthy", True)),
    )

    is_clean = bool(case.get("ground_truth_eligible") and not case.get("ground_truth_fraud"))

    return {
        **case,
        "c_identity": c_identity,
        "c_document": c_document,
        "c_rules": c_rules,
        "c_account": c_account,
        "r_fraud": r_fraud,
        "c": c,
        "hard_guards": hard_guards,
        "is_clean": is_clean,
    }


def compute_ece(probs: List[float], labels: List[int], n_bins: int = 10) -> Tuple[float, List[Dict[str, Any]]]:
    """Computes Expected Calibration Error (ECE) and reliability curve data across n bins."""
    ece = 0.0
    total = len(probs)
    curve = []

    for i in range(n_bins):
        low = i / float(n_bins)
        high = (i + 1) / float(n_bins)
        indices = [idx for idx, p in enumerate(probs) if low <= p < high or (i == n_bins - 1 and low <= p <= high)]
        count = len(indices)
        if count == 0:
            continue
        bin_conf = sum(probs[idx] for idx in indices) / count
        bin_acc = sum(labels[idx] for idx in indices) / count
        ece += (count / total) * abs(bin_acc - bin_conf)
        curve.append({
            "bin": f"[{low:.2f}, {high:.2f}]",
            "confidence": round(bin_conf, 4),
            "accuracy": round(bin_acc, 4),
            "count": count
        })

    return round(float(ece), 4), curve


def run_evaluation_harness(seed: int = 42) -> Dict[str, Any]:
    """Executes the complete evaluation benchmark and returns verifiable metrics."""
    # 1. Generate synthetic dataset
    cases, messages = generate_synthetic_dataset(seed=seed)
    scored_cases = [compute_case_scores(c) for c in cases]

    # 2. 40 / 30 / 30 Split (1,200 train, 900 calibration, 900 test)
    n_total = len(scored_cases)
    n_train = int(n_total * 0.40)       # 1,200
    n_calib = int(n_total * 0.30)       # 900
    train_set = scored_cases[:n_train]
    calib_set = scored_cases[n_train:n_train + n_calib]
    test_set = scored_cases[n_train + n_calib:]

    # 3. Fit Isotonic Calibrator on Train set
    train_scores = [c["c"] for c in train_set]
    train_labels = [1 if c["is_clean"] else 0 for c in train_set]
    calibrator = IsotonicCalibrator().fit(train_scores, train_labels)

    # Standard Rule Set Definition with Cost Model
    rule_set_def = {
        "parameters": {"max_grant_amount": 25000.0},
        "cost_table": {
            "unit_pkr": 250,
            "wrong_approval": 100,
            "human_review": 4,
            "ask_round": 1
        },
        "thresholds": {"auto_approval_p_min": 0.96},
        "reason_codes": {
            "ELIGIBLE_AUTO": {"en": "Eligible for auto approval", "ur": "خودکار منظوری کے اہل ہیں"},
            "MISSING_EVIDENCE": {"en": "Additional verification requested", "ur": "اضافی تصدیق درکار ہے"},
            "ESCALATED_HUMAN": {"en": "Escalated for officer review", "ur": "افسر کے جائزے کے لیے بھیج دیا گیا ہے"},
            "FRAUD_ACCOUNT_MISMATCH": {"en": "Account title mismatch", "ur": "اکاؤنٹ کا نام مماثل نہیں ہے"},
            "AUDIT_SAMPLE": {"en": "Random quality audit review", "ur": "معیار کے جائزے کا نمونہ"},
        }
    }

    # 4. Derive Optimal Tau on Calibration Set using 95% Clopper-Pearson bound <= 1%
    optimal_tau, calib_bound, calib_rate, calib_auto_count = select_optimal_tau(
        calibrator=calibrator,
        calibration_cases=calib_set,
        human_cost=4.0,
        wrong_approval_cost=100.0,
        target_wrong_rate_bound=0.01
    )

    # 5. Evaluate Test Set using Calibrated Policy
    test_results: List[Dict[str, Any]] = []
    routes = {"AUTO": 0, "ASK": 0, "HUMAN": 0}
    test_probs: List[float] = []
    test_labels: List[int] = []

    for t_case in test_set:
        pol_input = PolicyInput(
            c_identity=t_case["c_identity"],
            c_document=t_case["c_document"],
            c_rules=t_case["c_rules"],
            c_account=t_case["c_account"],
            r_fraud=t_case["r_fraud"],
            hard_guards=t_case["hard_guards"],
            ask_rounds_so_far=0,
            rule_set_def=rule_set_def,
            calibrator=calibrator,
            seed=seed,
            audit_sample_rate=0.05
        )
        pol_output = evaluate_decision_policy(pol_input)
        routes[pol_output.route] += 1
        test_probs.append(pol_output.p)
        test_labels.append(1 if t_case["is_clean"] else 0)

        test_results.append({
            "case_id": t_case["case_id"],
            "channel": t_case["channel"],
            "name_variant_group": t_case["name_variant_group"],
            "is_clean": t_case["is_clean"],
            "route": pol_output.route,
            "c": pol_output.c,
            "p": pol_output.p,
            "tau": pol_output.tau,
            "expected_cost": pol_output.expected_cost,
            "is_audit_sample": pol_output.is_audit_sample,
            "ask_target": pol_output.ask_target,
        })

    # Test Metrics Computation
    n_test = len(test_set)
    auto_cases = [r for r in test_results if r["route"] == "AUTO"]
    n_auto = len(auto_cases)
    wrong_auto = [r for r in auto_cases if not r["is_clean"]]
    k_wrong = len(wrong_auto)
    wrong_rate = (k_wrong / n_auto) if n_auto > 0 else 0.0

    test_cp_bound = clopper_pearson_upper_bound(k_wrong, n_auto, confidence=0.95)

    # Route percentages
    route_mix = {
        "AUTO_pct": round(routes["AUTO"] / n_test * 100.0, 2),
        "ASK_pct": round(routes["ASK"] / n_test * 100.0, 2),
        "HUMAN_pct": round(routes["HUMAN"] / n_test * 100.0, 2),
    }

    # Cost sweep over candidate taus in [0.90, 0.93, 0.96, 0.98, 0.99]
    cost_sweep = {}
    unit_pkr = 250
    wrong_cost = 100
    human_cost = 4
    ask_cost = 1

    for cand_tau in [0.90, 0.93, 0.96, 0.98, 0.99]:
        total_cost = 0.0
        for r in test_results:
            p_val = r["p"]
            # If auto eligible at cand_tau
            if p_val >= cand_tau and r["route"] != "ASK":
                # AUTO cost
                total_cost += (1.0 - p_val) * wrong_cost * unit_pkr
            elif r["route"] == "ASK":
                total_cost += ask_cost * unit_pkr
            else:
                total_cost += human_cost * unit_pkr
        cost_sweep[str(cand_tau)] = round(total_cost / n_test, 2)

    # Reliability curve and ECE
    ece_val, rel_curve = compute_ece(test_probs, test_labels, n_bins=10)

    # Average ask rounds (for cases routed to ASK, simulated 1 round)
    avg_ask_rounds = round(routes["ASK"] / n_test, 3)

    # Fairness Slices
    # 1. By Channel: self, helper, voice
    channel_metrics = {}
    channels = ["self", "helper", "voice"]
    for ch in channels:
        ch_cases = [r for r in test_results if r["channel"] == ch]
        n_ch = len(ch_cases)
        if n_ch == 0:
            continue
        human_cnt = sum(1 for r in ch_cases if r["route"] == "HUMAN")
        clean_ch = [r for r in ch_cases if r["is_clean"]]
        false_alarms = sum(1 for r in clean_ch if r["route"] == "HUMAN")
        channel_metrics[ch] = {
            "n": n_ch,
            "human_review_rate_pct": round(human_cnt / n_ch * 100.0, 2),
            "false_alarm_rate_pct": round(false_alarms / len(clean_ch) * 100.0, 2) if clean_ch else 0.0,
        }

    # 2. By Name Variant Group: standard vs transliteration_variant
    name_group_metrics = {}
    for grp in ["standard", "transliteration_variant"]:
        grp_cases = [r for r in test_results if r["name_variant_group"] == grp]
        n_grp = len(grp_cases)
        if n_grp == 0:
            continue
        human_cnt = sum(1 for r in grp_cases if r["route"] == "HUMAN")
        clean_grp = [r for r in grp_cases if r["is_clean"]]
        false_alarms = sum(1 for r in clean_grp if r["route"] == "HUMAN")
        name_group_metrics[grp] = {
            "n": n_grp,
            "human_review_rate_pct": round(human_cnt / n_grp * 100.0, 2),
            "false_alarm_rate_pct": round(false_alarms / len(clean_grp) * 100.0, 2) if clean_grp else 0.0,
        }

    # Fairness Gap Flags (> 5.0 percentage points)
    fairness_flags = []
    ch_rates = [v["human_review_rate_pct"] for v in channel_metrics.values()]
    if ch_rates and max(ch_rates) - min(ch_rates) > 5.0:
        fairness_flags.append({
            "dimension": "channel",
            "metric": "human_review_rate",
            "gap_points": round(max(ch_rates) - min(ch_rates), 2),
            "flagged": True,
            "note": "Human review disparity between channels exceeds 5 points"
        })

    grp_rates = [v["human_review_rate_pct"] for v in name_group_metrics.values()]
    if len(grp_rates) >= 2 and abs(grp_rates[0] - grp_rates[1]) > 5.0:
        fairness_flags.append({
            "dimension": "name_variant_group",
            "metric": "human_review_rate",
            "gap_points": round(abs(grp_rates[0] - grp_rates[1]), 2),
            "flagged": True,
            "note": "Name variant applicants routed to human review at higher rate due to transliteration guard"
        })

    return {
        "prototype": True,
        "seed": seed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_summary": {
            "total_cases": n_total,
            "train_cases": n_train,
            "calibration_cases": n_calib,
            "test_cases": n_test,
            "synthetic_messages": len(messages),
        },
        "optimal_tau": optimal_tau,
        "calibration": {
            "tau": optimal_tau,
            "auto_count": calib_auto_count,
            "wrong_approval_rate": round(calib_rate, 4),
            "clopper_pearson_95_upper_bound": round(calib_bound, 4),
            "target_bound_achieved": (calib_bound <= 0.01),
        },
        "test_evaluation": {
            "n_test": n_test,
            "n_auto": n_auto,
            "k_wrong_approvals": k_wrong,
            "measured_wrong_approval_rate": round(wrong_rate, 4),
            "clopper_pearson_95_upper_bound": round(test_cp_bound, 4),
            "sample_size_n": n_auto,
            "bound_le_1pct": (test_cp_bound <= 0.01),
            "route_mix": route_mix,
            "avg_ask_rounds": avg_ask_rounds,
            "expected_cost_per_case_sweep": cost_sweep,
            "expected_calibration_error": ece_val,
            "reliability_curve": rel_curve,
        },
        "fairness_analysis": {
            "by_channel": channel_metrics,
            "by_name_variant_group": name_group_metrics,
            "fairness_flags": fairness_flags,
        },
        "test_results_sample": test_results[:20],
    }


if __name__ == "__main__":
    import pprint
    res = run_evaluation_harness(seed=42)
    pprint.pprint({k: v for k, v in res.items() if k != "test_results_sample"})
