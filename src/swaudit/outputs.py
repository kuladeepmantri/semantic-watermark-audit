"""Invalidate generated artifacts when a recount does not complete."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ARTIFACTS = (
    "numbers-used.tex",
    "numbers-all.tex",
    "repair-numbers.tex",
    "numbers-used.diff",
    "repair-numbers.diff",
    "DETAILS.json",
)


def write_report(out: Path, report: dict) -> None:
    """Write the status read by downstream consumers."""
    (out / "RESULT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def clear_exports(out: Path) -> None:
    """Remove only known recount products, leaving unrelated files untouched."""
    for name in ARTIFACTS:
        (out / name).unlink(missing_ok=True)


@contextmanager
def output_run(out: Path | None, records: Path) -> Iterator[None]:
    """Make failure explicit and prevent previous exports surviving a failed run."""
    prepared = False
    try:
        if out is not None:
            if out.resolve().is_relative_to(records.resolve()):
                raise ValueError("Output must stay outside immutable records")
            out.mkdir(parents=True, exist_ok=True)
            prepared = True
            write_report(out, dict(status="FAIL", error="Recount has not completed"))
            clear_exports(out)
        yield
    except Exception as exc:
        report = dict(author="Kuladeep Mantri", status="FAIL", error=str(exc))
        if prepared:
            try:
                write_report(out, report)
                clear_exports(out)
            except OSError as output_error:
                report["output_error"] = str(output_error)
        print(json.dumps(report, indent=2))
        raise SystemExit(1) from exc
