"""Ensure every interval component uses the common numerical implementation."""

import pytest

from swaudit.analysis import statistics
from swaudit.headline.part1 import recompute as part1
from swaudit.headline.part2 import recompute as part2
from swaudit.headline.part3 import recompute as part3


def test_interval_components_delegate_to_shared_helper(monkeypatch):
    calls = []

    def interval(k, n, **kwargs):
        calls.append((k, n, kwargs))
        return [0.1, 0.9]

    monkeypatch.setattr(statistics, "exact_interval", interval)
    part2.interval.cache_clear()
    try:
        assert part1.exact_interval(3, 40, 95) == [0.1, 0.9]
        assert part2.interval(3, 40) == (0.1, 0.9)
        assert part3.exact95(3, 40) == [0.1, 0.9]
        assert len(calls) == 3
    finally:
        part2.interval.cache_clear()


@pytest.mark.parametrize("confidence", [0, 100, float("nan")])
def test_shared_interval_rejects_invalid_confidence(confidence):
    with pytest.raises(ValueError, match="confidence"):
        statistics.exact_interval(3, 40, confidence_percent=confidence)


def test_shared_interval_honors_nondefault_confidence():
    lower, upper = statistics.exact_interval(0, 10, confidence_percent=90)
    assert lower == 0
    assert upper == pytest.approx(1 - 0.05**0.1, abs=2e-14)
