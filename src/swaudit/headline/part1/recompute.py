"""Recompute part 1 using only de-identified scalars.

Counts are the audited master-table aggregate k,n fields, not a raw-score
replay. Exact two-sided Clopper-Pearson bounds use the shared
binomial-tail inversion. Expected values never supply computed inputs.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any

from swaudit.analysis import statistics as stats
from swaudit.analysis.format_numbers import rounded
from swaudit.paths import RECORDS


def exact_interval(k: int, n: int, confidence_percent: float) -> list[float]:
    """Compute an exact interval at the component's declared confidence level."""
    if n <= 0:
        raise ValueError("Invalid binomial counts")
    return stats.exact_interval(k, n, confidence_percent=confidence_percent)


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
