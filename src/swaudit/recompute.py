"""Recount saved evaluation records without models or network access."""

import argparse
import collections
import hashlib
import json
import math
import pathlib
import re
from typing import Any

from swaudit.analysis.format_numbers import rounded
from swaudit.analysis.frozen_rules import digest, full_boundary, p20, scalar_rules
from swaudit.analysis.statistics import exact_interval, paired
from swaudit.paths import RECORDS as BASE
from swaudit.protocol import cutoff

RULES = ("payload", "payload_full", "local_full", "published_count", "matched_strength")


def read(name: str) -> Any:
    """Read a bundled JSON record."""
    return json.loads((BASE / "data" / name).read_text())


def require(ok: bool, msg: str) -> None:
    """Reject invalid input with a descriptive error."""
    if not ok:
        raise ValueError(msg)


def unique(rows: Any, fields: Any) -> Any:
    """Require unique row keys."""
    keys = [tuple((r[k] for k in fields)) for r in rows]
    require(len(set(keys)) == len(keys), "Duplicate row: " + ",".join(fields))


def pct(x: float, places: int = 2) -> str:
    """Format a fraction as a TeX percentage."""
    return rounded(x, places, scale=100) + "\\%"


def count(rows: Any, fn: Any) -> Any:
    """Count rows satisfying the supplied predicate."""
    return sum((bool(fn(r)) for r in rows))


def interval(k: Any, n: Any) -> Any:
    """Return a binomial count with its exact 95% interval."""
    return dict(k=k, n=n, exact_95_ci=exact_interval(k, n))


def closest_rejected_mismatch(rows: list[dict[str, Any]]) -> float:
    """Return the smallest finite mismatch among rejected outputs."""
    values = [
        r["mismatch"]
        for r in rows
        if r["mismatch"] is not None and math.isfinite(r["mismatch"]) and not p20(r)
    ]
    require(bool(values), "No finite rejected mismatch")
    return min(values)


def analyze() -> Any:
    """Recompute repair endpoints and validate allocation and score bindings."""
    cfg = read("protocol.json")
    data = read("exp1b.json")
    rows = data["rows"]
    cand = data["all_candidates"]
    sel = read("selection1b.json")
    unique(rows, ("arm", "victim", "view"))
    unique(cand, ("victim", "candidate_id"))
    unique(sel["rows"], ("victim",))
    require(len(rows) == 440 and len(cand) == 500 and (len(sel["rows"]) == 100), "Exp1b coverage")
    require(
        not sel["budget_censored"] and all((not r["budget_censored"] for r in sel["rows"])),
        "Incomplete Exp1b",
    )
    cids = {f"C{i:03d}" for i in range(100, 140)}
    eids = {f"E{i:03d}" for i in range(100)}
    require({r["victim"] for r in sel["rows"]} == eids, "Assigned Exp1b victims")
    for arm, ids in [("CSI", eids), ("honest", cids | eids)]:
        require({r["victim"] for r in rows if r["arm"] == arm} == ids, "Dropped Exp1b IDs")
    cjpeg = [
        dict(r, C_corrected=r["C"], reference=r["victim"])
        for r in rows
        if r["arm"] == "honest" and r["victim"] in cids and (r["view"] == "B-J75.jpg")
    ]
    c1 = read("calibration1b.json")
    bound1 = c1["strength_threshold"]
    full = full_boundary(cjpeg, c1["payload_counts"]["jpeg75"])
    idx = {(r["victim"], r["candidate_id"]): r for r in cand}
    attack = {r["victim"]: r for r in rows if r["arm"] == "CSI"}
    for unit in sel["rows"]:
        require(len(unit["rendered"]) == 5, "Rendered Exp1b count")
        chosen = min(
            unit["rendered"],
            key=lambda c: (digest("exp1-select-v1:" + unit["victim"] + ":" + c["id"]), c["id"]),
        )
        require(chosen["id"] == unit["selected_id"], "Score-blind selection")
        for c in unit["rendered"]:
            require(
                c["generated"]
                and idx[unit["victim"], c["id"]]["image_sha256"] == c["image_sha256"],
                "Candidate binding",
            )
        require(
            attack[unit["victim"]]["image_sha256"] == chosen["image_sha256"],
            "Selected output binding",
        )
    for r in rows + cand:
        r["C_corrected"] = r["C"]
        r["_rules"] = scalar_rules(r, bound1, 1)
    out1 = {"honest_retention": {}, "arms": {}, "A5_boundary": full}
    for g, ids in [("C", cids), ("E", eids)]:
        for view in ("B.png", "B-J75.jpg"):
            pop = [
                r
                for r in rows
                if r["arm"] == "honest" and r["victim"] in ids and (r["view"] == view)
            ]
            require(len(pop) == len(ids), "Honest Exp1b coverage")
            out1["honest_retention"][g + "/" + view] = {
                k: interval(count(pop, lambda r: r["_rules"][k]), len(pop)) for k in RULES
            }
    for arm, n in [("CSI", 100), ("splice-B", 30)]:
        pop = [r for r in rows if r["arm"] == arm]
        require(len(pop) == n, "Arm Exp1b coverage")
        out1["arms"][arm] = {
            "assigned": n,
            "table": {k: interval(count(pop, lambda r: r["_rules"][k]), n) for k in RULES},
            "matched_strength": {
                "exact_two_sided_mcnemar_p": paired(
                    [r["_rules"]["payload"] for r in pop],
                    [r["_rules"]["matched_strength"] for r in pop],
                )["p_two_sided"]
            },
        }
    d2 = read("exp2.json")
    alloc = read("allocation2.json")
    queries = read("queries2.json")
    b2 = read("calibration2.json")
    require(
        len(alloc["victims"]) == 40
        and len(set(alloc["victims"])) == 40
        and (len(alloc["pairs"]) == 30)
        and (len(set(alloc["pairs"])) == 30),
        "Exp2 allocation",
    )
    unique(queries, ("victim", "query"))
    unique(d2["honest"], ("id", "view"))
    require(
        len(queries) == 120 and {r["victim"] for r in queries} == set(alloc["victims"]),
        "Exp2 query coverage",
    )
    require(
        {(r["id"], r["view"]) for r in d2["honest"]}
        == {(f"X2C{i:03d}", w) for i in range(40) for w in ("clean", "jpeg75")},
        "Exp2 honest coverage",
    )
    for r in d2["honest"] + list(d2["candidates"].values()):
        r["_rules"] = scalar_rules(r, b2, 2)
    used = set()
    victim_rows = []
    output = []
    qcounts = collections.Counter()
    lost = set()
    for v in alloc["victims"]:
        rr = sorted([r for r in queries if r["victim"] == v], key=lambda r: r["query"])
        require([r["query"] for r in rr] == [1, 2, 3], "Query indices")
        per = []
        accepted = False
        for q in rr:
            require(not accepted, "Query after accept")
            qcounts[f"{q['query']}/{q['reply']}"] += 1
            key = f"csi/{v}/q{q['query']}"
            if q["reply"] == "NO RESULT":
                require(
                    q["image_sha256"] is None and key not in d2["candidates"], "Lost slot has score"
                )
                lost.add(v)
                per.append({k: False for k in RULES})
                continue
            require(q["reply"] in ("ACCEPT", "REJECT"), "Invalid reply")
            r = d2["candidates"][key]
            used.add(key)
            require(
                r["image_sha256"] == q["image_sha256"]
                and r["_rules"]["payload"] == (q["reply"] == "ACCEPT"),
                "Query/score mismatch",
            )
            per.append(r["_rules"])
            output.append(r)
            accepted = q["reply"] == "ACCEPT"
        victim_rows.append({k: any((r[k] for r in per)) for k in RULES})
    local = []
    for p in alloc["pairs"]:
        key = "local/" + p
        r = d2["candidates"][key]
        used.add(key)
        local.append(r)
    require(set(d2["candidates"]) == used, "Extra or missing Exp2 score")
    out2 = {
        "honest_retention": {
            w: {
                k: interval(
                    count([r for r in d2["honest"] if r["view"] == w], lambda r: r["_rules"][k]), 40
                )
                for k in RULES
            }
            for w in ("clean", "jpeg75")
        },
        "a": interval(count(victim_rows, lambda r: r["payload_full"]), 40),
        "b": interval(count(local, lambda r: r["_rules"]["payload_full"]), 30),
        "thumbnail_alone": {
            "CSI": interval(count(victim_rows, lambda r: r["payload"]), 40),
            "local": interval(count(local, lambda r: r["_rules"]["payload"]), 30),
        },
        "victim_any_rule": {k: interval(count(victim_rows, lambda r: r[k]), 40) for k in RULES},
        "local_rules": {k: interval(count(local, lambda r: r["_rules"][k]), 30) for k in RULES},
        "all_rendered_CSI": {
            k: interval(count(output, lambda r: r["_rules"][k]), len(output)) for k in RULES
        },
        "query_reply_counts": dict(qcounts),
    }
    result = {}

    def put(k: Any, v: Any) -> Any:
        """Insert one macro, rejecting duplicate definitions."""
        require(k not in result, "Duplicate macro " + k)
        result[k] = str(v)

    sources = read("macro-sources.json")
    import ast

    for name, source in sources.items():
        if "#[" in source:
            expr = source.split("#", 1)[1].split(";", 1)[0]
            try:
                path = ast.literal_eval(expr)
            except (ValueError, SyntaxError):
                continue
            if "EXP1B-NUMBERS.json" in source:
                obj = out1
            elif "EXP2-NUMBERS.json" in source:
                obj = out2
            else:
                continue
            for key in path:
                obj = obj[key]
            put(name, obj)
    put(
        "RepOneBAttackThumbCIHighPercent",
        pct(out1["arms"]["CSI"]["table"]["payload"]["exact_95_ci"][1]),
    )
    pv = out1["arms"]["CSI"]["matched_strength"]["exact_two_sided_mcnemar_p"]
    (mant, exp) = rounded(pv, 1, scientific=True).split("e")
    put("RepOneBMcNemarP", "\\ensuremath{" + mant + "\\times 10^{" + str(int(exp)) + "}}")
    put("RepOneBJpegRejects", 100 - out1["honest_retention"]["E/B-J75.jpg"]["payload"]["k"])
    for name, cell, side in [
        ("RepTwoVictimsThumbFullCIHighPercent", "a", 1),
        ("RepTwoLocalThumbFullCILowPercent", "b", 0),
        ("RepTwoLocalThumbFullCIHighPercent", "b", 1),
    ]:
        put(name, pct(out2[cell]["exact_95_ci"][side]))
    put("RepTwoLostSlots", sum((n for (k, n) in qcounts.items() if k.endswith("/NO RESULT"))))
    put("RepMaxQueries", max((r["query"] for r in queries)))
    put(
        "RepTwoRecovered",
        count(
            alloc["victims"],
            lambda v: any(
                (q["reply"] == "ACCEPT" and q["query"] > 1 for q in queries if q["victim"] == v)
            ),
        ),
    )
    put("RepTwoWorstCaseVictims", out2["a"]["k"] + len(lost))
    require(len(lost) == 1, "Lost slot scope")
    put(
        "RepTwoLostSlotVictimQueries",
        count(queries, lambda q: q["victim"] in lost and q["reply"] != "NO RESULT"),
    )
    put("RepTwoLocalSquarePixels", cfg["local_square"])
    put("RepTwoLocalAreaPercent", pct((cfg["local_square"] / cfg["image_side"]) ** 2, 0))
    for name, key in [
        ("RepBandGoodMax", 0),
        ("RepBandInconclusiveMin", 1),
        ("RepBandInconclusiveMax", 2),
        ("RepBandBadMin", 3),
    ]:
        put(name, cfg["bands"][key])
    design_map = {
        "RepPayloadPatches": "payload_patches",
        "RepReadableFloor": "readable_floor",
        "RepReadableFloorSensitivity": "sensitivity_floor",
        "RepOneBUtilityFloor": "utility_floor",
        "RepOneBUtilityTarget": "utility_target",
        "RepOldGateClean": "old_gate",
        "RepTwoPTwoPredictedMin": "predicted_recoveries",
        "RepTwoLocalNearCutoffMarginPoints": "near_cutoff_margin_pp",
        "RepGateStrongJpegMin": "strong_jpeg_min",
        "RepGateStrongJpegRejectMax": "strong_jpeg_reject_max",
        "RepGateJpegSanity": "jpeg_sanity",
        "StandaloneStrengthCutoff": "standalone_strength",
        "RepNotConstructed": "not_constructed",
        "RepNotRegistered": "not_registered",
        "SealCodeCommitFull": "seal_code_commit",
        "FrontierReleasedSpatialLowCutoff": "released_spatial_low",
    }
    for name, key in design_map.items():
        put(name, cfg[key])
    for name, key in [
        ("RepMismatchCutoffPercent", "mismatch_cutoff"),
        ("RepUndescribedPercent", "undescribed_fraction_approx"),
        ("RepOneDinoCutoffPercent", "dino_cutoff"),
        ("RepTwoLocalNearCutoffUpperPercent", "near_cutoff_upper"),
    ]:
        put(name, pct(cfg[key], 0))
    put(
        "RunFourDevelopmentN",
        cfg["run4_development_indices"][1] - cfg["run4_development_indices"][0] + 1,
    )
    put("RepOneBRenders", max((len(r["rendered"]) for r in sel["rows"])))
    put("RepOneBMatchedStrengthBoundary", bound1["count"])
    put("RepTwoMatchedStrengthBoundary", b2["score"])
    put("RepOneBRecoveries", sel["recovery"]["recoveries"])
    hj = [
        r
        for r in rows
        if r["arm"] == "honest" and r["victim"] in eids and (r["view"] == "B-J75.jpg")
    ]

    def mismatch_ok(r):
        return (
            r["mismatch"] is not None
            and math.isfinite(r["mismatch"])
            and (0 <= r["mismatch"] <= cutoff("mismatch_cutoff"))
        )

    put(
        "RepOneBJpegRejectsFloorOnly",
        count(hj, lambda r: r["readable"] < cutoff("readable_floor") and mismatch_ok(r)),
    )
    put(
        "RepOneBJpegRejectsFloorAndMismatch",
        count(hj, lambda r: r["readable"] < cutoff("readable_floor") and (not mismatch_ok(r))),
    )
    put(
        "RepOneBJpegRejectsMismatchOnly",
        count(hj, lambda r: r["readable"] >= cutoff("readable_floor") and (not mismatch_ok(r))),
    )
    put(
        "RepOneBFloorFiveEvalJpeg",
        count(hj, lambda r: r["readable"] >= cutoff("sensitivity_floor") and mismatch_ok(r)),
    )
    put(
        "RepOneBFloorFiveCalJpeg",
        count(cjpeg, lambda r: r["readable"] >= cutoff("sensitivity_floor") and mismatch_ok(r)),
    )
    ev2 = read("eval2.json")
    unique(ev2, ("id", "view"))
    require(
        {(r["id"], r["view"]) for r in ev2}
        == {(f"X2E{i:03d}", w) for i in range(100) for w in ("clean", "jpeg75")},
        "Exp2 evaluation coverage",
    )
    put("RepTwoEvalN", len({r["id"] for r in ev2}))
    for w, name in [("clean", "RepTwoEvalCleanThumb"), ("jpeg75", "RepTwoEvalJpegThumb")]:
        put(name, count(ev2, lambda r: r["view"] == w and p20(r)))
    put("RepTwoClosestMismatchPercent", pct(closest_rejected_mismatch(output), 1))

    put(
        "RepTwoLocalNearCutoffPasses",
        count(
            local,
            lambda r: p20(r)
            and 0 <= cfg["mismatch_cutoff"] - r["mismatch"] <= cfg["near_cutoff_margin_pp"] / 100,
        ),
    )
    put(
        "RepTwoLocalRejectsNearCutoff",
        count(
            local,
            lambda r: r["mismatch"] is not None
            and cutoff("mismatch_cutoff") < r["mismatch"] <= cfg["near_cutoff_upper"],
        ),
    )
    dino = read("exp1-calibration.json")
    unique(dino, ("id", "view"))
    require(len(dino) == 80, "Exp1 calibration coverage")
    put("RepOneCalN", len({r["id"] for r in dino}))
    for w, name in [("clean", "RepOneDinoCalClean"), ("jpeg75", "RepOneDinoCalJpeg")]:
        put(
            name,
            count(
                dino,
                lambda r: r["view"] == w
                and r["readable"] >= cfg["dino_floor"]
                and (r["mismatch"] is not None)
                and (0 <= r["mismatch"] <= cfg["dino_cutoff"]),
            ),
        )
    locked = read("locked.json")
    unique(locked, ("case", "arm"))
    require(len(locked) == 80, "Locked-test coverage")
    decoy_counts = []
    for arm in ("plain", "repaired"):
        pop = [r for r in locked if r["arm"] == arm and r["main_label"] is not None]

        def fullpass(r: Any) -> Any:
            """Apply the local full-rule thresholds."""
            return (
                r["status"] == "ok"
                and r["M"] > cutoff("local_m")
                and (r["C_corrected"] >= cutoff("local_c"))
                and (r["N_any"] >= cutoff("strength_min"))
            )

        for status, fn in [("Pass", fullpass), ("Decoy", lambda r: not fullpass(r))]:
            for lab, suffix in [("1", "Consequential"), ("2", "Look"), ("3", "Other")]:
                name = "LockedClass" + arm.title() + status + suffix
                if name in sources:
                    put(name, count(pop, lambda r: fn(r) and r["main_label"] == lab))
        require(count(pop, lambda r: not fullpass(r)) == 11, "Locked decoy sample denominator")
        decoy_counts.append(count(pop, lambda r: not fullpass(r)))
    require(len(set(decoy_counts)) == 1, "Locked arms have different decoy counts")
    put("LockedClassDecoyPerArm", decoy_counts[0])
    seal = read("seal-alone.json")
    labels = {
        "Init": "run006_consequential",
        "Fresh": "fresh_consequential",
        "Honest": "run005_clean",
        "RunFourClean": "run004_calibration_clean",
        "RunFourJpeg": "run004_calibration_jpeg75",
        "FreshClean": "fresh_clean",
        "FreshJpeg": "fresh_jpeg75",
    }
    for suffix, group in labels.items():
        pop = seal[group]
        unique(pop, ("id",))
        k = count(pop, lambda r: r["M"] > cutoff("published_m"))
        n = len(pop)
        put("SealAlone" + suffix, f"{k}/{n}")
        put(
            "SealAloneIncl" + suffix, f"{count(pop, lambda r: r['M'] >= cutoff('published_m'))}/{n}"
        )
        if suffix in ("Init", "Fresh"):
            (lo, hi) = exact_interval(k, n)
            put("SealAlone" + suffix + "CI", pct(lo) + " to " + pct(hi))
    controls = {}
    for name in ("regen4", "regen4b"):
        d = read(name + ".json")
        unique(d["rows"], ("victim",))
        rules = {
            "count_strict": lambda r: r["M"] > cutoff("published_m"),
            "count_inclusive": lambda r: r["M"] >= cutoff("published_m"),
            "local_full": lambda r: r["M"] > cutoff("local_m")
            and r["C"] >= cutoff("local_c")
            and (r["N_any"] >= cutoff("strength_min")),
            "P20": p20,
            "conjunction": lambda r: p20(r)
            and r["M"] > cutoff("local_m")
            and (r["C"] >= cutoff("local_c"))
            and (r["N_any"] >= cutoff("strength_min")),
        }
        require(len(d["rows"]) == (40 if name == "regen4" else 100), "Regeneration denominator")
        for r in d["rows"]:
            require(r["total_read_bits"] == r["readable"] * 7, "Read-bit denominator")
            require(
                r["mismatch"] is None
                if not r["readable"]
                else abs(r["mismatch"] - r["mismatched_bits"] / r["total_read_bits"]) < 1e-12,
                "Mismatch reconstruction",
            )
            require(
                all((r["decisions"][k] == fn(r) for (k, fn) in rules.items())),
                "Regeneration decision drift",
            )
        controls[name] = {
            k: interval(count(d["rows"], fn), len(d["rows"])) for (k, fn) in rules.items()
        }
        for endpoint, pr in d["paired"].items():
            unique(pr, ("victim",))
            require(
                {r["victim"] for r in pr} == {r["victim"] for r in d["rows"]},
                "Regeneration pairing",
            )
            require(
                all(
                    (
                        r["regen"]
                        == next((x["decisions"] for x in d["rows"] if x["victim"] == r["victim"]))
                        for r in pr
                    )
                ),
                "Regeneration pair binding",
            )
            for pair in pr:
                if pair["missing_render"]:
                    require(
                        all((not v for v in pair["changed"].values())),
                        "Missing render counted as pass",
                    )
                    continue
                historical = (
                    idx[pair["victim"], pair["candidate_id"]]
                    if name == "regen4b"
                    else d2["candidates"][f"csi/{pair['victim']}/q{pair['query']}"]
                )
                require(
                    all((pair["changed"][k] == fn(historical) for (k, fn) in rules.items())),
                    "Historical control pair differs from scalar score",
                )
                if name == "regen4b" and endpoint == "committed":
                    require(
                        pair["candidate_id"]
                        == next(
                            (x["selected_id"] for x in sel["rows"] if x["victim"] == pair["victim"])
                        ),
                        "Committed control candidate changed",
                    )
            controls[name][endpoint] = {
                k: dict(
                    accepted=count(pr, lambda r: r["changed"][k]),
                    n=len(pr),
                    table=[
                        [
                            count(
                                pr,
                                lambda r: r["regen"][k] == bool(i) and r["changed"][k] == bool(j),
                            )
                            for j in (0, 1)
                        ]
                        for i in (0, 1)
                    ],
                )
                for k in rules
            }
    refusals = read("exp3-refusals.json")
    require(
        len(refusals["calls"]) == 2
        and all(
            (c["stop_reason"] == "refusal" and c["category"] == "cyber" for c in refusals["calls"])
        )
        and (refusals["cohort_victims_used"] == 0)
        and (refusals["verifier_calls"] == 0),
        "Exp3 dry-run scope",
    )
    return (
        result,
        dict(
            exp1b=out1,
            exp2=out2,
            controls=controls,
            exp3=refusals,
            design_macros=sorted(
                set(design_map)
                | {
                    "RepMismatchCutoffPercent",
                    "RepUndescribedPercent",
                    "RepOneDinoCutoffPercent",
                    "RepTwoLocalNearCutoffUpperPercent",
                    "RunFourDevelopmentN",
                    "RepTwoLocalSquarePixels",
                    "RepTwoLocalAreaPercent",
                    "RepBandGoodMax",
                    "RepBandInconclusiveMin",
                    "RepBandInconclusiveMax",
                    "RepBandBadMin",
                }
            ),
        ),
    )


def parse_tex(text: str) -> dict[str, str]:
    """Parse unique macro definitions from the frozen comparison file."""
    pairs = re.findall("^\\\\newcommand\\{\\\\(\\w+)\\}\\{(.*)\\}$", text, re.M)
    require(len(pairs) == len(dict(pairs)), "Duplicate expected macro")
    return dict(pairs)


def verify_manifest() -> int:
    """Verify the complete record inventory and SHA256 digests."""
    manifest = json.loads((BASE / "MANIFEST.json").read_text())
    listed = {entry["path"]: entry for entry in manifest["files"]}
    require(len(listed) == len(manifest["files"]), "Duplicate manifest path")
    actual = {
        p.relative_to(BASE).as_posix()
        for p in BASE.rglob("*")
        if p.is_file()
        and p.name not in {"MANIFEST.json", "__init__.py"}
        and ("__pycache__" not in p.parts)
    }
    require(set(listed) == actual, "Manifest file list differs")
    require(not any((p.is_symlink() for p in BASE.rglob("*"))), "Package contains symlink")
    for rel, entry in listed.items():
        p = BASE / rel
        require(
            not pathlib.Path(rel).is_absolute()
            and ".." not in pathlib.Path(rel).parts
            and p.resolve().is_relative_to(BASE),
            "Unsafe manifest path",
        )
        raw = p.read_bytes()
        require(
            len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"],
            "Manifest digest differs: " + rel,
        )
    return len(listed)


def main() -> Any:
    """Run the command-line recount."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=pathlib.Path)
    args = ap.parse_args()
    verify_manifest()
    (result, details) = analyze()
    target = (BASE / "expected/repair-numbers.tex").read_text()
    expected = parse_tex(target)
    mismatches = [
        dict(macro=k, expected=expected.get(k), actual=result.get(k))
        for k in sorted(set(result) | set(expected))
        if result.get(k) != expected.get(k)
    ]
    report = dict(
        author="Kuladeep Mantri",
        macros=len(expected),
        generated=len(result),
        mismatches=len(mismatches),
        differences=mismatches,
        design_macros=len(details["design_macros"]),
        observed_or_derived_macros=len(result) - len(details["design_macros"]),
    )
    if args.output:
        out = args.output.resolve()
        require(not out.is_relative_to(BASE), "Output must be outside immutable package")
        out.mkdir(parents=True, exist_ok=True)
        lines = target.splitlines()
        generated = (
            "\n".join(
                (
                    re.sub(
                        "^(\\\\newcommand\\{\\\\(\\w+)\\}\\{).*(\\})$",
                        lambda m: m[1] + result.get(m[2], "<MISSING>") + m[3],
                        line,
                    )
                    for line in lines
                )
            )
            + "\n"
        )
        (out / "repair-numbers.tex").write_text(generated)
        (out / "RESULT.json").write_text(
            json.dumps(dict(report, details=details), indent=2, sort_keys=True) + "\n"
        )
        import difflib

        (out / "repair-numbers.diff").write_text(
            "".join(
                difflib.unified_diff(
                    target.splitlines(True),
                    generated.splitlines(True),
                    fromfile="expected/repair-numbers.tex",
                    tofile="regenerated/repair-numbers.tex",
                )
            )
        )
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(mismatches))


if __name__ == "__main__":
    main()
