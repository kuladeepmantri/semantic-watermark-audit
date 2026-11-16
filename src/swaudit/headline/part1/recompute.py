"""Recompute part 1 using only de-identified scalars.

Counts are the audited master-table aggregate k,n fields, not a raw-score
replay. Exact two-sided Clopper-Pearson bounds use the source's 64-step
binomial-tail inversion. Expected values never supply computed inputs.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any

from swaudit.analysis.format_numbers import rounded
from swaudit.paths import RECORDS


def exact_interval(k: Any, n: Any, confidence_percent: Any) -> Any:
    """Compute an exact two-sided binomial interval."""
    if not isinstance(k, int) or not isinstance(n, int) or (not 0 <= k <= n) or (n <= 0):
        raise ValueError("Invalid binomial counts")
    tail_probability = (1 - confidence_percent / 100) / 2

    def solve(tail: Any, increasing: Any) -> Any:
        """Find the probability matching the requested tail mass."""
        (lo, hi) = (0.0, 1.0)
        for _ in range(64):
            mid = (lo + hi) / 2
            if (tail(mid) < tail_probability) == increasing:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def mass(i: Any, p: Any) -> Any:
        """Evaluate the binomial tail at a candidate probability."""
        return math.comb(n, i) * p**i * (1 - p) ** (n - i)

    lower = 0.0 if k == 0 else solve(lambda p: sum((mass(i, p) for i in range(k, n + 1))), True)
    upper = 1.0 if k == n else solve(lambda p: sum((mass(i, p) for i in range(k + 1))), False)
    return [lower, upper]


def recompute(data: Any, expected: Any) -> Any:
    """Regenerate the component values and compare frozen targets."""
    (mismatches, rendered) = ([], {})
    specs = data["macros"]
    confidence = data["design"]["confidence_percent"]["value"]
    if set(specs) != set(expected):
        mismatches.append({"error": "Macro coverage differs"})
    for macro, spec in specs.items():
        operation = spec["operation"]
        if operation == "design":
            value = data["design"][spec["constant"]]["value"]
            tex = rounded(value, 0, percent=True)
        elif operation == "naturalness":
            naturalness = data["naturalness"]
            value = (
                naturalness["total"]
                if spec["field"] == "total"
                else naturalness["total"] - naturalness["missing"]
            )
            tex = str(value)
        else:
            cell = data["cells"][spec["cell"]]
            (k, n) = (cell["k"], cell["n"])
            if operation == "fraction":
                value = [k, n]
                tex = f"{k}/{n}"
            elif operation == "ci":
                value = exact_interval(k, n, confidence)[spec["bound"]]
                tex = rounded(value, 2, scale=100) + "\\%"
            else:
                raise ValueError("Unknown operation: " + operation)
        rendered[macro] = tex
        target = expected.get(macro, {})
        target_value = target.get("value")
        equal = (
            math.isclose(value, target_value, rel_tol=0, abs_tol=1e-12)
            if isinstance(value, (int, float)) and isinstance(target_value, (int, float))
            else value == target_value
        )
        if not equal or tex != target.get("rendered"):
            mismatches.append(
                {
                    "macro": macro,
                    "computed": value,
                    "expected": target_value,
                    "rendered": tex,
                    "expected_rendered": target.get("rendered"),
                }
            )
    return {"checked": len(specs), "mismatches": mismatches, "rendered": rendered}


def main() -> Any:
    """Run the command-line recount."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the same JSON printed to stdout")
    args = parser.parse_args()
    here = RECORDS / "headline/part1"
    data = json.loads((here / "data.json").read_text())
    expected = json.loads((here / "expected.json").read_text())
    result = recompute(data, expected)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")
    return bool(result["mismatches"])


if __name__ == "__main__":
    raise SystemExit(main())
