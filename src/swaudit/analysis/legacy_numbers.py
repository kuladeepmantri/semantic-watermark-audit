"""Render pinned audited numeric selectors without private source files."""

import hashlib
import json
import re
from typing import Any

from swaudit.analysis.format_numbers import formatted


def render(snapshot: Any, operands: Any) -> Any:
    """Render recorded numerical operands for comparison."""
    (numbers, tex) = ({}, ["% Generated for Kuladeep Mantri from audited numeric selectors."])
    for record in snapshot["records"]:
        name = record["macro"]
        if not re.fullmatch("[A-Za-z]+", name) or name in numbers:
            raise ValueError("Invalid or duplicate paper macro")
        refs = record["provenance"]
        values = []
        for ref in refs:
            selector = {
                k: ref[k]
                for k in (
                    "source",
                    "path",
                    "pattern",
                    "group",
                    "csv_numeric",
                    "aggregate",
                    "column",
                    "where",
                    "q",
                    "gates",
                )
                if k in ref
            }
            key = hashlib.sha256(json.dumps(selector, sort_keys=True).encode()).hexdigest()
            operand = operands["operands"][key]
            if operand["selector"] != selector:
                raise ValueError("Numeric selector identity differs")
            values.append(operand["value"])
        op = record.get("operation")
        if op == "fraction":
            value = values
        elif op == "ratio":
            value = values[0] / values[1]
        elif op == "subtract":
            value = values[0] - values[1]
        elif op is None:
            value = values[0]
        else:
            raise ValueError("Unknown numeric operation")
        rendered = formatted(value, record)
        if rendered != record["reference_rendered"]:
            raise ValueError("Number renderer disagrees with the source catalog")
        if snapshot["source_inputs"][record["audit"]] != record["audit_sha256"]:
            raise ValueError("Unbound audit")
        for ref in record["provenance"]:
            if snapshot["source_inputs"][ref["source"]] != ref["sha256"]:
                raise ValueError("Unbound source")
        numbers[name] = {
            "value": value,
            "rendered": rendered,
            "source": record["source"],
            "audit": record["audit"],
            "audit_scope": record["audit_scope"],
        }
        tex.extend(
            [
                "% source: " + record["source"],
                "% audit: " + record["audit"],
                "\\newcommand{\\" + name + "}{" + rendered + "}",
            ]
        )
    return (numbers, "\n".join(tex) + "\n")
