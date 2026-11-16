"""Reproduce used paper macros from the local release directory."""

import argparse
import collections
import difflib
import json
import math
import pathlib
from typing import Any

from swaudit.analysis.format_numbers import formatted
from swaudit.analysis.headline import attribution, build_master, extras, frontier, primary_sources
from swaudit.analysis.legacy_numbers import render as legacy_render
from swaudit.protocol import cutoff
from swaudit.recompute import BASE, read, require, verify_manifest
from swaudit.recompute import analyze as repair_analysis


def at(obj: Any, path: Any) -> Any:
    """Follow a sequence of keys through a nested record."""
    for key in path:
        obj = obj[key]
    return obj


def close(a: Any, b: Any) -> bool:
    """Compare scalars with the frozen binary64 tolerance."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return (
            math.isfinite(a) and math.isfinite(b) and (abs(a - b) <= 2e-12 * max(1, abs(a), abs(b)))
        )
    return a == b


def run() -> Any:
    """Recompute and check the saved numerical evidence."""
    verify_manifest()
    inventory = read("used-macros.json")
    expected = read("expected-all.json")["values"]
    (repair, _) = repair_analysis()
    (legacy, _) = legacy_render(
        read("legacy-number-sources.json"), read("legacy-number-values.json")
    )
    generated = {k: r["rendered"] for (k, r) in legacy.items()}
    generated.update(repair)
    (master, groups) = build_master()
    (front, searches) = frontier(groups)
    attr = attribution(groups)
    (held, theory, o6) = extras(groups)
    (locked, fresh, run6, predictions, honest) = primary_sources(groups)
    selectors = read("used-selectors.json")
    operands = read("audited-operands.json")["operands"]
    sources = selectors["sources"]
    agreements = read("agreement-aggregates.json")
    derived = {
        "paper/build/numbers/MASTER-TABLE.json": master,
        "paper/build/frontier/frontier-results.json": front,
        "research/audits/audit/independent_critique_recheck.json": attr,
        "paper/build/friends/results/AGREEMENT.json": agreements,
        "research/breakthrough/O6/execution/RESULTS.json": o6,
        "experiments/seal-csi/run-004-clean-baseline/RESULTS.json": dict(held_out=held),
    }
    derived.update(
        {
            "research/attack-lab/locked-test/results/results.json": locked,
            "research/attack-lab/fresh-replication/analysis/RESULT-FRESH-REPLICATION.json": fresh,
            "experiments/seal-csi/run-006-analysis/results.json": run6,
            "research/model-deep-dive/results/a6_run005_predictions.json": predictions,
            "paper/repro/data/expected.json": honest,
        }
    )
    policy = read("crosscheck-policy.json")
    expected_skips = {
        (r["macro"], r["source"], tuple(r["path"])) for r in policy["expected_unresolved_selectors"]
    }
    skipped = []
    replay_sources = set(policy["aggregate_replay_sources"])
    methods = {}
    verified = []
    aggregate = []
    for spec in selectors["records"]:
        values = []
        checks = 0
        for ref in spec["refs"]:
            old = operands[ref["key"]]["value"]
            src = sources[ref["source"]]["path"]
            require(
                src in derived
                or src in replay_sources
                or src.endswith("a4_verifiers_and_geometry.json"),
                "Undeclared crosscheck source: " + spec["macro"],
            )
            actual = None
            checked = False
            if src in derived and ref["path"]:
                try:
                    actual = at(derived[src], ref["path"])
                    checked = True
                except (KeyError, IndexError, TypeError):
                    require(
                        (spec["macro"], src, tuple(ref["path"])) in expected_skips,
                        "Unresolved derived selector: " + spec["macro"],
                    )
                    skipped.append(
                        dict(
                            macro=spec["macro"],
                            source=src,
                            path=ref["path"],
                            reason="Independently checked by headline components",
                        )
                    )
            if src == "research/model-deep-dive/results/a4_verifiers_and_geometry.json" and ref[
                "path"
            ] == ["honest_under_paper_analytic_threshold", "M_ge_79"]:
                actual = (
                    len(theory)
                    if spec["macro"].endswith("N")
                    else sum((r["M"] >= cutoff("theory_m") for r in theory))
                )
                checked = True
            if checked:
                require(close(actual, old), "Derived selector differs: " + spec["macro"])
                checks += 1
            values.append(old)
        op = spec.get("operation")
        value = (
            values
            if op == "fraction"
            else values[0] / values[1]
            if op == "ratio"
            else values[0] - values[1]
            if op == "subtract"
            else values[0]
        )
        generated[spec["macro"]] = formatted(value, spec)
        if spec["macro"].startswith("Friend"):
            methods[spec["macro"]] = "audited volunteer aggregate or screen definition replay"
            aggregate.append(spec["macro"])
        elif checks:
            methods[spec["macro"]] = (
                "row recount with numeric agreement check; original full-precision serialization retained"
            )
            verified.append(spec["macro"])
        elif spec.get("format") == "identifier":
            methods[spec["macro"]] = "source-bound identifier or code-line locator"
        else:
            methods[spec["macro"]] = "audited numeric selector or frozen configuration replay"
    require(
        {(r["macro"], r["source"], tuple(r["path"])) for r in skipped} == expected_skips,
        "Crosscheck exception set differs from the declared list",
    )
    require(
        set(policy["required_row_checked_macros"]) <= set(verified),
        "Previously row-checked macros lost their crosscheck",
    )
    for name in repair:
        methods[name] = "repair recount or explicit design/context record"
    mismatches = [
        dict(macro=n, expected=expected.get(n), actual=generated.get(n))
        for n in sorted(generated)
        if generated.get(n) != expected.get(n)
    ]
    outside_scope = sorted(set(inventory["used"]) - set(generated))
    used = set(inventory["used"]) & set(generated)
    uncovered = sorted(used - set(generated))
    used_mismatch = [r for r in mismatches if r["macro"] in used]
    report = dict(
        author="Kuladeep Mantri",
        status="PASS" if not mismatches and (not uncovered) else "FAIL",
        used_macros=len(used),
        checked=len(used & set(generated)),
        mismatches=len(mismatches),
        used_mismatches=len(used_mismatch),
        uncovered=uncovered,
        outside_crosscheck_scope=outside_scope,
        differences=mismatches,
        all_exported_macros_checked=len(generated),
        initial_coverage=inventory["initial_coverage"],
        crosscheck_exceptions=skipped,
        coverage_by_method=dict(
            collections.Counter((methods.get(n, "legacy numeric selector replay") for n in used))
        ),
        independent_row_checked_used_macros=len(set(verified) & used),
        volunteer_aggregate_macros=aggregate,
        headline_checks=dict(
            frontier_95=[
                front["targets"][r["index"]][r["fake_cohort"] + "_accepted"]
                for r in read("frontier-spec.json")["targets"]
                if r["honest_constraint"] == "both_jpeg_only" and r["target_count"] == 190
            ],
            local_honest=master["cells"]["primary"]["run005_clean"]["k"],
            local_consequential=[
                master["cells"]["primary"][g + "_consequential"]["k"] for g in ("run006", "fresh")
            ],
            strength_gated=[
                master["cells"]["primary_strength"][g + "_consequential"]["k"]
                for g in ("run006", "fresh")
            ],
            fresh_jpeg=[
                master["cells"][k]["fresh_jpeg75"]["k"] for k in ("primary", "primary_strength")
            ],
        ),
        frontier_searches=searches,
        limits=[
            "Volunteer alpha and fixed-panel bootstrap intervals replay audited aggregates; individual answers are withheld. The statistic is alpha, not kappa.",
            "Continuous AUC points are recomputed from scores; original audited bootstrap interval endpoints are replayed.",
            "Legacy model/drift quantities retain audited numeric source operands and methods; images, latent arrays and model measurements are not regenerated.",
            "Numeric source agreement tolerance is 2e-12 relative, with original serialized precision preserved; displayed macros must match exactly.",
            "Coverage concerns exported numeric/identifier macros in current manuscript sources. Literal author testimony, ethics statements and bibliographic locators are separate from computational results.",
        ],
        main_generated_file=inventory["main_generated_file"],
    )
    return (
        report,
        generated,
        dict(
            master=master,
            frontier=front,
            attribution=attr,
            coverage_methods={
                n: methods.get(n, "legacy numeric selector replay") for n in sorted(used)
            },
        ),
    )


def main() -> Any:
    """Run the command-line recount."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=pathlib.Path, required=True)
    args = ap.parse_args()
    out = args.output.resolve() if args.output else None
    if out:
        require(not out.is_relative_to(BASE), "Output must stay outside release")
    try:
        (report, generated, details) = run()
    except (ValueError, KeyError, AssertionError, OSError) as exc:
        report = dict(
            author="Kuladeep Mantri", status="FAIL", mismatches=None, uncovered=[], error=str(exc)
        )
        print(json.dumps(report, indent=2))
        raise SystemExit(1)
    out.mkdir(parents=True, exist_ok=True)
    used = read("used-macros.json")["used"]
    expected = read("expected-all.json")["values"]

    def tex(vals: Any) -> Any:
        """Format a numerical value for its TeX macro."""
        return (
            "% Generated for Kuladeep Mantri.\n"
            + "\n".join(
                ("\\newcommand{\\" + n + "}{" + vals[n] + "}" for n in sorted(used) if n in vals)
            )
            + "\n"
        )

    actual = tex(generated)
    target = tex(expected)
    (out / "numbers-used.tex").write_text(actual)
    (out / "numbers-used.diff").write_text(
        "".join(
            difflib.unified_diff(
                target.splitlines(True),
                actual.splitlines(True),
                fromfile="expected",
                tofile="recomputed",
            )
        )
    )
    (out / "RESULT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out / "DETAILS.json").write_text(json.dumps(details, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(report["status"] != "PASS")


if __name__ == "__main__":
    main()
