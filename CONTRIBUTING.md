# Contributing

Maintainer: Kuladeep Mantri.

This is a frozen research artifact. Records are never edited in place. Report a suspected error through GitHub issues using the reproduction report template. Include the artifact version, command, expected result and observed result. Use synthetic examples; keep private images and personal data out of reports.

Corrections are recorded in [CHANGELOG.md](CHANGELOG.md). A correction that changes a number requires a new versioned release.

Before a pull request, run these checks from the repository root in an activated virtual environment:

```sh
python -m pip install -e '.[dev]'
ruff check .
python -m pytest -q
python -m swaudit.recompute_all
python -m swaudit.scan
```

See [docs/REPRODUCE.md](docs/REPRODUCE.md) for setup and expected output. Documentation changes must preserve the result caveats and the distinction between recounting saved records and running a fresh experiment.
