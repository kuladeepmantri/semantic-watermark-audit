"""Pinned number and identifier formatting."""

import math
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def rounded(
    value: int | float,
    places: int,
    *,
    scale: int | float = 1,
    percent: bool = False,
    scientific: bool = False,
) -> str:
    """Round decimal text half upward; scale before rounding."""
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Cannot round a nonfinite number")
    number = Decimal(str(value)) * Decimal(str(scale))
    if scientific:
        exponent = number.adjusted() if number else 0
        mantissa = number.scaleb(-exponent).quantize(
            Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP
        )
        if abs(mantissa) >= 10:
            mantissa /= 10
            exponent += 1
        return f"{mantissa:.{places}f}e{exponent:+03d}"
    number = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f"{number:.{places}f}" + (r"\%" if percent else "")


def formatted(value: Any, spec: dict[str, Any]) -> str:
    """Format a value using its declared display specification."""
    if spec.get("format") == "identifier":
        if not isinstance(value, str) or not re.fullmatch("[A-Za-z0-9][A-Za-z0-9._/-]*", value):
            raise ValueError("Unsafe or invalid identifier: " + spec["id"])
        if not re.fullmatch(spec.get("identifier_pattern", ".+"), value):
            raise ValueError("Identifier does not match its declared kind: " + spec["id"])
        prefix = spec.get("display_prefix", len(value))
        if (
            isinstance(prefix, bool)
            or not isinstance(prefix, int)
            or (not 0 < prefix <= len(value))
        ):
            raise ValueError("Invalid identifier display prefix: " + spec["id"])
        return value[:prefix].replace("_", "\\_")
    if spec.get("format") == "fraction":
        if (
            len(value) != 2
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or int(v) != v for v in value
            )
            or not 0 <= value[0] <= value[1]
            or value[1] <= 0
        ):
            raise ValueError("Invalid numeric fraction")
        return f"{int(value[0])}/{int(value[1])}"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (not math.isfinite(value)):
        raise ValueError("Expected a finite number: " + str(spec["id"]))
    if spec.get("format") == "integer":
        if int(value) != value:
            raise ValueError("Nonintegral count: " + spec["id"])
        return str(int(value))
    if spec.get("format") == "exact":
        return str(value)
    return rounded(
        value,
        spec.get("places", 2),
        scale=spec.get("scale", 1),
        percent=spec.get("unit") == "percent",
    )
