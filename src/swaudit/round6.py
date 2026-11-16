"""Derive the follow-up paper macros from scalar rows and frozen settings."""

from __future__ import annotations

import math
from typing import Any

from swaudit.analysis.format_numbers import rounded
from swaudit.analysis.statistics import exact_interval
from swaudit.protocol import cutoff
from swaudit.recompute import read, require, unique
from swaudit.round5 import baseline_decisions, load


def precision(record: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    """Check precision-ablation counts and intervals against the final summary."""
    rows = record["ablation"]
    unique(rows, ("index",))
    require({r["index"] for r in rows} == set(range(20)), "Precision cohort differs")
    result = {}
    for variant, expected in summary["precision"].items():
        k = sum(r["counts"][variant] > cutoff("published_m") for r in rows)
        require(k == expected["k"] and len(rows) == expected["n"], "Precision count differs")
        require(math.isclose(k / len(rows), expected["rate"]), "Precision rate differs")
        require(
            all(
                math.isclose(a, b, abs_tol=1e-12)
                for a, b in zip(exact_interval(k, len(rows)), expected["exact_95_ci"])
            ),
            "Precision interval differs",
        )
        result[variant] = dict(n=len(rows), strict=k)
    return result


def pairwise_auc(rows: list[dict[str, Any]], field: str, direction: int) -> float:
    """Compute clean-versus-negative AUC, giving ties half credit."""
    clean = [direction * r[field] for r in rows if r["condition"] == "clean"]
    negative = [direction * r[field] for r in rows if r["condition"] == "negative"]
    require(len(clean) == len(negative) == 20, "AUC cohort differs")
    return sum((x > y) + 0.5 * (x == y) for x in clean for y in negative) / (
        len(clean) * len(negative)
    )


def macros(
    existing: dict[str, str], recount: dict[str, Any]
) -> tuple[dict[str, str], dict[str, str]]:
    """Regenerate follow-up macros and identify numerical versus configuration inputs."""
    result: dict[str, str] = {}
    methods: dict[str, str] = {}
    settings = load("design")

    def put(name: str, value: Any, method: str = "follow-up scalar recount") -> None:
        require(name not in result, "Duplicate follow-up macro: " + name)
        result[name] = str(value)
        methods[name] = method

    def fraction(group: dict[str, Any], rule: str) -> str:
        return f"{group['accepted'][rule]}/{group['n']}"

    edits = load("whitebox-edits")["rows"]
    unique(edits, ("pair", "strategy"))
    require(len(edits) == 60, "White-box edit count differs")
    for strategy, prefix in [("masked", "RWhiteMasked"), ("iterative", "RWhiteSearch")]:
        group = recount["whitebox"][strategy]
        for suffix, rule in [("Thumb", "P20"), ("Full", "conjunction"), ("Seal", "count_strict")]:
            put(prefix + suffix, fraction(group, rule))
        values = [r["changed_fraction"] for r in edits if r["strategy"] == strategy]
        require(
            len(values) == group["n"] and all(0 <= v <= 1 for v in values), "Edit fractions differ"
        )
        put(prefix + "ChangeMin", rounded(min(values), 2, scale=100, percent=True))
        put(prefix + "ChangeMax", rounded(max(values), 2, scale=100, percent=True))
    for suffix, rule in [("Thumb", "P20"), ("Full", "conjunction")]:
        put("RWhiteSource" + suffix, fraction(recount["whitebox"]["source"], rule))
    design = settings["whitebox"]
    require(
        {r["region_size"] for r in edits if r["strategy"] == "masked"} == {design["square"]},
        "Masked square differs from design",
    )
    design_values = {
        "RWhiteSquare": design["square"],
        "RWhiteGrid": design["grid"],
        "RWhiteGatePercent": rounded(design["change_fraction"], 0, scale=100, percent=True),
        "RWhiteGateDelta": design["change_delta"],
        "RWhiteGateMae": design["change_mae"],
    }
    for word, size in zip(("Large", "Medium", "Small"), design["sizes"][1:]):
        design_values["RWhiteSize" + word] = size
    for word, blend in zip(("Full", "Strong", "Half", "Quarter"), design["blends"]):
        design_values["RWhiteBlend" + word] = blend
    thumb = settings["thumbnail"]
    for name, key in [
        ("RThumbSide", "side"),
        ("RMaskMargin", "margin"),
        ("RCarrierSide", "carrier_side"),
        ("RPayloadBits", "payload_bits"),
        ("RDhashBits", "dhash_bits"),
    ]:
        design_values[name] = thumb[key]
    design_values["RDhashCutoff"] = cutoff("dhash_cutoff")
    distortions = settings["distortions"]
    for word, key in [
        ("CropSide", "crop_side"),
        ("NoiseSigma", "noise_sigma"),
        ("BlurRadius", "blur_radius"),
    ]:
        design_values["RDist" + word] = distortions[key]
    design_values["RDistCropPercent"] = rounded(distortions["crop_percent"], 0, percent=True)
    for word, quality in zip(("Low", "Mid", "High"), distortions["qualities"]):
        design_values["RDistQuality" + word] = quality
    for name, value in design_values.items():
        put(name, value, "frozen configuration replay")

    final = load("seal-repro-final")
    summary = load("seal-repro-summary")
    prec = precision(final, summary)
    for condition, word in [("clean", "Clean"), ("negative", "Negative")]:
        group = recount["reproduction"][condition]
        for rule, suffix in [("strict", "Strict"), ("inclusive", "Inclusive")]:
            expected = summary["rates"][condition + "_" + rule]
            require(
                (group[rule], group["n"]) == (expected["k"], expected["n"]), "Summary rate differs"
            )
            put("RRepro" + word + suffix, f"{group[rule]}/{group['n']}")
    for field, suffix, digits, direction in [
        ("M", "SemanticAuc", 3, 1),
        ("C_corrected", "SpatialAuc", 5, -1),
        ("N_any", "ExhaustiveAuc", 3, 1),
    ]:
        auc = pairwise_auc(final["rows"], field, direction)
        require(math.isclose(auc, summary["aucs"][field]["auc"]), "Final AUC differs")
        put("RRepro" + suffix, rounded(auc, digits))
    put("RReproN", recount["reproduction"]["clean"]["n"])
    put(
        "RReproPublishedTarget",
        rounded(summary["publication"]["clean_reported"], 3),
        "published comparison endpoint replay",
    )
    for variant, suffix in [("fresh_fp16", "FpHalf"), ("fresh_fp32", "FpFull")]:
        put("RRepro" + suffix, f"{prec[variant]['strict']}/{prec[variant]['n']}")
    ablation = final["ablation"]
    gains = [
        r["index"]
        for r in ablation
        if r["counts"]["fresh_fp16"] <= cutoff("published_m") < r["counts"]["fresh_fp32"]
    ]
    losses = [
        r["index"]
        for r in ablation
        if r["counts"]["fresh_fp32"] <= cutoff("published_m") < r["counts"]["fresh_fp16"]
    ]
    require(
        gains == summary["paired_changes"]["improved"]
        and losses == summary["paired_changes"]["worsened"],
        "Paired precision changes differ",
    )
    put("RReproPrecisionGains", len(gains))
    put("RReproPrecisionLosses", len(losses))
    low, high = exact_interval(
        recount["reproduction"]["clean"]["strict"], recount["reproduction"]["clean"]["n"]
    )
    put("RReproStrictCILow", rounded(low, 1, scale=100, percent=True))
    put("RReproStrictCIHigh", rounded(high, 1, scale=100, percent=True))
    failures = [r for r in ablation if r["counts"]["saved_fp16"] <= cutoff("published_m")]
    causes = dict(
        Rejected=len(failures),
        CodeLimited=sum(r["retained_codes"] <= cutoff("published_m") for r in failures),
        InversionLimited=sum(r["retained_codes"] > cutoff("published_m") for r in failures),
        OracleMin=min(r["counts"]["oracle_original"] for r in failures),
        OracleMax=max(r["counts"]["oracle_original"] for r in failures),
    )
    for key, value in causes.items():
        put("RRepro" + key, value)

    external = recount["external"]
    for prefix, rule, cohorts in [
        (
            "RExternal",
            "external_S",
            [
                ("Jpeg", "exp1b_jpeg75"),
                ("Local", "exp2_local"),
                ("Csi", "exp1b_csi_selected"),
                ("Query", "exp2_csi_any_query"),
            ],
        ),
        (
            "RDhash",
            "dhash",
            [("Jpeg", "exp1b_jpeg75"), ("Local", "exp2_local"), ("AllCsi", "exp1b_csi_all")],
        ),
    ]:
        for word, cohort in cohorts:
            put(prefix + word, fraction(external[cohort], rule))
        controls = [external[name] for name in ("exp4_same_caption", "exp4b_same_caption")]
        put(
            prefix + "Controls",
            f"{sum(g['accepted'][rule] for g in controls)}/{sum(g['n'] for g in controls)}",
        )
    clean = load("distortion-clean")["rows"]
    unique(clean, ("victim",))
    transformed_ids = {r["victim"] for r in load("distortions")["rows"]}
    require({r["victim"] for r in clean} == transformed_ids, "Clean distortion cohort differs")
    clean_rules = []
    for row in clean:
        rules = baseline_decisions(row)
        rules.update(
            published_count=row["M"] > cutoff("published_m"),
            local_full=row["M"] > cutoff("local_m")
            and row["C"] >= cutoff("local_c")
            and row["N_any"] >= cutoff("strength_min"),
        )
        clean_rules.append(rules)
    groups = dict(
        recount["distortions"],
        clean=dict(
            n=len(clean), accepted={key: sum(r[key] for r in clean_rules) for key in clean_rules[0]}
        ),
    )
    names = [
        ("Clean", "clean"),
        ("JpegLow", "jpeg50"),
        ("JpegMid", "jpeg75"),
        ("JpegHigh", "jpeg90"),
        ("Resize", "resize_half"),
        ("Crop", "crop90"),
        ("Blur", "blur1"),
        ("Noise", "noise002"),
    ]
    for word, cohort in names:
        for suffix, rule in [
            ("Seal", "published_count"),
            ("Full", "local_full"),
            ("Thumb", "embedded_P20"),
            ("External", "external_S"),
            ("Dhash", "dhash"),
        ]:
            put("RDist" + word + suffix, groups[cohort]["accepted"][rule])
    put("RDistN", len(clean))
    put("RDistJpegLowLost", groups["jpeg50"]["n"] - groups["jpeg50"]["accepted"]["embedded_P20"])
    locked = [
        r
        for r in read("headline-locked.json")["rows"]
        if r["arm"] == "plain" and r["main_label"] is not None
    ]

    def accepted(row: dict[str, Any]) -> bool:
        return (
            row["status"] == "ok"
            and row["M"] > cutoff("local_m")
            and row["C_corrected"] >= cutoff("local_c")
            and row["N_any"] >= cutoff("strength_min")
        )

    qualified = sum(
        accepted(r) and r["main_label"] == "1" and r["normal_looking"] == "Yes" for r in locked
    )
    require(
        existing["LockedHumanPlainPass"] == str(qualified), "Locked human-qualified count differs"
    )
    methods["LockedHumanPlainPass"] = "follow-up scalar recount"
    flips = sum(r["main_label"] == "2" for r in locked)
    put("RReratedN", len(locked))
    put("RReratedFlips", flips)
    put("RReratedFlipPercent", rounded(flips / len(locked), 0, scale=100, percent=True))
    put("RReratedFailureFlips", sum(r["main_label"] == "2" and not accepted(r) for r in locked))
    for name, numerator, denominator in [
        ("RSealInitYield", "SealAloneInit", len(read("headline-run006.json")["rows"])),
        (
            "RSealFreshYield",
            "SealAloneFresh",
            len([r for r in read("headline-fresh_scores.json")["rows"] if r["arm"] == "plain"]),
        ),
    ]:
        put(name, f"{existing[numerator].split('/')[0]}/{denominator}")
    expected = load("expected-macros")
    require(
        set(result) == set(expected),
        "Follow-up macro set differs: " + str(sorted(set(result) ^ set(expected))),
    )
    differences = [name for name in result if result[name] != expected[name]]
    require(not differences, "Follow-up macro values differ: " + ", ".join(differences))
    return result, methods
