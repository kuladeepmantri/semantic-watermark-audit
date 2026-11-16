"""Scan distribution files without displaying matching content."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import unicodedata
from collections.abc import Iterator, Sequence
from typing import Any

BASE = pathlib.Path(__file__).resolve().parents[2]
if not (BASE / "pyproject.toml").is_file():
    BASE = pathlib.Path(__file__).resolve().parent
# Escape scanner signatures so their definitions do not match their own source.
PATTERNS = {
    "rule_01": "-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "rule_02": "\\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\\b",
    "rule_03": "\\b(?:\x41KIA|ASIA)[A-Z0-9]{16}\\b",
    "rule_04": "\\bAIza[A-Za-z0-9_-]{30,}\\b",
    "rule_05": "\\bxox[baprs]-[A-Za-z0-9-]{20,}\\b",
    "rule_06": "\\beyJ[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}\\b",
    "rule_07": "(?i)https?://[^\\s/:]+:[^\\s/@]+@",
    "rule_08": "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}\\b",
    "rule_09": "(?i)\\x73k-",
    "rule_10": "(?i)\x63tx7\\x73k-",
    "rule_11": "(?i)api\\x2dkey",
    "rule_12": "(?i)\\x74oken",
    "rule_13": "(?i)\\x70assword",
    "rule_14": "(?i)@g\\x6dail",
    "rule_15": "/\\x55sers/",
    "private_login": "(?i)\\x6bmantri",
    "credential_prefix": "\\x63tx7|\\x67hp_|\\x41KIA",
    "rule_16": "(?i)(?:api[_-]?key|access[_-]?\\x74oken|client[_-]?secret|\\x70assword)\\s*[:=]\\s*[\"'][A-Za-z0-9_+/=-]{16,}[\"']",
}
EXTENSIONS = {".py", ".json", ".md", ".tex", ".toml", ".yml", ".yaml", ".cff", ".txt", ""}
# Reviewed binaries allowed in the distribution, pinned by SHA-256.
PINNED_BINARIES = {
    "paper/semantic-watermark-audit.pdf": "19e74a8d0e4cb5fd9b3a16960c946c649966e7e8ab58ff416671afdd1fb5607e",
}
IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist"}


def normalized(text: str) -> str:
    """Fold accents, case and common name separators for privacy matching."""
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )
    return re.sub(r"[\s._-]+", " ", folded)


def views(text: str, is_json: bool) -> Iterator[tuple[str, int, bool]]:
    """Yield raw lines and decoded JSON strings at their original line numbers."""
    yield text, 1, False
    if is_json:
        json.loads(text)
        for match in re.finditer(r'"(?:\\.|[^"\\])*"', text):
            if "\\" not in match.group():
                continue
            value = json.loads(match.group())
            yield value, text.count("\n", 0, match.start()) + 1, True


def scan(names: Sequence[str] = ()) -> dict[str, Any]:
    """Return file locations and rule names for every unsafe match."""
    findings = set()
    files = []
    size = 0

    def walk(folder: pathlib.Path) -> Iterator[pathlib.Path]:
        for path in sorted(folder.iterdir()):
            if path.name in IGNORED or path.name.endswith(".egg-info"):
                continue
            if path.is_symlink() or path.is_file():
                yield path
            elif path.is_dir():
                yield from walk(path)

    name_patterns = [
        re.compile(
            r"(?<![a-z0-9])"
            + r"[\s._-]+".join(re.escape(word) for word in normalized(n).split())
            + r"(?![a-z0-9])"
        )
        for n in names
        if n.strip()
    ]
    for path in walk(BASE):
        relative = path.relative_to(BASE)
        rel = relative.as_posix()
        files.append(rel)
        if path.is_symlink():
            findings.add((rel, 0, "symlink"))
            continue
        if rel in PINNED_BINARIES:
            if hashlib.sha256(path.read_bytes()).hexdigest() != PINNED_BINARIES[rel]:
                findings.add((rel, 0, "pinned_binary_changed"))
            continue
        if path.suffix not in EXTENSIONS or any(p.startswith(".env") for p in relative.parts):
            findings.add((rel, 0, "forbidden_file"))
        for pattern in name_patterns:
            if pattern.search(normalized(rel)):
                findings.add((rel, 0, "private_name"))
        raw = path.read_bytes()
        size += len(raw)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            findings.add((rel, 0, "binary"))
            continue
        try:
            for view, first_line, decoded in views(text, path.suffix == ".json"):
                for rule, expression in PATTERNS.items():
                    for match in re.finditer(expression, view):
                        findings.add(
                            (
                                rel,
                                first_line + (0 if decoded else view.count("\n", 0, match.start())),
                                rule,
                            )
                        )
                folded = "".join(
                    c
                    for c in unicodedata.normalize("NFKD", view.casefold())
                    if not unicodedata.combining(c)
                )
                folded = folded.replace("kuladeep mantri", "author attribution")
                for pattern in name_patterns:
                    for match in pattern.finditer(folded):
                        line = (
                            first_line
                            if decoded
                            else first_line + folded.count("\n", 0, match.start())
                        )
                        findings.add((rel, line, "private_name"))
                if "\u2014" in view:
                    findings.add((rel, first_line, "typography"))
        except json.JSONDecodeError:
            findings.add((rel, 0, "invalid_json"))
    return dict(
        status="failed" if findings else "clean",
        files_scanned=len(files),
        bytes_scanned=size,
        private_names_checked=len(name_patterns),
        findings=[dict(path=p, line=line, rule=rule) for p, line, rule in sorted(findings)],
    )


def main() -> None:
    """Run the scanner against a checkout or an explicit distribution root."""
    global BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", type=pathlib.Path)
    parser.add_argument("--root", type=pathlib.Path, default=BASE)
    args = parser.parse_args()
    BASE = args.root.resolve()
    if args.names and args.names.resolve().is_relative_to(BASE):
        raise ValueError("The private name list must stay outside the distribution")
    names = args.names.read_text().splitlines() if args.names else []
    result = scan(names)
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["findings"]))


if __name__ == "__main__":
    main()
