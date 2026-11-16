"""Extract numerical macro usage from a manuscript's input graph."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

DEFINITION = re.compile(
    r"^\\(new|renew|provide)command\{\\([A-Za-z]+)\}"
    r"(?:\[([0-9]+)\](?:\[[^\]]*\])?)?\{(.*)\}$"
)
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
            child = main.parent / name
            if not child.suffix:
                child = child.with_suffix(".tex")
            visit(child)

    visit(main)
    providers = {}
    sources = {}
    values = {}
    alternatives: dict[str, set[str]] = {}
    for path, text in files.items():
        definitions = {}
        lines = []
        for line in uncomment(text).splitlines():
            match = DEFINITION.fullmatch(line.strip())
            if not match:
                lines.append(line)
                continue
            lines.append("")
            kind, name, arguments, value = match.groups()
            if arguments is not None:
                continue
            # Formatting and symbolic aliases are not exported numerical values.
            if not re.search(r"[0-9]", value) and re.search(r"\\[A-Za-z]+", value):
                continue
            if kind == "provide" and name in values:
                continue
            definitions[name] = value
            values[name] = value
            alternatives.setdefault(name, set()).add(value)
        if definitions:
            providers[path] = definitions
        if any(line.strip() for line in lines):
            sources[path] = "\n".join(lines)
    occurrences = {}
    for path, text in sources.items():
        relative = Path(os.path.relpath(path, main.parent)).as_posix()
        for line, content in enumerate(text.splitlines(), 1):
            for name in set(COMMAND.findall(content)) & values.keys():
                occurrences.setdefault(name, []).append({"path": relative, "line": line})

    for name in occurrences:
        if len(alternatives[name]) != 1:
            raise ValueError("Conflicting numeric definition: " + name)

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
