"""Recount fixed-cohort acceptance from saved scalar records."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any

from swaudit.analysis.frozen_rules import p20
from swaudit.paths import RECORDS
from swaudit.protocol import cutoff
from swaudit.recompute import require, unique

Row = dict[str, Any]


def load(name: str) -> Row:
    """Read one bundled round-five record."""
    return json.loads((RECORDS / "round5" / f"{name}.json").read_text())


def scalar(row: Row, key: str, upper: float) -> float:
    """Validate a finite, nonnegative score before applying a cutoff."""
    value = row[key]
    require(
        type(value) in (int, float) and math.isfinite(value) and (0 <= value <= upper),
        f"Invalid scalar: {key}",
    )
    return value


def whitebox(rows: list[Row]) -> Row:
    """Recompute all five decisions for each paired repaint strategy."""
    unique(rows, ("strategy", "pair"))
    require(len(rows) == 90, "White-box denominator differs")
    result = {}
    for strategy in ("source", "masked", "iterative"):
        group = [r for r in rows if r["strategy"] == strategy]
        require(len(group) == 30, "White-box strategy denominator differs")
        require(
            {r["pair"] for r in group} == {f"X2P{i:03d}" for i in range(30)},
            "White-box pair set differs",
        )
        decisions = []
        for row in group:
            (m, c, n) = (scalar(row, key, 1024) for key in ("M", "C", "N_any"))
            payload = p20(row)
            local = (
                m > cutoff("local_m") and c >= cutoff("local_c") and (n >= cutoff("strength_min"))
            )
            rules = dict(
                P20=payload,
                conjunction=payload and local,
                local_full=local,
                count_strict=m > cutoff("published_m"),
                count_inclusive=m >= cutoff("published_m"),
            )
            require(rules == row["rules"], "White-box saved decisions differ")
            decisions.append(rules)
        result[strategy] = dict(
            n=30, accepted={k: sum((r[k] for r in decisions)) for k in decisions[0]}
        )
    return result


def reproduction(rows: list[Row]) -> Row:
    """Count strict and inclusive acceptance for the 20 paired controls."""
    unique(rows, ("condition", "index"))
    require(len(rows) == 40, "Reproduction denominator differs")
    result = {}
    for condition in ("clean", "negative"):
        group = [r for r in rows if r["condition"] == condition]
        require({r["index"] for r in group} == set(range(20)), "Reproduction index set differs")
        for row in group:
            m = scalar(row, "M", 1024)
            require(
                row["strict"] == (m > cutoff("published_m"))
                and row["inclusive"] == (m >= cutoff("published_m")),
                "Reproduction saved decisions differ",
            )
        result[condition] = dict(
            n=20,
            strict=sum((r["M"] > cutoff("published_m") for r in group)),
            inclusive=sum((r["M"] >= cutoff("published_m") for r in group)),
        )
    return result


def baseline_decisions(row: Row, distortion: bool = False) -> dict[str, bool]:
    """Apply the frozen external-reference and embedded-payload cutoffs."""
    result = dict(
        embedded_P20=p20(dict(readable=row["readable"], mismatch=row["embedded_mismatch"])),
        external_S=scalar(row, "external_S_mismatch", 1) <= cutoff("mismatch_cutoff"),
        external_B=scalar(row, "external_B_mismatch", 1) <= cutoff("mismatch_cutoff"),
        dhash=scalar(row, "dhash_distance", 64) <= cutoff("dhash_cutoff"),
        rgb=scalar(row, "rgb_score", 1) <= cutoff("rgb_cutoff"),
    )
    if distortion:
        (m, c, n) = (scalar(row, key, 1024) for key in ("M", "C", "N_any"))
        result.update(
            published_count=m > cutoff("published_m"),
            published_inclusive=m >= cutoff("published_m"),
            local_mc=m > cutoff("local_m") and c >= cutoff("local_c"),
            local_full=m > cutoff("local_m")
            and c >= cutoff("local_c")
            and (n >= cutoff("strength_min")),
            published_corrected_mc=m > cutoff("published_m") and c >= cutoff("published_c"),
            published_corrected_full=m > cutoff("published_m")
            and c >= cutoff("published_c")
            and (n >= cutoff("strength_min")),
        )
    require(result == row["decisions"], "Baseline saved decisions differ")
    return result


def baselines(record: Row, distortion: bool = False) -> Row:
    """Recount cohort totals, preserving selected and any-query denominators."""
    rows = record["rows"]
    unique(rows, ("transform", "victim") if distortion else ("image",))
    require(len(rows) == (350 if distortion else 989), "Baseline row count differs")
    groups = defaultdict(list)
    for row in rows:
        baseline_decisions(row, distortion)
        groups[row["transform"] if distortion else row["group"]].append(row)
    if not distortion:
        for name, source in [
            ("exp1b_csi_selected", "exp1b_csi_all"),
            ("exp2_csi_committed", "exp2_csi_all"),
        ]:
            groups[name] = [r for r in groups[source] if r["selected"]]
    result = {
        name: dict(
            n=len(group),
            accepted={k: sum((r["decisions"][k] for r in group)) for k in group[0]["decisions"]},
        )
        for (name, group) in groups.items()
    }
    if not distortion:
        group = groups["exp2_csi_all"]
        victims = {r["victim"] for r in group}
        result["exp2_csi_any_query"] = dict(
            n=len(victims),
            accepted={
                k: sum(
                    (any((r["decisions"][k] for r in group if r["victim"] == v)) for v in victims)
                )
                for k in group[0]["decisions"]
            },
        )
    expected = {
        name: {"n": value["n"], "accepted": value["accepted"]}
        for (name, value) in record["groups"].items()
        if isinstance(value, dict)
    }
    require(result == expected, "Baseline aggregate differs from scalar recount")
    if distortion:
        victim_sets = [{r["victim"] for r in group} for group in groups.values()]
        require(
            all((ids == victim_sets[0] for ids in victim_sets)),
            "Distortion paired victim sets differ",
        )
        require(
            len(groups) == 7 and all((v["n"] == 50 for v in result.values())),
            "Distortion cohort denominator differs",
        )
    return result


def run() -> Row:
    """Verify the added paper counts against the independent row recounts."""
    result = dict(
        whitebox=whitebox(load("whitebox")["rows"]),
        reproduction=reproduction(load("seal-repro")["rows"]),
        external=baselines(load("external")),
        distortions=baselines(load("distortions"), True),
    )
    for strategy, expected in [("masked", (30, 28, 19)), ("iterative", (29, 25, 22))]:
        actual = result["whitebox"][strategy]["accepted"]
        require(
            tuple((actual[k] for k in ("P20", "conjunction", "count_strict"))) == expected,
            "White-box paper count differs",
        )
    require(
        result["reproduction"]["clean"]["strict"] == 13
        and result["reproduction"]["negative"]["strict"] == 0,
        "Reproduction paper count differs",
    )
    from swaudit.round6 import precision

    result["precision"] = precision(load("seal-repro-final"), load("seal-repro-summary"))
    return result


def main() -> None:
    """Print all round-five numerators and denominators as JSON."""
    print(json.dumps(run(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
