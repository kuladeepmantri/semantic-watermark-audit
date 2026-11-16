"""Integration failure checks for four-part release."""

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

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


class IntegrationChecks(unittest.TestCase):
    def run_copy(self, change=None):
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
            seal(folder)
            child = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "swaudit.recompute_all",
                    "--output",
                    str(pathlib.Path(td) / "result"),
                ],
                cwd=td,
                capture_output=True,
                text=True,
                env=dict(
                    os.environ,
                    PYTHONPATH=str(folder / "src") + os.pathsep + str(folder),
                    PYTHONDONTWRITEBYTECODE="1",
                ),
            )
            return child.returncode, json.loads(child.stdout)

    def test_complete_package_without_checkout(self):
        code, result = self.run_copy()
        self.assertEqual(code, 0, result)
        self.assertEqual(
            result["used_macros"],
            len(json.loads((BASE / "data/data/used-macros.json").read_text())["used"]),
        )
        self.assertEqual(result["checked"], result["used_macros"])
        self.assertEqual(result["mismatches"], 0)
        self.assertEqual(result["uncovered"], [])

    def test_missing_part_cannot_fall_back(self):
        def change(folder):
            shutil.move(
                str(folder / "src/swaudit/headline/part2/recompute.py"),
                str(folder.parent / "withheld.py"),
            )

        code, result = self.run_copy(change)
        self.assertNotEqual(code, 0)
        self.assertIn("Missing headline/part2", result["error"])

    def test_failed_component_cannot_fall_back(self):
        def change(folder):
            (folder / "src/swaudit/headline/part1/recompute.py").write_text("raise SystemExit(1)\n")

        code, result = self.run_copy(change)
        self.assertNotEqual(code, 0)
        self.assertIn("part1 failed", result["error"])

    def test_wrong_component_values_are_compared(self):
        def change(folder):
            part = folder / "src/swaudit/headline/part1/recompute.py"
            r = json.loads(
                subprocess.check_output(
                    [sys.executable, "-B", str(part)],
                    text=True,
                    env=dict(os.environ, PYTHONPATH=str(folder / "src")),
                )
            )
            name = next(iter(r["rendered"]))
            r["rendered"][name] = "999"
            part.write_text("import json\nprint(json.dumps(" + repr(r) + "))\n")

        code, result = self.run_copy(change)
        self.assertNotEqual(code, 0)
        self.assertGreater(result["mismatches"], 0)

    def test_duplicate_partition_fails(self):
        def change(folder):
            part = folder / "src/swaudit/headline/part2/recompute.py"
            r = json.loads(
                subprocess.check_output(
                    [sys.executable, "-B", str(part)],
                    text=True,
                    env=dict(os.environ, PYTHONPATH=str(folder / "src")),
                )
            )
            other = json.loads(
                subprocess.check_output(
                    [sys.executable, "-B", str(folder / "src/swaudit/headline/part1/recompute.py")],
                    text=True,
                    env=dict(os.environ, PYTHONPATH=str(folder / "src")),
                )
            )
            name = next(iter(other["rendered"]))
            r["rendered"][name] = other["rendered"][name]
            part.write_text("import json\nprint(json.dumps(" + repr(r) + "))\n")

        code, result = self.run_copy(change)
        self.assertNotEqual(code, 0)
        self.assertIn("Duplicate macro", result["error"])


class ReviewIntegrationChecks(unittest.TestCase):
    run_copy = IntegrationChecks.run_copy

    def test_unexpected_derived_selector_path_fails(self):
        def change(folder):
            path = folder / "data/data/used-selectors.json"
            record = json.loads(path.read_text())
            source = next(
                key
                for key, value in record["sources"].items()
                if value["path"] == "paper/build/numbers/MASTER-TABLE.json"
            )
            row = next(
                row
                for row in record["records"]
                if any(ref["source"] == source for ref in row["refs"])
            )
            next(ref for ref in row["refs"] if ref["source"] == source)["path"] = ["missing_field"]
            path.write_text(json.dumps(record))

        code, result = self.run_copy(change)
        self.assertNotEqual(code, 0)
        self.assertIn("Unresolved derived selector", result["error"])

    def test_renamed_source_cannot_downgrade_to_replay(self):
        def change(folder):
            path = folder / "data/data/used-selectors.json"
            record = json.loads(path.read_text())
            source = next(
                value
                for value in record["sources"].values()
                if value["path"] == "paper/build/numbers/MASTER-TABLE.json"
            )
            source["path"] = "missing-source.json"
            path.write_text(json.dumps(record))

        code, result = self.run_copy(change)
        self.assertNotEqual(code, 0)
        self.assertIn("Undeclared crosscheck source", result["error"])

    def test_new_inventory_macro_is_reported_uncovered(self):
        def change(folder):
            path = folder / "data/data/used-macros.json"
            record = json.loads(path.read_text())
            record["used"].append("NewUncomputedCount")
            path.write_text(json.dumps(record))

        code, result = self.run_copy(change)
        self.assertNotEqual(code, 0)
        self.assertIn("NewUncomputedCount", result["uncovered"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
