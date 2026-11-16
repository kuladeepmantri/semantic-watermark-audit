"""Saved-score headline recounts. Standard library only."""

import bisect
import collections
import functools
import math
from typing import Any

from swaudit.analysis.statistics import exact_interval
from swaudit.protocol import cutoff as protocol_cutoff
from swaudit.protocol import rule_definitions
from swaudit.recompute import read, require, unique


@functools.lru_cache(None)
def endpoint(k: Any, n: Any) -> Any:
    """Summarize an accepted count and its exact binomial interval."""
    return dict(k=k, n=n, rate=k / n, exact_95_ci=exact_interval(k, n))


def rules(r: dict[str, Any], names: tuple[str, ...] | None = None) -> dict[str, bool]:
    """Apply only the requested rules, rejecting missing score fields."""
    definitions = rule_definitions()
    result = {}
    for name in definitions if names is None else names:
        passed = True
        for field, (operator, threshold) in definitions[name].items():
            value = r[field]
            require(type(value) in (int, float) and math.isfinite(value), "Invalid score: " + field)
            require(operator in {"gt", "ge"}, "Unknown rule operator")
            passed = passed and (value > threshold if operator == "gt" else value >= threshold)
        result[name] = passed
    return result


def build_master() -> Any:
    """Recount the master table from scalar scores and outcome codes."""
    rr = read("frontier-rows.json")["rows"]
    unique(rr, ("cohort", "victim"))
    groups = {g: [r for r in rr if r["cohort"] == g] for g in {r["cohort"] for r in rr}}
    expected = {
        "run005_clean": 200,
        "run005_null": 200,
        "run004_clean": 200,
        "run004_jpeg75": 200,
        "fresh_clean": 200,
        "fresh_jpeg75": 200,
        "run006": 40,
        "fresh": 37,
        "run006_code2": 147,
        "fresh_code2": 154,
    }
    require({g: len(v) for (g, v) in groups.items()} == expected, "Headline cohort denominators")
    for a, b in [("run004_clean", "run004_jpeg75"), ("fresh_clean", "fresh_jpeg75")]:
        require(
            {r["victim"] for r in groups[a]} == {r["victim"] for r in groups[b]}, "Honest pairing"
        )
    cohorts = {
        "run005_clean": "run005_clean",
        "run005_negative": "run005_null",
        "run004_calibration_clean": "run004_clean",
        "run004_calibration_jpeg75": "run004_jpeg75",
        "fresh_clean": "fresh_clean",
        "fresh_jpeg75": "fresh_jpeg75",
    }
    ctx = read("master-context.json")
    require(ctx["rules"] == rule_definitions(), "Master rule declarations differ from protocol")
    cells = {}
    sensitivity = {}
    labels = read("headline-fresh_labels.json")["rows"]
    scores = read("headline-fresh_scores.json")["rows"]
    unique(labels, ("case", "arm"))
    unique(scores, ("case", "arm"))
    lab = {(r["case"], r["arm"]): r for r in labels}
    fresh = [r for r in scores if r["arm"] == "plain"]
    require(
        len(fresh) == 200 and all(((r["case"], "plain") in lab for r in fresh)),
        "Fresh plain labels",
    )
    r6 = read("headline-run006.json")["rows"]
    unique(r6, ("case",))
    require(len(r6) == 200, "Run006 full labels")
    for pop, consequential, cohort in [
        (r6, lambda r: r["label"] == "consequential", "run006"),
        (fresh, lambda r: lab[r["case"], "plain"]["label"] == 1, "fresh"),
    ]:
        fields = ("M", "C_corrected", "C_released", "N_any")
        require(
            sorted((tuple((r[k] for k in fields)) for r in pop if consequential(r)))
            == sorted((tuple((r[k] for k in fields)) for r in groups[cohort])),
            "Consequential projection differs",
        )
    for rule in ctx["rules"]:
        cells[rule] = {
            name: endpoint(sum((rules(r)[rule] for r in groups[g])), len(groups[g]))
            for (name, g) in cohorts.items()
        }
        for batch in ("run006", "fresh"):
            k = sum((rules(r)[rule] for r in groups[batch]))
            cells[rule][batch + "_consequential"] = endpoint(k, len(groups[batch]))
            cells[rule][batch + "_consequential_yield"] = endpoint(k, 200)
            if batch == "run006":
                cells[rule]["run006_descriptive_consequential_normal_passing_yield"] = endpoint(
                    ctx["normal_passing"][rule], 200
                )
            else:
                k = sum(
                    (
                        rules(r)[rule]
                        and lab[r["case"], "plain"]["label"] == 1
                        and (lab[r["case"], "plain"]["normal"] == "Yes")
                        for r in fresh
                    )
                )
                cells[rule]["fresh_human_qualified_yield"] = endpoint(k, 200)
    for rule, field, cutoff in [
        ("paper_corrected", "C_corrected", protocol_cutoff("published_c")),
        ("paper_released", "C_released", protocol_cutoff("released_c")),
    ]:
        sensitivity[rule] = {
            name: endpoint(
                sum(
                    (
                        r["M"] >= protocol_cutoff("published_m") and r[field] >= cutoff
                        for r in groups[g]
                    )
                ),
                len(groups[g]),
            )
            for (name, g) in cohorts.items()
        }
        for batch in ("run006", "fresh"):
            sensitivity[rule][batch + "_consequential"] = endpoint(
                sum(
                    (
                        r["M"] >= protocol_cutoff("published_m") and r[field] >= cutoff
                        for r in groups[batch]
                    )
                ),
                len(groups[batch]),
            )
    return (
        dict(
            cells=cells,
            count_comparator_sensitivity=sensitivity,
            run006_naturalness=ctx["run006_naturalness"],
        ),
        groups,
    )


def frontier(groups: Any) -> Any:
    """Search attainable thresholds while preserving the frozen tie order."""
    spec = read("frontier-spec.json")
    gates = spec["grid"]["c_gates"]
    declared = dict(
        corrected7=["C_corrected", protocol_cutoff("local_c")],
        corrected19=["C_corrected", protocol_cutoff("held_c")],
        corrected32=["C_corrected", protocol_cutoff("published_c")],
        released20=["C_released", protocol_cutoff("released_spatial_low")],
        released53=["C_released", protocol_cutoff("released_c")],
        disabled=[None, 0],
    )
    require(gates == declared, "Frontier gates differ from protocol")
    targets = {}
    searches = []
    for req in spec["targets"]:
        fake = req["fake_cohort"]
        honest = spec["grid"]["contexts"][req["honest_constraint"]]
        target = req["target_count"]
        choices = []
        for gate, (field, cutoff) in gates.items():
            pops = {
                g: [r for r in rows if field is None or r[field] >= cutoff]
                for (g, rows) in groups.items()
            }
            ms = sorted({-1} | {r["M"] for rows in pops.values() for r in rows})
            for m in ms:
                ns = {
                    g: sorted((r["N_any"] for r in rows if r["M"] > m))
                    for (g, rows) in pops.items()
                    if g in honest + [fake]
                }
                if any((len(ns[g]) < target for g in honest)):
                    continue
                maxn = min((ns[g][-target] for g in honest))
                f = ns[fake]
                left = bisect.bisect_left(f, maxn)
                n = 0 if left == 0 else f[left - 1] + 1
                accepted = len(f) - bisect.bisect_left(f, n)
                capacity = min((len(ns[g]) - bisect.bisect_left(ns[g], n) for g in honest))
                key = (accepted, -capacity, m, n, list(gates).index(gate))
                choices.append((key, gate, m, n))
        require(choices, "No feasible frontier rule")
        (key, gate, m, n) = min(choices)
        (field, cutoff) = gates[gate]

        def accepts(r: Any) -> Any:
            """Check numerical acceptance for an experimental arm."""
            return r["M"] > m and r["N_any"] >= n and (field is None or r[field] >= cutoff)

        row = dict(
            req, c_variant=gate, M_strict_gt=m, N_any_ge=n, min_constrained_honest_kept=-key[1]
        )
        for g, rr in groups.items():
            k = sum((accepts(r) for r in rr))
            e = endpoint(k, len(rr))
            row.update(
                {
                    g + "_accepted": k,
                    g + "_n": len(rr),
                    g + "_acceptance_rate": e["rate"],
                    g + "_ci_low": e["exact_95_ci"][0],
                    g + "_ci_high": e["exact_95_ci"][1],
                }
            )
        targets[req["index"]] = row
        searches.append(
            dict(
                index=req["index"],
                candidate_rules=len(choices),
                chosen=[gate, m, n],
                accepted=key[0],
            )
        )
    auc = {}
    for r in spec["meaning_auc"]:
        one = groups[r["batch"]]
        two = groups[r["batch"] + "_code2"]
        key = r["score"]
        wins = sum(
            (1 if b[key] > a[key] else 0.5 if b[key] == a[key] else 0 for a in one for b in two)
        )
        auc[r["index"]] = dict(
            r, code1_n=len(one), code2_n=len(two), auc=wins / (len(one) * len(two))
        )
    return (dict(targets=targets, meaning_auc=auc), searches)


def attribution(groups: Any) -> Any:
    """Separate rejection counts by verifier component."""
    r6 = read("headline-run006.json")["rows"]
    r5 = read("headline-run005.json")["rows"]
    clean6 = read("run006-clean.json")["rows"]
    pops = {
        "run005_clean": [r for r in r5 if r["condition"] == "clean"],
        "run004_clean": groups["run004_clean"],
        "run004_jpeg75": groups["run004_jpeg75"],
        "run006_paired_clean": clean6,
    }
    pops.update(
        {
            "run006_" + label: [r for r in r6 if r["label"] == label]
            for label in ("consequential", "inconsequential", "off-subject")
        }
    )

    def summarize(rr: Any) -> Any:
        """Summarize a fixed cohort under each rule."""
        out = collections.Counter(n=len(rr))
        for r in rr:
            (m, c, n) = (
                r["M"] > protocol_cutoff("local_m"),
                r["C_corrected"] >= protocol_cutoff("local_c"),
                r["N_any"] >= protocol_cutoff("strength_min"),
            )
            out.update(
                dict(
                    full=m and c and n,
                    no_M=c and n,
                    no_C=m and n,
                    no_N=m and c,
                    M_unique_rejects=not m and c and n,
                    N_unique_rejects=m and c and (not n),
                    fail_both_MN=not m and (not n),
                )
            )
        return dict(out)

    out = {k: summarize(v) for (k, v) in pops.items()}
    out["matched421"] = {}
    for label, pop in [
        ("run005_clean", pops["run005_clean"]),
        ("consequential", pops["run006_consequential"]),
    ]:

        def full(r):
            return (
                r["M"] > protocol_cutoff("local_m")
                and r["C_corrected"] >= protocol_cutoff("local_c")
                and (r["N_any"] >= protocol_cutoff("strength_min"))
            )

        out["matched421"][label] = dict(
            full=sum((full(r) for r in pop)),
            strength421=sum((r["N_any"] >= protocol_cutoff("standalone_strength") for r in pop)),
            both=sum(
                (full(r) and r["N_any"] >= protocol_cutoff("standalone_strength") for r in pop)
            ),
        )
    return out


def extras(groups: Any) -> Any:
    """Recount supplementary score distributions and diagnostics."""
    diag = read("run004-diagnostics.json")["rows"]
    unique(diag, ("id", "split", "condition"))
    held = {}
    for w in ("clean", "negative"):
        pop = [r for r in diag if r["split"] == "evaluation" and r["condition"] == w]
        require(len(pop) == 100, "Run004 heldout denominator")
        held["clean" if w == "clean" else "unwatermarked"] = {
            "corrected_joint": endpoint(
                sum(
                    (
                        r["M"] > protocol_cutoff("held_m")
                        and r["C_corrected"] >= protocol_cutoff("held_c")
                        for r in pop
                    )
                ),
                len(pop),
            )
        }
    theory = [r for r in diag if r["condition"] == "clean"]
    require(len(theory) == 400, "Theory honest denominator")
    o6 = {}
    pop = groups["fresh_jpeg75"]
    k = sum((r["N_any"] < protocol_cutoff("strength_min") for r in pop))
    o6["conditions"] = {
        "jpeg75": {
            "strength": dict(rejected=k, n=len(pop), rejected_exact95=exact_interval(k, len(pop)))
        }
    }
    return (held, theory, o6)


def primary_sources(groups: Any) -> Any:
    """Recount primary outcomes from score and label joins."""
    from swaudit.analysis.statistics import binomial_sf, paired

    locked = read("headline-locked.json")["rows"]
    unique(locked, ("case", "arm"))
    cases = sorted({r["case"] for r in locked})
    keyed = {(r["case"], r["arm"]): r for r in locked}
    require(
        len(cases) == 40 and set(keyed) == {(c, a) for c in cases for a in ("plain", "repaired")},
        "Locked paired coverage",
    )
    outcomes = {
        name: {a: [] for a in ("plain", "repaired")} for name in ("primary", "secondary_numeric")
    }
    acceptance = {}
    for arm in ("plain", "repaired"):
        pop = [keyed[c, arm] for c in cases]
        acceptance[arm] = {
            k: endpoint(
                sum(
                    (
                        r["status"] == "ok"
                        and r["M"] > protocol_cutoff("local_m")
                        and (r["C_corrected"] >= protocol_cutoff("local_c"))
                        if k == "primary"
                        else r["status"] == "ok" and r["N_any"] >= protocol_cutoff("strength_min")
                        for r in pop
                    )
                ),
                40,
            )
            for k in ("primary", "strength")
        }
        for r in pop:
            numeric = r["status"] == "ok" and rules(r, ("primary_strength",))["primary_strength"]
            outcomes["secondary_numeric"][arm].append(numeric)
            if numeric:
                require(
                    r["main_label"] in ("1", "2", "3", "4")
                    and r["normal_looking"] in ("Yes", "No"),
                    "Missing passing locked label",
                )
            outcomes["primary"][arm].append(
                numeric and r["main_label"] == "1" and (r["normal_looking"] == "Yes")
            )
    outlocked = {
        name: dict(
            arms={a: endpoint(sum(v), 40) for (a, v) in arms.items()},
            paired=paired(arms["plain"], arms["repaired"]),
        )
        for (name, arms) in outcomes.items()
    }
    outlocked.update(
        acceptance=acceptance,
        coverage=dict(
            packet_label_rows=sum((r["main_label"] is not None for r in locked)),
            unsampled_numeric_failures=sum((r["main_label"] is None for r in locked)),
        ),
    )
    labels = read("headline-fresh_labels.json")["rows"]
    scores = read("headline-fresh_scores.json")["rows"]
    lab = {(r["case"], r["arm"]): r for r in labels}
    sk = {(r["case"], r["arm"]): r for r in scores}
    cs = sorted({r["case"] for r in scores})
    require(len(cs) == 200 and len(scores) == 400, "Fresh paired score coverage")

    def qualified(c: Any, a: Any) -> Any:
        """Require numerical acceptance and the declared human outcome."""
        s = sk[c, a]
        numeric = rules(s, ("primary_strength",))["primary_strength"] and s["gate"]
        if numeric:
            require((c, a) in lab, "Missing fresh pass label")
        return numeric and lab[c, a]["label"] == 1 and (lab[c, a]["normal"] == "Yes")

    matched = [c for c in cs if (c, "repaired") in lab]
    pair = paired(
        [qualified(c, "plain") for c in matched], [qualified(c, "repaired") for c in matched]
    )
    pair["cells"] = dict(k3_only_c=pair["repair_only"], plain_only_b=pair["plain_only"])
    plain = [sk[c, "plain"] for c in cs]
    con = [r for r in plain if lab[r["case"], "plain"]["label"] == 1]
    inc = [r for r in plain if lab[r["case"], "plain"]["label"] == 2]
    positions = {(r["case"], r["arm"]): i for (i, r) in enumerate(labels)}
    p = sum((rules(sk[c, "repaired"], ("primary_strength",))["primary_strength"] for c in cs))
    fresh = dict(
        plain=dict(
            class_counts={"consequential": len(con)},
            rules=dict(
                primary=dict(
                    by_label=dict(
                        inconsequential=endpoint(
                            sum((rules(r, ("primary",))["primary"] for r in inc)), len(inc)
                        )
                    ),
                    conditional_consequential=endpoint(
                        sum((rules(r, ("primary",))["primary"] for r in con)), len(con)
                    ),
                    unconditional_yield=endpoint(
                        sum((rules(r, ("primary",))["primary"] for r in con)), 200
                    ),
                )
            ),
        ),
        matched_subset=pair,
        human_qualified={
            a: endpoint(sum((qualified(c, a) for c in cs)), 200) for a in ("plain", "repaired")
        },
        packet=dict(
            P_K3=p,
            d=len(matched) - p,
            plain=200,
            total=len(labels),
            separation=dict(
                k3_before_plain=sum(
                    (positions[c, "repaired"] < positions[c, "plain"] for c in matched)
                )
            ),
        ),
    )
    fresh["human_qualified"]["k3"] = fresh["human_qualified"]["repaired"]
    r6 = read("headline-run006.json")["rows"]
    con = [r for r in r6 if r["label"] == "consequential"]
    inc = [r for r in r6 if r["label"] == "inconsequential"]
    run6 = dict(
        populations=dict(
            all_200=dict(
                class_counts=dict(consequential=len(con)),
                rules=dict(
                    primary=dict(
                        by_label=dict(
                            inconsequential=endpoint(
                                sum((rules(r, ("primary",))["primary"] for r in inc)), len(inc)
                            )
                        ),
                        conditional_consequential=endpoint(
                            sum((rules(r, ("primary",))["primary"] for r in con)), len(con)
                        ),
                        unconditional_yield=endpoint(
                            sum((rules(r, ("primary",))["primary"] for r in con)), len(r6)
                        ),
                    )
                ),
            )
        )
    )
    r5 = read("headline-run005.json")["rows"]
    hon = [r for r in r5 if r["condition"] == "clean"]
    null = [r for r in r5 if r["condition"] == "negative"]
    require(len(hon) == len(null) == 200, "Run005 diagnostic coverage")
    model = {}
    for cut in (3, 12):
        predicted = math.fsum(
            (binomial_sf(cut, 1024, (1 - r["theta"] / 180) ** 7 * r["oracle"] / 1024) for r in hon)
        )
        model["M_gt_" + str(cut)] = dict(
            observed=sum((r["M"] > cut for r in hon)), predicted=predicted
        )
    predictions = dict(n_honest=len(hon), n_unwatermarked=len(null), P1=model)
    expected = dict(
        heldout_rules=dict(
            primary={
                w: endpoint(sum((rules(r, ("primary",))["primary"] for r in pop)), len(pop))
                for (w, pop) in [("clean", hon), ("unwatermarked", null)]
            }
        )
    )
    return (outlocked, fresh, run6, predictions, expected)
