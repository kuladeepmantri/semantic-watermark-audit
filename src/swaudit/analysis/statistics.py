"""CPU statistics."""

import math
from typing import Any


def require(condition: bool, message: str) -> None:
    """Reject invalid input with a descriptive error."""
    if not condition:
        raise ValueError(message)


def binomial_cdf(k: int, n: int, p: float) -> float:
    """Compute P(X <= k) for a binomial random variable."""
    require(isinstance(n, int) and n >= 0 and (0 <= p <= 1), "Invalid binomial parameters")
    if k < 0:
        return 0.0
    if k >= n or p == 0:
        return 1.0
    if p == 1:
        return 0.0
    terms = (
        math.exp(
            math.lgamma(n + 1)
            - math.lgamma(i + 1)
            - math.lgamma(n - i + 1)
            + i * math.log(p)
            + (n - i) * math.log1p(-p)
        )
        for i in range(k + 1)
    )
    return min(1.0, math.fsum(terms))


def binomial_sf(k: int, n: int, p: float) -> float:
    """Compute P(X > k) for a binomial random variable."""
    return binomial_cdf(n - k - 1, n, 1 - p)


def exact_interval(k: Any, n: Any) -> Any:
    """Compute an exact two-sided binomial interval."""
    require(isinstance(k, int) and isinstance(n, int) and (0 <= k <= n), "Invalid interval counts")
    if n == 0:
        return None

    def invert(predicate: Any) -> Any:
        """Bisect a monotone predicate on the unit interval."""
        (lo, hi) = (0.0, 1.0)
        for _ in range(60):
            mid = (lo + hi) / 2
            if predicate(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else invert(lambda p: binomial_sf(k - 1, n, p) >= 0.025)
    upper = 1.0 if k == n else invert(lambda p: binomial_cdf(k, n, p) <= 0.025)
    return [lower, upper]


def paired(plain: Any, repaired: Any) -> Any:
    """Summarize paired binary outcomes."""
    require(len(plain) == len(repaired) and len(plain) > 0, "Invalid paired population")
    both = sum((p and r for (p, r) in zip(plain, repaired)))
    b = sum((p and (not r) for (p, r) in zip(plain, repaired)))
    c = sum((not p and r for (p, r) in zip(plain, repaired)))
    n = len(plain)
    pvalue = min(1.0, 2 * sum((math.comb(b + c, i) for i in range(min(b, c) + 1))) / 2 ** (b + c))
    return {
        "both_success": both,
        "plain_only": b,
        "repair_only": c,
        "neither_success": n - both - b - c,
        "n": n,
        "p_two_sided": pvalue,
        "paired_difference": (c - b) / n,
    }
