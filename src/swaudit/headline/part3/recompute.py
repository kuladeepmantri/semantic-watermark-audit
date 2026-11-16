"""Standalone stdlib recomputation part 3 release slice.

Alpha uses pooled class totals and off-diagonal coincidence mass from the
frozen analysis. Bootstrap rows are aggregate sufficient statistics for each
of its 10,000 frozen PCG64 resamples, with no per-item or per-rater labels.
CI endpoints use linear percentiles. Binomial intervals are exact two-sided
95% Clopper-Pearson, inverted directly through binomial probabilities.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any

from swaudit.analysis import statistics as stats
from swaudit.analysis.format_numbers import rounded
from swaudit.paths import RECORDS
from swaudit.protocol import cutoff

HERE = RECORDS / "headline/part3"


def alpha(counts: list[int], off: float) -> float:
    """Compute nominal agreement from pooled coincidence statistics."""
    n = sum(counts)
    denominator = n * n - sum((c * c for c in counts))
    if n <= 1 or denominator <= 0:
        raise ValueError("Undefined alpha replicate")
    return 1 - off * (n - 1) / denominator


def percentile(values: list[float], q: float) -> float:
    """Interpolate the requested quantile between sorted observations."""
    values = sorted(values)
    index = (len(values) - 1) * q
    lo = math.floor(index)
    hi = math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def exact95(k: int, n: int) -> list[float]:
    """Return the shared two-sided 95% binomial interval."""
    if n <= 0:
        raise ValueError("Invalid binomial counts")
    return stats.exact_interval(k, n)


def derive(data: Any) -> Any:
    """Derive agreement, interval and design quantities from aggregate records."""
    values = {name: rec["value"] for (name, rec) in data["design"].items()}
    if (
        data["auxiliary_design"]["strength_accept_minimum"]["value"] != cutoff("strength_min")
        or data["auxiliary_design"]["honest_match_minimum"]["value"] != cutoff("theory_m")
        or values["RunFourFailedMThreshold"] != cutoff("held_m")
        or values["RunFourFailedCThreshold"] != cutoff("held_c")
    ):
        raise ValueError("Component thresholds differ from protocol")
    panels = data["friend"]["panels"]
    for panel_name, prefix in [
        ("all_complete", "FriendAllCompleteFriends"),
        ("screened", "FriendScreenedFriends"),
    ]:
        for coding, suffix in [("binary", "Binary"), ("four_class", "FourClass")]:
            rec = panels[panel_name]["codings"][coding]
            values[prefix + suffix + "Alpha"] = alpha(rec["counts"], rec["off"])
            if panel_name == "screened":
                statistics = rec["bootstrap_sufficient_statistics"]
                if not len(statistics) == data["bootstrap"]["replicates"]:
                    raise ValueError(
                        "Data validation failed: len(statistics) == data['bootstrap']['replicates']"
                    )
                boot = [alpha(row[:-1], row[-1]) for row in statistics]
                values[prefix + suffix + "CILow"] = percentile(boot, 0.025)
                values[prefix + suffix + "CIHigh"] = percentile(boot, 0.975)
    repeats = data["friend"]["repeat_disagreement_histogram"]
    values["FriendCompleteReturns"] = sum(repeats.values())
    values["FriendExcludedByScreen"] = sum(
        (
            count
            for (disagreements, count) in repeats.items()
            if int(disagreements) > values["FriendMaxRepeatDisagreements"]
        )
    )
    values["FriendScreenedRetained"] = (
        values["FriendCompleteReturns"] - values["FriendExcludedByScreen"]
    )
    if not values["FriendCompleteReturns"] == panels["all_complete"]["raters"]:
        raise ValueError(
            "Data validation failed: values['FriendCompleteReturns'] == panels['all_complete']['raters']"
        )
    if not values["FriendScreenedRetained"] == panels["screened"]["raters"]:
        raise ValueError(
            "Data validation failed: values['FriendScreenedRetained'] == panels['screened']['raters']"
        )
    values["FriendSharedPairs"] = panels["screened"]["pairs"]
    for condition, suffix in [("clean", "Clean"), ("negative", "Unwatermarked")]:
        scores = data["run4_scores"][condition]
        k = sum(
            (
                m > values["RunFourFailedMThreshold"] and c >= values["RunFourFailedCThreshold"]
                for (m, c) in scores
            )
        )
        values["RunFourFailed" + suffix + "Fraction"] = [k, len(scores)]
        values["RunFourFailed" + suffix + "N"] = len(scores)
    if not values["CalibrationTargetPass"] == math.ceil(
        values["CalibrationCleanRateTargetPercent"] * values["CalibrationTargetN"]
    ):
        raise ValueError(
            "Data validation failed: values['CalibrationTargetPass'] == math.ceil(values['CalibrationCleanRateTargetPercent'] * values['CalibrationTargetN'])"
        )
    scores = data["jpeg_strength_scores"]
    k = sum((s < data["auxiliary_design"]["strength_accept_minimum"]["value"] for s in scores))
    values["FreshJpegOurStrengthRejectedN"] = len(scores)
    values["FreshJpegOurStrengthRejectedPercent"] = k / len(scores)
    (low, high) = exact95(k, len(scores))
    values["FreshJpegOurStrengthRejectedCILowPercent"] = low
    values["FreshJpegOurStrengthRejectedCIHighPercent"] = high
    values["TheoryCutoffHonestN"] = len(data["honest_match_scores"])
    values["TheoryCutoffHonestPass"] = sum(
        (
            m >= data["auxiliary_design"]["honest_match_minimum"]["value"]
            for m in data["honest_match_scores"]
        )
    )
    return values


def render(name: Any, value: Any) -> Any:
    """Render recorded numerical operands for comparison."""
    if isinstance(value, list):
        return "/".join((str(x) for x in value))
    if name.startswith("FreshJpeg") and name.endswith("Percent"):
        return rounded(value, 2, scale=100) + "\\%"
    if name.endswith("Percent"):
        return rounded(value, 0, scale=100) + "\\%"
    if "Alpha" in name or name.endswith(("CILow", "CIHigh")):
        return rounded(value, 3)
    return str(int(value))


def matches(actual: Any, expected: Any) -> Any:
    """Compare reconstructed values using the declared numerical tolerance."""
    if isinstance(expected, list):
        return isinstance(actual, list) and actual == expected
    return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def main() -> Any:
    """Run the command-line recount."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = json.loads((HERE / "data.json").read_text())
    expected = json.loads((HERE / "expected.json").read_text())
    values = derive(data)
    rendered = {name: render(name, values[name]) for name in expected}
    mismatches = []
    for name, target in expected.items():
        if not matches(values[name], target["value"]):
            mismatches.append({"macro": name, "actual": values[name], "expected": target["value"]})
        if rendered[name] != target["rendered"]:
            mismatches.append(
                {
                    "macro": name,
                    "actual_rendered": rendered[name],
                    "expected_rendered": target["rendered"],
                }
            )
    if not set(values) == set(expected):
        raise ValueError("Data validation failed: set(values) == set(expected)")
    result = {"checked": len(expected), "mismatches": mismatches, "rendered": rendered}
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded)
    print(encoded, end="")
    raise SystemExit(bool(mismatches))


if __name__ == "__main__":
    main()
