"""Clopper-Pearson exact binomial confidence interval calculator.

Follows Section 8.2 of docs/BLUEPRINT.md.
Implements exact bisection on the Binomial CDF to derive the 95% upper confidence bound
on wrong-approval rate, with zero external dependencies and exact analytical edge cases.
"""
import math

def binomial_cdf(k: int, n: int, p: float) -> float:
    """Calculates P(X <= k) for X ~ Binomial(n, p)."""
    if k >= n:
        return 1.0
    if k < 0:
        return 0.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0

    # Summing terms in log-space for numerical stability
    total_prob = 0.0
    log_p = math.log(p)
    log_1_minus_p = math.log(1.0 - p)

    for i in range(k + 1):
        # log(comb(n, i)) + i*log(p) + (n-i)*log(1-p)
        log_comb = math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
        log_term = log_comb + (i * log_p) + ((n - i) * log_1_minus_p)
        total_prob += math.exp(log_term)

    return min(1.0, max(0.0, total_prob))


def clopper_pearson_upper_bound(k: int, n: int, confidence: float = 0.95) -> float:
    """Computes the Clopper-Pearson exact upper confidence bound.
    
    For k errors out of n trials at confidence level (default 0.95):
    - Solves P(X <= k; n, p_upper) = 1 - confidence (alpha = 0.05).
    - For k=0, solves (1 - p)^n = alpha => p_upper = 1 - alpha^(1/n).
      e.g., k=0, n=300, conf=0.95 => 1 - 0.05^(1/300) ~= 0.009939 (~0.0099).
    """
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    if k < 0:
        k = 0

    alpha = 1.0 - confidence

    # Analytical solution for k = 0
    if k == 0:
        return 1.0 - math.pow(alpha, 1.0 / n)

    # Bisection search on [0.0, 1.0]
    low = 0.0
    high = 1.0
    tol = 1e-8

    for _ in range(60):
        mid = (low + high) / 2.0
        # binomial_cdf(k, n, p) decreases as p increases
        prob = binomial_cdf(k, n, mid)
        if prob > alpha:
            # mid is too small (prob is too high), increase mid
            low = mid
        else:
            high = mid
        if (high - low) < tol:
            break

    return (low + high) / 2.0
