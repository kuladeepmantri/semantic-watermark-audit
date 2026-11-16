"""Locate bundled evaluation records."""

from pathlib import Path

from swaudit import records

RECORDS = Path(records.__file__).resolve().parent
