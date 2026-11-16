"""Extract numerical macro usage from a manuscript's input graph."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

DEFINITION = re.compile(r"^\\(?:new|renew|provide)command\{\\([A-Za-z]+)\}\{(.*)\}$", re.M)
COMMAND = re.compile(r"\\([A-Za-z]+)")
INPUT = re.compile(r"\\(?:input|include)\{([^}]+)\}")


def uncomment(text: str) -> str:
    """Remove TeX comments while preserving escaped percent signs and line numbers."""
    return "\n".join(re.split(r"(?<!\\)%", line, maxsplit=1)[0] for line in text.splitlines())


def collect(main: Path) -> dict[str, Any]:
    """Walk local input files and record used numeric definitions and source hashes."""
    main = main.resolve()
    files: dict[Path, str] = {}

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in files:
            return
        text = path.read_text()
        files[path] = text
        for name in INPUT.findall(uncomment(text)):
            child = path.parent / name
            if not child.suffix:
                child = child.with_suffix(".tex")
            visit(child)

    visit(main)
    providers = {}
    sources = {}
    for path, text in files.items():
        clean = uncomment(text)
        definitions = dict(DEFINITION.findall(clean))
        if definitions and all(
            re.fullmatch(
                r"\\(?:new|renew|provide)command\{\\[A-Za-z]+\}(?:\[[0-9]+\])?\{.*\}", line.strip()
            )
            for line in clean.splitlines()
            if line.strip()
        ):
            providers[path] = definitions
        else:
            sources[path] = clean
    values = {}
    for definitions in providers.values():
        for name, value in definitions.items():
            if name in values and values[name] != value:
                raise ValueError("Conflicting numeric definition: " + name)
            values[name] = value
    occurrences = {}
    for path, text in sources.items():
        relative = Path(os.path.relpath(path, main.parent)).as_posix()
        for line, content in enumerate(text.splitlines(), 1):
            for name in set(COMMAND.findall(content)) & values.keys():
                occurrences.setdefault(name, []).append({"path": relative, "line": line})

    def receipt(path: Path) -> dict[str, str]:
        return dict(
            path=Path(os.path.relpath(path, main.parent)).as_posix(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )

    return dict(
        used=sorted(occurrences),
        occurrences=occurrences,
        values=values,
        tex_sources=[receipt(p) for p in sources],
        definition_sources=[dict(receipt(p), definitions=len(d)) for p, d in providers.items()],
    )
