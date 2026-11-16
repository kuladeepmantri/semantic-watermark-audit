"""Load the frozen thresholds used by every recount."""

import json
import math
from functools import lru_cache
from typing import Any

from swaudit.paths import RECORDS


@lru_cache(maxsize=1)
def protocol() -> dict[str, Any]:
    """Read the protocol once per process; validation happens before each recount."""
    return json.loads((RECORDS / "data/protocol.json").read_text())


def cutoff(name: str) -> int | float:
    """Return a declared numerical threshold, rejecting absent or invalid entries."""
    value = protocol()[name]
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Invalid protocol cutoff: " + name)
    return value


def rule_definitions() -> dict[str, dict[str, list[Any]]]:
    """Build named rules from the protocol's single set of threshold values."""
    primary = {"M": ["gt", cutoff("local_m")], "C_corrected": ["ge", cutoff("local_c")]}
    return dict(
        primary=primary,
        primary_strength=dict(primary, N_any=["ge", cutoff("strength_min")]),
        paper_corrected={
            "M": ["gt", cutoff("published_m")],
            "C_corrected": ["ge", cutoff("published_c")],
        },
        paper_released={
            "M": ["gt", cutoff("published_m")],
            "C_released": ["ge", cutoff("released_c")],
        },
    )
