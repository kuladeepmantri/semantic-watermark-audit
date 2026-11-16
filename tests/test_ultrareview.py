"""Regression checks for manuscript coverage and failed recounts."""

import importlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest

from swaudit import inventory, recompute, recompute_all, round5, round6
from swaudit.analysis import headline, headline_crosscheck, statistics
from swaudit.protocol import protocol


@pytest.mark.parametrize("placement", ["main", "section", "numbers"])
def test_mixed_file_definitions_remain_in_inventory(tmp_path, placement):
    main = tmp_path / "main.tex"
    definition = "\\newcommand{\\NewCount}{5}\n"
    main.write_text("\\documentclass{article}\n\\input{numbers}\n\\input{section}\n")
    (tmp_path / "numbers.tex").write_text("\\newcommand{\\ExistingCount}{2}\n")
    (tmp_path / "section.tex").write_text("\\NewCount and \\ExistingCount\n")
    path = tmp_path / (placement + ".tex")
    path.write_text("\\relax\n" + definition + path.read_text())
    result = inventory.collect(main)
    assert result["used"] == ["ExistingCount", "NewCount"]
    assert result["values"]["NewCount"] == "5"
    assert len(result["occurrences"]["NewCount"]) == 1


@pytest.mark.parametrize(
    "definition", ["  \\newcommand{\\NewCount}{5}", "\\newcommand{\\NewCount}{5} % source"]
)
def test_whitespace_and_comments_do_not_drop_definitions(tmp_path, definition):
    main = tmp_path / "main.tex"
    main.write_text("\\input{numbers}\n\\NewCount\n")
    (tmp_path / "numbers.tex").write_text("\\newcommand{\\ExistingCount}{2}\n" + definition + "\n")
    result = inventory.collect(main)
    assert result["used"] == ["NewCount"]
    assert result["values"]["NewCount"] == "5"


def test_nested_inputs_resolve_from_document_root(tmp_path):
    (tmp_path / "sections/sections").mkdir(parents=True)
    main = tmp_path / "main.tex"
    main.write_text("\\input{sections/results}\n\\NewCount\n")
    (tmp_path / "sections/results.tex").write_text("\\input{sections/table}\n")
    (tmp_path / "sections/table.tex").write_text("\\newcommand{\\NewCount}{5}\n")
    (tmp_path / "sections/sections/table.tex").write_text("\\newcommand{\\NewCount}{999}\n")
    assert inventory.collect(main)["values"]["NewCount"] == "5"


def test_standalone_round5_rejects_record_digest_change(tmp_path, monkeypatch):
    records = tmp_path / "records"
    shutil.copytree(recompute.BASE, records)
    path = records / "round5/whitebox.json"
    path.write_text(path.read_text() + "\n")
    monkeypatch.setattr(recompute, "BASE", records)
    monkeypatch.setattr(round5, "RECORDS", records)
    with pytest.raises(ValueError, match="Manifest digest differs"):
        round5.main()


@pytest.mark.parametrize(
    "module_name, operation",
    [
        ("swaudit.recompute_all", "run"),
        ("swaudit.recompute", "analyze"),
        ("swaudit.analysis.headline_crosscheck", "run"),
    ],
)
@pytest.mark.parametrize("error", [ValueError, TypeError])
def test_failed_run_invalidates_previous_outputs(
    tmp_path, monkeypatch, module_name, operation, error
):
    module = importlib.import_module(module_name)
    out = tmp_path / "output"
    out.mkdir()
    (out / "RESULT.json").write_text(json.dumps({"status": "PASS"}))
    exports = ["numbers-used.tex", "numbers-all.tex", "repair-numbers.tex", "DETAILS.json"]
    for name in exports:
        (out / name).write_text("stale")
    (out / "unrelated.txt").write_text("keep")

    def fail(*args, **kwargs):
        raise error("synthetic validation failure")

    monkeypatch.setattr(module, operation, fail)
    monkeypatch.setattr(sys, "argv", ["recount", "--output", str(out)])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 1
    report = json.loads((out / "RESULT.json").read_text())
    assert report["status"] == "FAIL"
    assert "synthetic validation failure" in report["error"]
    assert not any((out / name).exists() for name in exports)
    assert (out / "unrelated.txt").read_text() == "keep"


def test_component_mismatch_keeps_json_diagnostics(monkeypatch):
    mismatch = dict(macro="ExampleCount", actual="2", expected="1")
    child = SimpleNamespace(returncode=1, stdout=json.dumps(dict(mismatches=[mismatch])), stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: child)
    with pytest.raises(ValueError) as exc:
        recompute_all.run_part(1)
    assert "ExampleCount" in str(exc.value)
    assert '"actual": "2"' in str(exc.value)
    assert '"expected": "1"' in str(exc.value)


@pytest.mark.parametrize("length", [0, 1, 3])
def test_precision_requires_two_interval_bounds(length):
    summary = round5.load("seal-repro-summary")
    interval = summary["precision"]["saved_fp16"]["exact_95_ci"]
    summary["precision"]["saved_fp16"]["exact_95_ci"] = (interval + [1])[:length]
    with pytest.raises(ValueError, match="interval"):
        round6.precision(round5.load("seal-repro-final"), summary)


def test_precision_requires_all_ablation_variants():
    summary = round5.load("seal-repro-summary")
    del summary["precision"]["saved_fp16"]
    with pytest.raises(ValueError, match="variant"):
        round6.precision(round5.load("seal-repro-final"), summary)


@pytest.mark.parametrize("mutation", ["empty_path", "suffix_source"])
def test_crosscheck_cannot_bypass_source_policy(monkeypatch, mutation):
    original = headline_crosscheck.read
    selectors = deepcopy(original("used-selectors.json"))
    policy = original("crosscheck-policy.json")
    row = next(
        r
        for r in selectors["records"]
        if r["macro"] not in policy["required_row_checked_macros"] and r["refs"]
    )
    ref = row["refs"][0]
    source_id = "synthetic_source"
    source = (
        "paper/build/numbers/MASTER-TABLE.json"
        if mutation == "empty_path"
        else "undeclared/a4_verifiers_and_geometry.json"
    )
    selectors["sources"][source_id] = {"path": source}
    ref.update(source=source_id, path=[])
    monkeypatch.setattr(
        headline_crosscheck,
        "read",
        lambda name: selectors if name == "used-selectors.json" else original(name),
    )
    with pytest.raises(ValueError, match="Empty derived selector|Undeclared crosscheck source"):
        headline_crosscheck.run()


def test_prediction_model_uses_protocol_parameters(monkeypatch):
    config = protocol()
    for name, value in dict(local_m=4, published_m=13, patch_count=64, bit_exponent=3).items():
        monkeypatch.setitem(config, name, value)
    calls = []

    def survival(cut, n, probability):
        calls.append((cut, n, probability))
        return 0.25

    monkeypatch.setattr(statistics, "binomial_sf", survival)
    result = headline.primary_sources({})[3]["P1"]
    assert set(result) == {"M_gt_4", "M_gt_13"}
    calls = calls[-400:]
    assert len(calls) == 400
    assert {n for _, n, _ in calls} == {64}
    row = next(
        r for r in recompute.read("headline-run005.json")["rows"] if r["condition"] == "clean"
    )
    assert calls[0][2] == pytest.approx((1 - row["theta"] / 180) ** 3 * row["oracle"] / 64)


@pytest.mark.parametrize("missing", ["local_m", "published_m", "patch_count", "bit_exponent"])
def test_prediction_model_requires_protocol_parameters(monkeypatch, missing):
    monkeypatch.delitem(protocol(), missing, raising=False)
    with pytest.raises((KeyError, ValueError), match=missing):
        headline.primary_sources({})
