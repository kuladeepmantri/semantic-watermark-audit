"""Recompute part 4 from de-identified scalar evidence.

Run with Python's standard library only. Source hashes were verified during
extraction. This replay checks scalar arithmetic, not latent reconstruction.
"""

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

from swaudit.paths import RECORDS
from swaudit.protocol import cutoff, protocol


def binomial_sf(cutoff: int, n: int, p: float) -> float:
    """P(X > cutoff), evaluating the short lower tail by recurrence."""
    if p == 1:
        return float(n > cutoff)
    if p == 0:
        return 0.0
    term = math.exp(n * math.log1p(-p))
    terms = [term]
    for k in range(cutoff):
        term *= (n - k) / (k + 1) * p / (1 - p)
        terms.append(term)
    return max(0.0, min(1.0, 1.0 - math.fsum(terms)))


def auc(honest: Any, null: Any) -> Any:
    """Compute pairwise ROC-AUC, giving ties half credit."""
    return sum(((h > z) + 0.5 * (h == z) for h in honest for z in null)) / (len(honest) * len(null))


def recompute(data: Any) -> Any:
    """Regenerate the component values and compare frozen targets."""
    values = {k: v["value"] for (k, v) in data["constants"].items()}
    for macro, item in data["provenance"].items():
        values[macro] = (
            str(item["line_count_before_anchor"] + 1)
            if item["tag"] == "source_location"
            else item["value"]
        )
    limits = protocol()["prediction_checks"]
    (H, Z) = (data["honest"], data["unwatermarked"])
    (n, bits) = (data["model_design"]["patch_count"], data["model_design"]["bits"])

    def rho(h):
        return (1 - h["theta"] / 180.0) ** bits

    predicted = {
        m: sum((binomial_sf(m, n, rho(h) * h["oracle"] / n) for h in H))
        for m in (cutoff("local_m"), cutoff("published_m"))
    }
    observed = {m: sum((h["M"] > m for h in H)) for m in (cutoff("local_m"), cutoff("published_m"))}
    zscores = [
        (h["retained"] - n * rho(h)) / math.sqrt(max(n * rho(h) * (1 - rho(h)), 1e-09))
        for h in H
        if h["theta"] > limits["angle_min"]
    ]
    hp = sum((h["N_margin"] >= cutoff("margin_min") for h in H))
    zp = sum((z["N_margin"] >= cutoff("margin_min") for z in Z))
    hp2 = sum((h["N_any"] >= cutoff("strength_min") for h in H))
    zp2 = sum((z["N_any"] >= cutoff("strength_min") for z in Z))
    rmse = math.sqrt(sum(((h["theta_hat"] - h["theta"]) ** 2 for h in H)) / len(H))
    released_auc = auc([h["C_released"] for h in H], [z["C_released"] for z in Z])
    primary_h = sum(
        (h["M"] > cutoff("local_m") and h["C_corrected"] >= cutoff("local_c") for h in H)
    )
    primary_z = sum(
        (z["M"] > cutoff("local_m") and z["C_corrected"] >= cutoff("local_c") for z in Z)
    )
    confirmations = [
        all(
            (
                abs(observed[m] - predicted[m]) <= limits["count_error_max"]
                for m in (cutoff("local_m"), cutoff("published_m"))
            )
        ),
        limits["z_sd_range"][0] <= statistics.stdev(zscores) <= limits["z_sd_range"][1],
        min((h["N_margin"] for h in H)) > max((z["N_margin"] for z in Z)),
        limits["strength_honest_range"][0] <= hp <= limits["strength_honest_range"][1]
        and zp <= limits["strength_null_max"]
        and limits["strength_honest_range"][0] <= hp2 <= limits["strength_honest_range"][1]
        and zp2 <= limits["strength_null_max"],
        rmse < limits["angle_rmse_max"],
        statistics.median((z["C_corrected"] for z in Z))
        - statistics.median((h["C_corrected"] for h in H))
        >= limits["spatial_median_gap_min"],
        limits["released_auc_range"][0] <= released_auc <= limits["released_auc_range"][1],
        limits["primary_honest_range"][0] <= primary_h <= limits["primary_honest_range"][1]
        and primary_z <= limits["primary_null_max"],
    ]
    prefix = "RunFivePredictions"
    values.update(
        {
            prefix + "ConfirmedCount": sum(confirmations),
            prefix + "NHonest": len(H),
            prefix + "NUnwatermarked": len(Z),
        }
    )
    for m, word in [(cutoff("local_m"), "Three"), (cutoff("published_m"), "OneTwo")]:
        values[prefix + "POneMGt" + word + "Observed"] = observed[m]
        values[prefix + "POneMGt" + word + "Predicted"] = predicted[m]
    return values


def tex(macro: Any, value: Any) -> Any:
    """Format a numerical value for its TeX macro."""
    if macro.endswith("Short"):
        return str(value)[:8]
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def main() -> Any:
    """Run the command-line recount."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = RECORDS / "headline/part4"
    data = json.loads((base / "data.json").read_text())
    expected = json.loads((base / "expected.json").read_text())
    values = recompute(data)
    display_values = dict(values)
    for macro, scalar in data["prediction_serialization"].items():
        if math.isclose(values[macro], scalar, rel_tol=0.0, abs_tol=1e-12):
            display_values[macro] = scalar
    rendered = {macro: tex(macro, value) for (macro, value) in display_values.items()}
    mismatches = []
    for macro, target in expected.items():
        value = values.get(macro)
        same = (
            math.isclose(value, target["value"], rel_tol=1e-13, abs_tol=1e-12)
            if isinstance(value, (int, float)) and isinstance(target["value"], (int, float))
            else value == target["value"]
        )
        if not same or rendered.get(macro) != target["rendered"]:
            mismatches.append(
                {
                    "macro": macro,
                    "actual": value,
                    "expected": target["value"],
                    "rendered": rendered.get(macro),
                    "expected_rendered": target["rendered"],
                }
            )
    result = {"checked": len(expected), "mismatches": mismatches, "rendered": rendered}
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload)
    print(payload, end="")
    return bool(mismatches)


if __name__ == "__main__":
    raise SystemExit(main())
