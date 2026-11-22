"""Anomaly Rules for Fraud Risk Scoring.

Follows docs/BLUEPRINT.md section 8.3 and AGENTS.md:
- Pure logic rules evaluating:
  1. Repeat CNIC submission
  2. Single bank account used across multiple disparate CNICs
  3. Burst of claims from one client_uuid / device within short time window
  4. Odd hours submissions (2 AM to 5 AM)
- Helper devices / agent roles are explicitly EXEMPT from the one-device rule.
- A flag strictly routes to HUMAN with a fraud tag; NEVER auto-rejects or blocks.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def evaluate_anomalies(
    case_data: Dict[str, Any],
    recent_cases: List[Dict[str, Any]],
    is_helper_device: bool = False
) -> Tuple[float, List[str]]:
    """Evaluates rule-based anomaly risk.
    
    Returns:
        (r_fraud_score, list_of_anomaly_flags)
    """
    flags = []
    r_fraud = 0.02  # Baseline low fraud prior

    cnic = case_data.get("cnic")
    account = (case_data.get("account_number") or case_data.get("iban") or "").strip().upper()
    client_uuid = case_data.get("client_uuid") or case_data.get("device_id")

    # 1. Repeat CNIC check
    if cnic:
        matching_cnics = [c for c in recent_cases if c.get("cnic") == cnic and c.get("case_id") != case_data.get("case_id")]
        if matching_cnics:
            flags.append("REPEAT_CNIC: Multiple active claims filed under identical CNIC")
            r_fraud = max(r_fraud, 0.85)

    # 2. Account Shared Across Multiple Different CNICs
    if account:
        diff_cnic_same_acc = [
            c for c in recent_cases
            if (c.get("account_number") or c.get("iban") or "").strip().upper() == account
            and c.get("cnic") != cnic
        ]
        if len(diff_cnic_same_acc) >= 2:
            flags.append(f"SHARED_ACCOUNT: Disbursement account {account} is linked to multiple different CNICs")
            r_fraud = max(r_fraud, 0.80)

    # 3. Burst from Single Device (Exempting Helper Agents)
    if client_uuid and not is_helper_device:
        device_burst = [
            c for c in recent_cases
            if (c.get("client_uuid") or c.get("device_id")) == client_uuid
            and c.get("case_id") != case_data.get("case_id")
        ]
        if len(device_burst) >= 4:
            flags.append(f"DEVICE_BURST: {len(device_burst)} claims registered from same unverified device")
            r_fraud = max(r_fraud, 0.75)

    # 4. Odd Hours Submission (between 2 AM and 5 AM local time)
    created_at = case_data.get("created_at") or datetime.now(timezone.utc)
    if isinstance(created_at, datetime):
        # 2:00 to 4:59 AM
        if 2 <= created_at.hour <= 4:
            flags.append("ODD_HOURS_SUBMISSION: Claim submitted during unusual low-activity nocturnal window")
            r_fraud = max(r_fraud, 0.25)

    return round(r_fraud, 3), flags
