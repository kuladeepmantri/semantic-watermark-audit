"""Recompute part 2 macros using only de-identified scalars.

Frontier search compresses unchanged threshold ranges, retaining the source tie
order. Bootstrap replays the source PCG64 stream and multinomial inversion.
No repository files, third-party modules, network, or expected endpoints enter
any computation. expected.json is used only for comparison and macro bindings.
"""

import argparse
import bisect
import functools
import json
import math
from pathlib import Path
from typing import Any

from swaudit.analysis import statistics as stats
from swaudit.analysis.format_numbers import rounded
from swaudit.paths import RECORDS
from swaudit.protocol import cutoff as protocol_cutoff

BASE = RECORDS / "headline/part2"
GATES = (
    (None, 0),
    (1, protocol_cutoff("local_c")),
    (1, protocol_cutoff("held_c")),
    (1, protocol_cutoff("published_c")),
    (2, protocol_cutoff("released_spatial_low")),
    (2, protocol_cutoff("released_c")),
)
CONTEXTS = {
    "both": ("run005_clean", "run004_clean", "run004_jpeg75", "fresh_clean", "fresh_jpeg75"),
    "both_jpeg_only": ("run004_jpeg75", "fresh_jpeg75"),
}


@functools.lru_cache(None)
def interval(k: int, n: int) -> tuple[float, float]:
    """Return the shared exact 95% binomial interval."""
    if n <= 0:
        raise ValueError("Invalid binomial counts")
    return tuple(stats.exact_interval(k, n))


def frontier(groups: Any, request: Any) -> Any:
    """Search attainable thresholds while preserving the frozen tie order."""
    honest = CONTEXTS[request["honest_constraint"]]
    fake = request["fake_cohort"]
    target = request["target_count"]
    choices = []
    for gate_index, (field, cutoff) in enumerate(GATES):
        pops = {
            g: [r for r in groups[g] if field is None or r[field] >= cutoff]
            for g in (*honest, fake)
        }
        ms = sorted({-1} | {r[0] for rows in pops.values() for r in rows})
        for m in ms:
            ns = {g: sorted((r[3] for r in rows if r[0] > m)) for (g, rows) in pops.items()}
            if any((len(ns[g]) < target for g in honest)):
                continue
            maxn = min((ns[g][-target] for g in honest))
            f = ns[fake]
            left = bisect.bisect_left(f, maxn)
            n = 0 if left == 0 else f[left - 1] + 1
            accepted = len(f) - bisect.bisect_left(f, n)
            capacity = min((len(ns[g]) - bisect.bisect_left(ns[g], n) for g in honest))
            choices.append((accepted, -capacity, m, n, gate_index))
    (accepted, _, m, n, gate_index) = min(choices)
    (field, cutoff) = GATES[gate_index]
    if not accepted == sum(
        (r[0] > m and r[3] >= n and (field is None or r[field] >= cutoff) for r in groups[fake])
    ):
        raise ValueError(
            "Data validation failed: accepted == sum((r[0] > m and r[3] >= n and (field is None or r[field] >= cutoff) for r in groups[fake]))"
        )
    den = len(groups[fake])
    (low, high) = interval(accepted, den)
    return {
        fake + "_accepted": accepted,
        fake + "_n": den,
        fake + "_ci_low": low,
        fake + "_ci_high": high,
        "target_count": target,
    }


class PCG64:
    def __init__(self, initialization: Any) -> Any:
        self.state = initialization["state"]
        self.inc = initialization["inc"]

    def uniform(self) -> Any:
        """Draw a uniform variate from the pinned generator stream."""
        self.state = (self.state * 47026247687942121848144207491837523525 + self.inc) % (1 << 128)
        mask = (1 << 64) - 1
        x = (self.state >> 64 ^ self.state) & mask
        rotation = self.state >> 122
        raw = (x >> rotation | x << (-rotation & 63)) & mask
        return (raw >> 11) * (1.0 / 9007199254740992)

    def binomial(self, n: Any, p: Any) -> Any:
        """Draw a binomial count using inversion sampling."""
        if n == 0 or p == 0:
            return 0
        if p > 0.5:
            return n - self.binomial(n, 1 - p)
        if not n * p <= 30:
            raise ValueError("Data validation failed: n * p <= 30")
        q = 1 - p
        qn = math.exp(n * math.log(q))
        bound = min(n, int(n * p + 10 * math.sqrt(n * p * q + 1)))
        (x, px, u) = (0, qn, self.uniform())
        while u > px:
            x += 1
            if x > bound:
                (x, px, u) = (0, qn, self.uniform())
            else:
                u -= px
                px = (n - x + 1) * p * px / (x * q)
        return x

    def multinomial(self, n: Any) -> Any:
        """Draw bootstrap multiplicities for an equally weighted sample."""
        (remaining_n, remaining_p) = (n, 1.0)
        weights = []
        for j in range(n - 1):
            value = self.binomial(remaining_n, 1.0 / n / remaining_p)
            weights.append(value)
            remaining_n -= value
            if remaining_n <= 0:
                weights.extend([0] * (n - 1 - j))
                break
            remaining_p -= 1.0 / n
        else:
            weights.append(remaining_n)
        if not (len(weights) == n and sum(weights) == n):
            raise ValueError("Data validation failed: len(weights) == n and sum(weights) == n")
        return weights


def quantile(values: list[float], p: float) -> float:
    """Interpolate the requested quantile with the frozen rounding order."""
    values = sorted(values)
    index = (len(values) - 1) * p
    low = int(index)
    fraction = index - low
    (a, b) = (values[low], values[min(low + 1, len(values) - 1)])
    return a + (b - a) * fraction if fraction < 0.5 else b - (b - a) * (1 - fraction)


def meaning(groups: Any, design: Any) -> Any:
    """Compute score discrimination and its fixed bootstrap intervals."""
    rng = PCG64(design["pcg64_initialization"])
    result = {}
    for batch, base in (("run006", 0), ("fresh", 12)):
        (one, two) = (groups[batch], groups[batch + "_code2"])
        (n1, n2) = (len(one), len(two))
        replicates = design["bootstrap_replicates"]
        w1 = [rng.multinomial(n1) for _ in range(replicates)]
        w2 = [rng.multinomial(n2) for _ in range(replicates)]
        for offset, score in ((0, 0), (1, 3)):
            (x, y) = ([r[score] for r in one], [r[score] for r in two])
            pairs = sum((2 * (b > a) + (b == a) for a in x for b in y))
            row = {"auc": pairs / (2 * n1 * n2)}
            if score == 3:
                values = sorted(set(x + y))
                positions = {v: i for (i, v) in enumerate(values)}
                (xp, yp) = ([positions[v] for v in x], [positions[v] for v in y])
                boot = []
                for a, b in zip(w1, w2):
                    (hx, hy) = ([0] * len(values), [0] * len(values))
                    for i, w in zip(xp, a):
                        hx[i] += w
                    for i, w in zip(yp, b):
                        hy[i] += w
                    (below, numerator) = (0, 0)
                    for wx, wy in zip(hx, hy):
                        numerator += wy * (2 * below + wx)
                        below += wx
                    boot.append(numerator / (2 * n1 * n2))
                row.update(
                    bootstrap_ci_low=quantile(boot, 0.025), bootstrap_ci_high=quantile(boot, 0.975)
                )
            result[str(base + offset)] = row
    return result


def render(macro: Any, value: Any) -> Any:
    """Render recorded numerical operands for comparison."""
    if isinstance(value, list):
        return "/".join((str(v) for v in value))
    if macro.endswith("Percent"):
        return rounded(value, 2, scale=100) + "\\%"
    if macro.endswith("TargetCount"):
        return str(value)
    return rounded(value, 3)


def run() -> Any:
    """Recompute and check the saved numerical evidence."""
    data = json.loads((BASE / "data.json").read_text())
    expected = json.loads((BASE / "expected.json").read_text())["rows"]
    targets = {i: frontier(data["groups"], r) for (i, r) in data["targets"].items()}
    auc = meaning(data["groups"], data["design"])
    (rendered, mismatches) = ({}, [])
    for row in expected:
        macro = row["macro"]
        if macro in data["design_macros"]:
            value = int(rounded(data["design"]["honest_n"] * data["design"]["target_retention"], 0))
        else:
            values = []
            for selector in row["source_selectors"]:
                (kind, index, key) = selector["path"]
                values.append((targets if kind == "targets" else auc)[str(index)][key])
            value = values if len(values) > 1 else values[0]
        text = render(macro, value)
        rendered[macro] = text
        equal = (
            value == row["value"]
            if isinstance(value, list)
            else math.isclose(value, row["value"], rel_tol=2e-12, abs_tol=2e-12)
        )
        if not equal or text != row["rendered"]:
            mismatches.append(
                {
                    "macro": macro,
                    "actual": value,
                    "expected": row["value"],
                    "rendered": text,
                    "expected_rendered": row["rendered"],
                }
            )
    return {"checked": len(expected), "mismatches": mismatches, "rendered": rendered}


def main() -> Any:
    """Run the command-line recount."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")
    raise SystemExit(bool(result["mismatches"]))


if __name__ == "__main__":
    main()
