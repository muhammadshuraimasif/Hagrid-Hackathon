"""Isotonic Calibration & Optimal Tau derivation using Clopper-Pearson risk bounds.

Follows docs/BLUEPRINT.md section 8.2 and 8.3.
Implements the Pool Adjacent Violators Algorithm (PAVA) for isotonic regression
mapping raw composite score c to calibrated probability p, ensuring monotonicity.
"""
from typing import List, Tuple, Dict, Any, Optional
from api.decision_engine.clopper_pearson import clopper_pearson_upper_bound


class IsotonicCalibrator:
    """Non-parametric isotonic calibrator fitted via Pool Adjacent Violators Algorithm (PAVA)."""

    def __init__(self, breakpoints: Optional[List[Tuple[float, float]]] = None):
        # List of (c_threshold, p_calibrated) sorted by c_threshold
        self.breakpoints: List[Tuple[float, float]] = breakpoints or [(0.0, 0.0), (1.0, 1.0)]

    def fit(self, scores: List[float], labels: List[int]) -> "IsotonicCalibrator":
        """Fits isotonic regression on training data (scores, binary labels 0 or 1)."""
        if len(scores) == 0:
            self.breakpoints = [(0.0, 0.0), (1.0, 1.0)]
            return self

        # Pair and sort by score ascending
        paired = sorted(zip(scores, labels), key=lambda x: x[0])
        
        # PAVA algorithm
        # Each block: [weight, sum_labels, mean_label, min_score, max_score]
        blocks = []
        for s, y in paired:
            blocks.append([1.0, float(y), float(y), s, s])
            # Merge while monotonicity violated: mean of previous > mean of current
            while len(blocks) >= 2 and blocks[-2][2] > blocks[-1][2]:
                b2 = blocks.pop()
                b1 = blocks.pop()
                new_w = b1[0] + b2[0]
                new_sum = b1[1] + b2[1]
                new_mean = new_sum / new_w
                new_min_s = b1[3]
                new_max_s = b2[4]
                blocks.append([new_w, new_sum, new_mean, new_min_s, new_max_s])

        # Extract breakpoints
        bp = [(0.0, max(0.0, min(1.0, blocks[0][2])))]
        for b in blocks:
            c_val = b[4]
            p_val = max(0.0, min(1.0, b[2]))
            bp.append((c_val, p_val))

        if bp[-1][0] < 1.0:
            bp.append((1.0, bp[-1][1]))

        # Remove duplicate x entries
        clean_bp = []
        for x, y in bp:
            if not clean_bp or x > clean_bp[-1][0]:
                clean_bp.append((x, y))
            else:
                # Same x, take latest monotonic y
                clean_bp[-1] = (x, max(clean_bp[-1][1], y))

        self.breakpoints = clean_bp
        return self

    def calibrate(self, c: float) -> float:
        """Interpolates calibrated probability p for raw score c."""
        c = max(0.0, min(1.0, float(c)))
        if c <= self.breakpoints[0][0]:
            return self.breakpoints[0][1]
        if c >= self.breakpoints[-1][0]:
            return self.breakpoints[-1][1]

        # Piecewise linear interpolation
        for i in range(len(self.breakpoints) - 1):
            x1, y1 = self.breakpoints[i]
            x2, y2 = self.breakpoints[i + 1]
            if x1 <= c <= x2:
                if x2 == x1:
                    return y1
                slope = (y2 - y1) / (x2 - x1)
                p = y1 + slope * (c - x1)
                return max(0.0, min(1.0, float(p)))

        return self.breakpoints[-1][1]

    def to_dict(self) -> Dict[str, Any]:
        return {"breakpoints": self.breakpoints}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IsotonicCalibrator":
        return cls(breakpoints=data.get("breakpoints"))


def select_optimal_tau(
    calibrator: IsotonicCalibrator,
    calibration_cases: List[Dict[str, Any]],
    human_cost: float = 4.0,
    wrong_approval_cost: float = 100.0,
    target_wrong_rate_bound: float = 0.01,
) -> Tuple[float, float, float, int]:
    """Derives optimal tau satisfying cost break-even and Clopper-Pearson 95% risk bound.
    
    Returns:
        (tau_chosen, cp_upper_bound, wrong_approval_rate, auto_count)
    """
    # 1. Base break-even threshold from cost table
    tau_break_even = 1.0 - (human_cost / wrong_approval_cost)  # e.g., 0.96

    # Score all calibration cases: case has 'c' and 'is_clean_eligible' (ground truth)
    scored = []
    for case in calibration_cases:
        c = case["c"]
        p = calibrator.calibrate(c)
        is_eligible = bool(case.get("ground_truth_eligible", False))
        is_fraud = bool(case.get("ground_truth_fraud", False))
        is_clean = is_eligible and not is_fraud
        scored.append({"c": c, "p": p, "is_clean": is_clean})

    # Test candidate thresholds starting from break-even upwards
    candidate_taus = [
        round(tau_break_even + i * (0.995 - tau_break_even) / 29.0, 4)
        for i in range(30)
    ]

    best_tau = candidate_taus[-1]
    best_bound = 1.0
    best_rate = 1.0
    best_n = 0

    for tau in candidate_taus:
        # Cases auto-approved at this threshold (p >= tau)
        auto_cases = [c for c in scored if c["p"] >= tau]
        n_auto = len(auto_cases)
        if n_auto == 0:
            continue

        wrong_count = sum(1 for c in auto_cases if not c["is_clean"])
        rate = wrong_count / n_auto
        bound = clopper_pearson_upper_bound(wrong_count, n_auto, confidence=0.95)

        # We want the lowest tau that achieves bound <= target_wrong_rate_bound
        if bound <= target_wrong_rate_bound:
            return tau, bound, rate, n_auto

        # Track the lowest bound achieved
        if bound < best_bound:
            best_bound = bound
            best_tau = tau
            best_rate = rate
            best_n = n_auto

    # If bound cannot be strictly met under 1%, return safest tau and honest bound
    return best_tau, best_bound, best_rate, best_n
