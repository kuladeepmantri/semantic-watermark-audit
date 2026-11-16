"""Boundary, independent-statistic and corruption checks."""

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from swaudit import scan
from swaudit.analysis.frozen_rules import p20
from swaudit.analysis.statistics import exact_interval, paired

BASE = pathlib.Path(__file__).resolve().parents[1]


def seal(folder):
    records = folder / "data"
    files = [
        dict(
            path=p.relative_to(records).as_posix(),
            bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        )
        for p in sorted(records.rglob("*"))
        if p.is_file()
        and p.name not in {"MANIFEST.json", "__init__.py"}
        and "__pycache__" not in p.parts
    ]
    (records / "MANIFEST.json").write_text(
        json.dumps(dict(author="Kuladeep Mantri", files=files), indent=2) + "\n"
    )


class ReleaseChecks(unittest.TestCase):
    def run_copy(self, change=None, reseal=True, extra=()):
        with tempfile.TemporaryDirectory() as td:
            folder = pathlib.Path(td) / "candidate"
            shutil.copytree(
                BASE,
                folder,
                ignore=shutil.ignore_patterns(
                    ".git",
                    "__pycache__",
                    ".pytest_cache",
                    ".ruff_cache",
                    "*.egg-info",
                    "build",
                    "dist",
                ),
            )
            (folder / "src/swaudit/paths.py").write_text(
                'from pathlib import Path\nRECORDS=Path(__file__).resolve().parents[2]/"data"\n'
            )
            if change:
                change(folder)
            if reseal:
                seal(folder)
            out = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "swaudit.recompute",
                    *[str(folder / "data") if x == "<candidate>" else x for x in extra],
                ],
                capture_output=True,
                text=True,
                env=dict(
                    os.environ,
                    PYTHONPATH=str(folder / "src") + os.pathsep + str(folder),
                    PYTHONDONTWRITEBYTECODE="1",
                ),
            )
            return out.returncode, out.stdout + out.stderr

    def edit(self, folder, name, change):
        p = folder / "data/data" / name
        d = json.loads(p.read_text())
        change(d)
        p.write_text(json.dumps(d, allow_nan=False) + "\n")

    def test_baseline_isolated(self):
        code, out = self.run_copy()
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["mismatches"], 0)

    def test_duplicate_victim_fails(self):
        code, _ = self.run_copy(
            lambda f: self.edit(f, "selection1b.json", lambda d: d["rows"].append(d["rows"][0]))
        )
        self.assertNotEqual(code, 0)

    def test_lost_query_dropped_fails(self):
        code, _ = self.run_copy(lambda f: self.edit(f, "queries2.json", lambda d: d.pop()))
        self.assertNotEqual(code, 0)

    def test_score_change_fails_even_after_resealing(self):
        def mutate(d):
            r = next(
                r
                for r in d["rows"]
                if r["arm"] == "honest" and r["victim"] == "E000" and r["view"] == "B.png"
            )
            r["M"] = 0

        code, _ = self.run_copy(lambda f: self.edit(f, "exp1b.json", mutate))
        self.assertNotEqual(code, 0)

    def test_expected_change_fails(self):
        def change(f):
            p = f / "data/expected/repair-numbers.tex"
            p.write_text(
                p.read_text().replace(
                    "\\newcommand{\\RepOneBCalN}{40}", "\\newcommand{\\RepOneBCalN}{41}"
                )
            )

        code, out = self.run_copy(change)
        self.assertNotEqual(code, 0)
        self.assertIn("RepOneBCalN", out)

    def test_control_pair_change_fails(self):
        def mutate(d):
            d["paired"]["committed"][0]["changed"]["P20"] = True

        code, _ = self.run_copy(lambda f: self.edit(f, "regen4b.json", mutate))
        self.assertNotEqual(code, 0)

    def test_digest_change_fails(self):
        code, out = self.run_copy(
            lambda f: (f / "data/data/protocol.json").write_text("{}"), reseal=False
        )
        self.assertNotEqual(code, 0)
        self.assertIn("Manifest digest differs", out)

    def test_changed_protocol_produces_mismatch(self):
        code, out = self.run_copy(
            lambda f: self.edit(f, "protocol.json", lambda d: d.update(utility_floor=89))
        )
        self.assertNotEqual(code, 0)
        self.assertIn("RepOneBUtilityFloor", out)

    def test_output_cannot_overwrite_package(self):
        code, _ = self.run_copy(extra=("--output", "<candidate>"))
        self.assertNotEqual(code, 0)

    def test_p20_edges(self):
        self.assertTrue(p20(dict(readable=20, mismatch=0.06)))
        for r, m in [
            (19, 0.06),
            (20, 0.06000001),
            (20, None),
            (20, -0.01),
            (20, float("nan")),
            (20, float("inf")),
        ]:
            self.assertFalse(p20(dict(readable=r, mismatch=m)))

    def test_intervals_against_closed_form(self):
        for n in (1, 30, 40, 100, 200):
            self.assertAlmostEqual(exact_interval(0, n)[1], 1 - 0.025 ** (1 / n), places=12)
            self.assertAlmostEqual(exact_interval(n, n)[0], 0.025 ** (1 / n), places=12)
        self.assertAlmostEqual(paired([False] * 7, [True] * 7)["p_two_sided"], 0.015625)

    def test_required_scan_patterns_and_private_names(self):
        samples = [
            bytes(x).decode()
            for x in (
                [115, 107, 45],
                [99, 116, 120, 55, 115, 107, 45],
                [97, 112, 105, 45, 107, 101, 121],
                [116, 111, 107, 101, 110],
                [112, 97, 115, 115, 119, 111, 114, 100],
                [64, 103, 109, 97, 105, 108],
                [47, 85, 115, 101, 114, 115, 47],
            )
        ]
        for sample in samples:
            self.assertTrue(
                any(__import__("re").search(expr, sample) for expr in scan.PATTERNS.values())
            )
        with tempfile.TemporaryDirectory() as td:
            old = scan.BASE
            try:
                scan.BASE = pathlib.Path(td)
                (scan.BASE / "probe.md").write_text("Synthetic Person")
                self.assertEqual(scan.scan(["Synthetic Person"])["status"], "failed")
                (scan.BASE / "probe.md").write_text("harmless")
                self.assertEqual(scan.scan(["Synthetic Person"])["status"], "clean")
                (scan.BASE / "image.png").write_bytes(b"example")
                self.assertEqual(scan.scan()["status"], "failed")
            finally:
                scan.BASE = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
