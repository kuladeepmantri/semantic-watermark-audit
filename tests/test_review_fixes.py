"""Regression tests for validation, privacy and numerical consistency."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from swaudit import scan
from swaudit.analysis.format_numbers import formatted, rounded
from swaudit.analysis.frozen_rules import p20
from swaudit.analysis.headline import rules
from swaudit.analysis.statistics import exact_interval
from swaudit.inventory import collect
from swaudit.protocol import protocol
from swaudit.recompute import closest_rejected_mismatch
from swaudit.round5 import load
from swaudit.round6 import precision


@pytest.mark.parametrize(
    "variant",
    [
        "Sýnthétic Persön",
        "synthetic_person",
        "SYNTHETIC.PERSON",
        "synthetic-person",
        "Synthetic\nPerson",
    ],
)
def test_private_names_match_json_escapes_and_separators(tmp_path, monkeypatch, variant):
    monkeypatch.setattr(scan, "BASE", tmp_path)
    (tmp_path / "sample.json").write_text(json.dumps({"rater": variant}, ensure_ascii=True))
    result = scan.scan(["Synthetic Person"])
    assert result["status"] == "failed"
    assert any(r["rule"] == "private_name" and r["line"] == 1 for r in result["findings"])
    assert variant not in json.dumps(result)


def test_encoded_credential_prefix_is_detected_without_echo(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "BASE", tmp_path)
    prefix = "".join(chr(n) for n in [115, 107, 45])
    encoded = "".join("\\u" + format(ord(c), "04x") for c in prefix)
    (tmp_path / "sample.json").write_text('{"value": "' + encoded + 'synthetic"}')
    result = scan.scan()
    assert any(r["rule"] == "rule_09" for r in result["findings"])
    assert prefix not in json.dumps(result)


def test_scanner_checks_private_filename_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "BASE", tmp_path)
    (tmp_path / "synthetic_person.json").write_text("{}")
    assert any(
        r["rule"] == "private_name" and r["line"] == 0
        for r in scan.scan(["Synthetic Person"])["findings"]
    )


def test_scanner_accepts_repository_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "BASE", tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text("name: Check\n")
    (tmp_path / "LICENSE").write_text("MIT License\n")
    (tmp_path / ".gitignore").write_text("build/\n")
    (tmp_path / ".gitattributes").write_text("* text eol=lf\n")
    assert scan.scan()["status"] == "clean"


def test_payload_counts_use_protocol_thresholds(monkeypatch):
    config = protocol()
    row = dict(readable=19, mismatch=0.05)
    assert not p20(row)
    monkeypatch.setitem(config, "readable_floor", 19)
    assert p20(row)
    monkeypatch.setitem(config, "mismatch_cutoff", 0.04)
    assert not p20(row)


def test_named_rules_use_protocol_and_reject_missing_scores(monkeypatch):
    row = dict(M=3, C_corrected=7, N_any=388)
    assert not rules(row, ("primary",))["primary"]
    monkeypatch.setitem(protocol(), "local_m", 2)
    assert rules(row, ("primary",))["primary"]
    with pytest.raises(KeyError, match="C_released"):
        rules(row)


def test_decimal_ties_share_one_rounding_policy():
    assert rounded(0.125, 0, scale=100) == "13"
    assert rounded(-12.5, 0) == "-13"
    assert formatted(0.125, {"id": "test", "scale": 100, "places": 0}) == "13"
    assert rounded(9.99e-5, 1, scientific=True) == "1.0e-04"


def test_interior_exact_interval():
    lower, upper = exact_interval(3, 40)
    assert lower == pytest.approx(0.015742179851041, abs=2e-14)
    assert upper == pytest.approx(0.203864748732899, abs=2e-14)


def test_closest_rejection_excludes_accepted_and_nonfinite():
    rows = [
        dict(readable=25, mismatch=0.01),
        dict(readable=25, mismatch=float("nan")),
        dict(readable=25, mismatch=0.12),
        dict(readable=25, mismatch=0.15),
    ]
    assert closest_rejected_mismatch(rows) == 0.12
    assert closest_rejected_mismatch(list(reversed(rows))) == 0.12
    with pytest.raises(ValueError, match="No finite"):
        closest_rejected_mismatch(rows[:2])


def test_optimized_python_keeps_integrity_checks():
    program = """
from swaudit.headline.part2.recompute import PCG64
from swaudit.headline.part3.recompute import derive
from swaudit.paths import RECORDS
import json
try:
    PCG64({'state': 1, 'inc': 1}).binomial(100, .5)
except ValueError:
    pass
else:
    raise RuntimeError('Binomial precondition disappeared')
data=json.loads((RECORDS/'headline/part3/data.json').read_text())
data['friend']['repeat_disagreement_histogram']['0'] += 1
try:
    derive(data)
except ValueError:
    pass
else:
    raise RuntimeError('Panel count validation disappeared')
"""
    child = subprocess.run([sys.executable, "-O", "-c", program], capture_output=True, text=True)
    assert child.returncode == 0, child.stdout + child.stderr


def test_final_precision_summary_is_checked_against_rows():
    summary = load("seal-repro-summary")
    actual = precision(load("seal-repro-final"), summary)
    assert actual["fresh_fp16"] == actual["fresh_fp32"] == dict(n=20, strict=13)
    changed = deepcopy(summary)
    changed["precision"]["fresh_fp32"]["k"] = 14
    with pytest.raises(ValueError, match="Precision count"):
        precision(load("seal-repro-final"), changed)


def test_inventory_tracks_inputs_and_new_numeric_macros(tmp_path):
    (tmp_path / "main.tex").write_text("\\input{numbers}\n\\input{section}\n")
    (tmp_path / "numbers.tex").write_text(
        "\\newcommand{\\OneCount}{1}\n\\newcommand{\\TwoCount}{2}\n\\providecommand{\\Wrap}[1]{#1}\n"
    )
    (tmp_path / "section.tex").write_text("\\OneCount{} % \\TwoCount{}\n")
    before = collect(tmp_path / "main.tex")
    assert before["used"] == ["OneCount"]
    (tmp_path / "section.tex").write_text("\\OneCount{} and \\TwoCount{}\n")
    after = collect(tmp_path / "main.tex")
    assert after["used"] == ["OneCount", "TwoCount"]
    assert after["tex_sources"] != before["tex_sources"]


def test_no_assert_based_validation_in_package():
    import ast

    from swaudit import __file__ as package_file

    for path in Path(package_file).parent.rglob("*.py"):
        assert not any(
            isinstance(node, ast.Assert) for node in ast.walk(ast.parse(path.read_text()))
        )
