"""Frozen analysis functions. File loaders omitted."""

import hashlib
import math
from typing import Any

from swaudit.protocol import cutoff

C1 = [f"C{i:03d}" for i in range(100, 140)]


def require(ok: bool, message: str) -> None:
    """Reject invalid input with a descriptive error."""
    if not ok:
        raise ValueError(message)


def digest(text: str) -> str:
    """Hash UTF-8 text with SHA256 for deterministic tie breaking."""
    return hashlib.sha256(text.encode()).hexdigest()


def p20(row: dict[str, Any]) -> bool:
    """Apply the readability and mismatch acceptance rule."""
    (r, m) = (row["readable"], row["mismatch"])
    require(type(r) is int and 0 <= r <= cutoff("payload_patches"), "Invalid readable count")
    require(m is None or type(m) in (int, float), "Invalid mismatch type")
    return (
        r >= cutoff("readable_floor")
        and m is not None
        and math.isfinite(m)
        and (0 <= m <= cutoff("mismatch_cutoff"))
    )


def scalar_rules(row: Any, boundary: Any, experiment: Any) -> Any:
    """Recompute the payload, count and local full-rule decisions."""
    (m, c, n) = (row["M"], row["C_corrected" if experiment == 1 else "C"], row["N_any"])
    require(
        all((type(v) in (int, float) and math.isfinite(v) for v in (m, c, n))),
        "Invalid scalar score",
    )
    require(type(n) is int and 0 <= n <= 1024, "Invalid strength count")
    h = row["image_sha256"]
    require(len(h) == 64 and all((x in "0123456789abcdef" for x in h)), "Invalid image hash")
    prefix = "exp1-strength-tie-v1:" if experiment == 1 else "exp2-strength-tie-v2:"
    if experiment == 1:
        matched = n > boundary["count"] or (
            n == boundary["count"] and digest(prefix + h) <= boundary["tie_hash"]
        )
    else:
        matched = n > boundary["score"] or (
            n == boundary["score"]
            and (digest(prefix + h), h) <= (boundary["tie"], boundary["image_sha256"])
        )
    p = p20(row)
    local = m > cutoff("local_m") and c >= cutoff("local_c") and (n >= cutoff("strength_min"))
    result = dict(
        payload=p,
        published_count=m > cutoff("published_m"),
        local_full=local,
        matched_strength=matched,
        payload_full=p and local,
    )
    aliases = (
        dict(payload="P20", published_count="paper_count", payload_full="P20_local_full")
        if experiment == 2
        else dict(payload_full="payload_full")
    )
    for key, value in result.items():
        require(
            type(row["decisions"][aliases.get(key, key)]) is bool
            and row["decisions"][aliases.get(key, key)] == value,
            "Saved decision differs from raw fields: " + key,
        )
    if experiment == 2:
        require(type(row["accept"]) is bool and row["accept"] == p, "Saved P20 differs")
    return result


def full_boundary(rows: Any, k: Any) -> Any:
    """Fit the matched full-rule cutoff on the fixed calibration cohort."""
    require(
        len(rows) == 40 and {r["reference"] for r in rows} == set(C1), "Wrong A5 calibration cohort"
    )
    require(
        type(k) is int and 30 <= k <= 40 and (sum((p20(r) for r in rows)) == k), "Wrong A5 target"
    )
    require(len({r["image_sha256"] for r in rows}) == 40, "Duplicate calibration image")
    eligible = [
        r for r in rows if r["M"] > cutoff("local_m") and r["C_corrected"] >= cutoff("local_c")
    ]
    eligible.sort(key=lambda r: (-r["N_any"], digest("exp1-fullrule-tie-v1:" + r["image_sha256"])))
    short = len(eligible) < k
    boundary = dict(
        target_k=k,
        calibration_n=40,
        MC_passers=len(eligible),
        unreachable=short,
        strength_accept_all=short,
        count=None if short else eligible[k - 1]["N_any"],
        tie_hash=None
        if short
        else digest("exp1-fullrule-tie-v1:" + eligible[k - 1]["image_sha256"]),
        calibration_kept=len(eligible) if short else k,
        retention_shortfall=max(0, k - len(eligible)),
    )
    require(
        sum((matched_full(r, boundary) for r in rows)) == boundary["calibration_kept"],
        "A5 calibration self-check failed",
    )
    return boundary


def matched_full(row: dict[str, Any], boundary: dict[str, Any]) -> bool:
    """Evaluate the calibrated count cutoff and its deterministic tie break."""
    return (
        row["M"] > cutoff("local_m")
        and row["C_corrected"] >= cutoff("local_c")
        and (
            boundary["strength_accept_all"]
            or row["N_any"] > boundary["count"]
            or (
                row["N_any"] == boundary["count"]
                and digest("exp1-fullrule-tie-v1:" + row["image_sha256"]) <= boundary["tie_hash"]
            )
        )
    )
