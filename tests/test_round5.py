"""Boundary and corruption tests for the added saved-record recounts."""

from copy import deepcopy

import pytest

from swaudit.round5 import baseline_decisions, baselines, load, reproduction, run, whitebox


def test_paper_counts():
    result = run()
    assert result["whitebox"]["masked"]["accepted"]["P20"] == 30
    assert result["whitebox"]["iterative"]["accepted"]["conjunction"] == 25
    assert result["reproduction"]["clean"]["strict"] == 13
    assert result["external"]["exp1b_jpeg75"]["accepted"]["external_S"] == 100
    assert result["external"]["exp2_csi_any_query"]["n"] == 40
    assert result["distortions"]["crop90"]["accepted"]["embedded_P20"] == 0


def test_duplicate_whitebox_pair_rejected():
    rows = load("whitebox")["rows"]
    rows[-1] = deepcopy(rows[0])
    with pytest.raises(ValueError, match="Duplicate"):
        whitebox(rows)


def test_reproduction_boundary_and_missing_control():
    rows = load("seal-repro")["rows"]
    assert reproduction(rows)["clean"]["inclusive"] == 14
    with pytest.raises(ValueError, match="denominator"):
        reproduction(rows[:-1])


def test_changed_scalar_rejected_even_with_saved_decision():
    rows = load("whitebox")["rows"]
    rows[0]["M"] = 1024
    with pytest.raises(ValueError, match="decisions differ"):
        whitebox(rows)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_invalid_external_score_rejected(value):
    row = load("external")["rows"][0]
    row["external_S_mismatch"] = value
    with pytest.raises(ValueError, match="Invalid scalar"):
        baseline_decisions(row)


def test_altered_aggregate_rejected():
    record = load("external")
    record["groups"]["exp1b_jpeg75"]["accepted"]["external_S"] = 99
    with pytest.raises(ValueError, match="aggregate differs"):
        baselines(record)


def test_distortion_missing_or_duplicate_row_rejected():
    record = load("distortions")
    with pytest.raises(ValueError, match="row count"):
        baselines(dict(record, rows=record["rows"][:-1]), True)
    record["rows"][-1] = deepcopy(record["rows"][0])
    with pytest.raises(ValueError, match="Duplicate"):
        baselines(record, True)


def test_external_cutoffs_are_inclusive():
    row = dict(
        readable=20,
        embedded_mismatch=0.06,
        external_S_mismatch=0.06,
        external_B_mismatch=0.06,
        dhash_distance=1,
        rgb_score=0.02416506328451865,
        decisions=dict(embedded_P20=True, external_S=True, external_B=True, dhash=True, rgb=True),
    )
    assert all(baseline_decisions(row).values())


def test_distortion_pairing_cannot_change_between_transforms():
    record = load("distortions")
    record["rows"][0]["victim"] = "unpaired"
    with pytest.raises(ValueError, match="paired victim sets"):
        baselines(record, True)
