"""Integrate release parts with the repair and legacy recounts."""

import argparse
import collections
import json
import pathlib
import subprocess
import sys
from typing import Any

from swaudit.analysis.legacy_numbers import render as legacy_render
from swaudit.recompute import BASE, read, require, verify_manifest
from swaudit.recompute import analyze as repair_analysis


def run_part(index: int) -> tuple[dict[str, str], dict[str, Any]]:
    """Run one headline component and validate its exported macro values."""
    path = pathlib.Path(__file__).parent / "headline" / ("part" + str(index)) / "recompute.py"
    require(path.is_file(), "Missing headline/part%d/recompute.py" % index)
    child = subprocess.run(
        [sys.executable, "-B", "-m", f"swaudit.headline.part{index}.recompute"],
        capture_output=True,
        text=True,
    )
    require(child.returncode == 0, "Headline part%d failed: " % index + child.stderr[-500:])
    try:
        result = json.loads(child.stdout)
    except ValueError:
        raise ValueError("Headline part%d did not emit JSON" % index)
    mismatches = result.get("mismatches")
    count = len(mismatches) if isinstance(mismatches, list) else mismatches
    require(count == 0, "Headline part%d reports mismatches" % index)
    numbers = result.get("rendered", result.get("values", result.get("numbers")))
    require(
        isinstance(numbers, dict) and numbers,
        "Headline part%d must return regenerated rendered macro values" % index,
    )
    values = {}
    for name, value in numbers.items():
        if isinstance(value, dict):
            value = value.get("rendered", value.get("actual"))
        require(
            isinstance(name, str) and isinstance(value, str),
            "Headline part%d returned invalid macro values" % index,
        )
        values[name] = value
    return (
        values,
        dict(checked=result.get("checked", len(values)), mismatches=0, macros=sorted(values)),
    )


def run(manuscript: pathlib.Path | None = None) -> Any:
    """Recompute and check the saved numerical evidence."""
    verify_manifest()
    inventory = read("used-macros.json")
    expected = read("expected-all.json")["values"]
    used = set(inventory["used"])
    (repairs, _) = repair_analysis()
    (legacy, _) = legacy_render(
        read("legacy-number-sources.json"), read("legacy-number-values.json")
    )
    generated = {n: r["rendered"] for (n, r) in legacy.items()}
    generated.update(repairs)
    required = set()
    for index in range(1, 5):
        component = json.loads((BASE / "headline" / f"part{index}" / "expected.json").read_text())
        required.update(r["macro"] for r in component["rows"]) if index == 2 else required.update(
            component
        )
    contributed = {}
    parts = {}
    for index in range(1, 5):
        (values, receipt) = run_part(index)
        parts["part" + str(index)] = receipt
        require(not set(values) & set(contributed), "Duplicate macro between headline parts")
        contributed.update(values)
    require(
        set(contributed) == required,
        "Headline component macro set differs from its declared comparison targets",
    )
    generated.update(contributed)
    from swaudit import round5, round6

    followup = round5.run()
    added, added_methods = round6.macros(generated, followup)
    require(not set(generated) & set(added), "Duplicate follow-up macro")
    generated.update(added)
    if manuscript is not None:
        from swaudit.inventory import collect

        current = collect(manuscript)
        used = set(current["used"])
        expected.update({n: current["values"][n] for n in used})
    mismatches = [
        dict(macro=n, expected=expected.get(n), actual=generated.get(n))
        for n in sorted(set(expected) | set(generated))
        if expected.get(n) != generated.get(n)
    ]
    uncovered = sorted(used - set(generated))
    from swaudit.analysis import headline_crosscheck

    (cross, _, details) = headline_crosscheck.run()
    require(cross["status"] == "PASS", "Independent headline crosscheck failed")
    report = dict(
        author="Kuladeep Mantri",
        status="PASS" if not mismatches and (not uncovered) else "FAIL",
        used_macros=len(used),
        checked=len(used & set(generated)),
        mismatches=len(mismatches),
        uncovered=uncovered,
        differences=mismatches,
        all_exported_macros_checked=len(generated),
        initial_coverage=inventory["initial_coverage"],
        headline_parts={
            name: dict(
                checked=r["checked"], mismatches=r["mismatches"], macro_count=len(r["macros"])
            )
            for (name, r) in parts.items()
        },
        independent_row_checked_used_macros=cross["independent_row_checked_used_macros"],
        coverage_by_method=dict(
            collections.Counter(
                added_methods.get(
                    n, details["coverage_methods"].get(n, "legacy numeric selector replay")
                )
                for n in used
            )
        ),
        crosscheck_exceptions=cross["crosscheck_exceptions"],
        round5=followup,
        followup_macros=len(added),
        used_macro_names=sorted(used),
        live_manuscript_checked=manuscript is not None,
        headline_checks=cross["headline_checks"],
        limits=cross["limits"],
        source_snapshot=dict(
            main_generated_definitions=inventory["main_generated_file"]["definitions"],
            main_missing_used_at_snapshot=len(inventory["main_generated_file"]["missing_used"]),
            full_generated_definitions=inventory["full_definition_file"]["definitions"],
        ),
    )
    return (report, generated, dict(parts=parts, independent_crosscheck=details))


def main() -> None:
    """Check the manuscript snapshot and added records, optionally exporting JSON and TeX."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument(
        "--manuscript",
        type=pathlib.Path,
        help="Check the current main TeX file and its input graph",
    )
    args = parser.parse_args()
    out = args.output.resolve() if args.output else None
    try:
        if out:
            require(not out.is_relative_to(BASE), "Output must stay outside records")
        (report, generated, details) = run(args.manuscript)
    except (ValueError, KeyError, AssertionError, OSError) as exc:
        print(json.dumps(dict(status="FAIL", error=str(exc))))
        raise SystemExit(1) from exc
    if out:
        out.mkdir(parents=True, exist_ok=True)
        if report["status"] != "PASS":
            (out / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report))
            raise SystemExit(1)
        used = report["used_macro_names"]

        def tex(names: list[str]) -> str:
            """Format a numerical value for its TeX macro."""
            return (
                "% Generated for Kuladeep Mantri.\n"
                + "\n".join(
                    ("\\newcommand{\\" + n + "}{" + generated[n] + "}" for n in sorted(names))
                )
                + "\n"
            )

        (out / "numbers-used.tex").write_text(tex(used))
        (out / "numbers-all.tex").write_text(tex(list(generated)))
        (out / "RESULT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        (out / "DETAILS.json").write_text(json.dumps(details, indent=2, sort_keys=True) + "\n")
        print(json.dumps(report, indent=2))
    else:
        print(
            f"{report['status']}: {report['checked']}/{report['used_macros']} manuscript macros; {report['mismatches']} mismatches; {len(report['uncovered'])} uncovered"
        )
        print(f"Exports checked: {report['all_exported_macros_checked']}")
        for name, values in report["round5"].items():
            for cohort, value in values.items():
                counts = value.get("accepted", {k: v for (k, v) in value.items() if k != "n"})
                print(
                    f"{name}/{cohort}: "
                    + ", ".join((f"{k}={v}/{value['n']}" for (k, v) in counts.items()))
                )
    raise SystemExit(report["status"] != "PASS")


if __name__ == "__main__":
    main()
