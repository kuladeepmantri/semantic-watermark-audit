# Reproduce the saved-record checks

Author: Kuladeep Mantri. Artifact version: 1.0.1.

## Summary

The checks run on a CPU with Python's standard library. They verify arithmetic, record integrity and recorded decisions; they do not regenerate images or rerun model inference.

The current manuscript input graph uses 534 numeric or identifier macros. The package regenerates all of them and checks 3,390 exported definitions, including the 114 later definitions in `round6.py`. Coverage follows the extracted inventory. Expected values only supply comparison targets and display bindings. The calculation modules read saved scores, protocol settings or audited aggregate operands. This is not a fresh execution of the experiments.

## Requirements

Python 3.10 or later is required. The runtime uses the standard library only; the development extras are pytest 8.4.2 and ruff 0.14.5. The recount needs only a CPU and no OS-specific runtime features. The tracked artifact is under 20 MB; allow additional space for Python and the development environment. Installation may download dependencies; the checks need no network after installation.

## Install and run

From a local checkout:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m swaudit.recompute_all
python -m pytest -q
ruff check .
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell.

## Basic check

Run `python -m swaudit.recompute_all`. Successful recomputation starts with:

```text
PASS: 534/534 manuscript macros; 0 mismatches; 0 uncovered
Exports checked: 3390
```

The command then prints each added cohort's numerators and denominators. A failed integrity check, missing component or numerical mismatch returns a nonzero exit status. Successful checks return zero.

## Claims to commands

| Paper result | Command | Where to find it |
|---|---|---|
| Master acceptance (`tab:master`) and operating-point frontier (`tab:operating`) | `python -m swaudit.recompute_all --output ../audit-results` | `numbers-used.tex`: `\SealAloneInit`, `\SealAloneFresh`, `\SealAloneHonest`; `DETAILS.json`: `independent_crosscheck.master`, `independent_crosscheck.frontier`, `parts.part1`, `parts.part2` |
| Volunteer agreement, exact intervals, prediction, configuration and identifiers | `python -m swaudit.recompute_all --output ../audit-results` | `DETAILS.json`: `parts.part3`, `parts.part4`; used macro values in `numbers-used.tex` |
| Repair (`tab:repair`, `tab:repair-two`) | `python -m swaudit.recompute_all --output ../audit-results` | `numbers-used.tex`: macros beginning `\RepOneB` and `\RepTwo` |
| White-box repaint (`tab:repair-whitebox`) | `python -m swaudit.round5` | JSON: `whitebox`; integrated output also includes `\RWhiteMaskedThumb` in `numbers-used.tex` |
| Local SEAL diagnostic and precision | `python -m swaudit.round5` | JSON: `reproduction`, `precision` |
| External reference (`tab:repair-external`) | `python -m swaudit.round5` | JSON: `external` |
| Honest distortions (`tab:repair-distortions`) | `python -m swaudit.round5` | JSON: `distortions` |

To check the first headline count, run with `--output` and look for `\SealAloneInit` in `numbers-used.tex`:

```sh
python -m swaudit.recompute_all --output ../audit-results
grep -F '\SealAloneInit}' ../audit-results/numbers-used.tex
```

The generated line is:

```text
\newcommand{\SealAloneInit}{8/40}
```

The follow-up command prints JSON. The integrated recount prints cohort summaries; these lines come from an actual `python -m swaudit.recompute_all` run:

```text
whitebox/masked: P20=30/30, conjunction=28/30, local_full=28/30, count_strict=19/30, count_inclusive=19/30
reproduction/clean: strict=13/20, inclusive=14/20
external/exp1b_jpeg75: dhash=100/100, embedded_P20=88/100, external_B=100/100, external_S=100/100, rgb=100/100
distortions/jpeg75: dhash=50/50, embedded_P20=44/50, external_B=50/50, external_S=50/50, local_full=25/50, local_mc=40/50, published_corrected_full=16/50, published_corrected_mc=26/50, published_count=26/50, published_inclusive=30/50, rgb=50/50
```

Recomputation takes seconds on a laptop CPU. The follow-up recount and lint check take less than a second; the test suite and privacy scan take longer. Timings depend on the machine and its load.

## Machine-readable output

For machine-readable output and regenerated TeX, run `python -m swaudit.recompute_all --output ../audit-results`.

The output directory contains `RESULT.json`, `DETAILS.json`, `numbers-used.tex` and `numbers-all.tex`. `numbers-used.tex` holds every used macro by name. `DETAILS.json` contains `independent_crosscheck` and `parts`; `RESULT.json` contains `coverage_by_method`, `crosscheck_exceptions` and the follow-up results under `round5`.

Run only the follow-up cohort recount with `python -m swaudit.round5`. The later definitions in `round6.py` are regenerated and compared with their paper targets by the integrated recount. See [the local SEAL precision diagnostic](RESULTS.md#local-seal-precision-diagnostic) for its counts and limitations.

## Checking against manuscript sources

The inventory records macro occurrences and source hashes for the manuscript and its explicit inputs. The count comes from that inventory, not a fixed total. With manuscript sources available, run `python -m swaudit.recompute_all --manuscript /path/to/main.tex` to check the live input graph and current definition values. A new, uncomputed numeric macro fails coverage. Literal prose and bibliography entries are outside this exported-macro check.

## Full validation

```sh
python -m pytest -q
ruff check .
python -m swaudit.scan
```

CI runs the same installation and four validation commands on Python 3.10, 3.11 and 3.12: install the development extras, lint, run the tests, recompute and scan. A successful test run reports 80 passed; ruff reports `All checks passed!`; the scanner reports `"status": "clean"` and an empty findings list.

## What this does not reproduce

No images, model weights, latent tensors, prompts, captions, raw volunteer sheets or volunteer identities are included. This is not a fresh execution of the experiments.

Exact intervals and ROC-AUC diagnostics are recomputed; checkpoint identity and equivalence to the published endpoint remain unresolved. See [the local SEAL precision diagnostic](RESULTS.md#local-seal-precision-diagnostic) for the results and their limits.

[Repository README](../README.md) · [Results](RESULTS.md) · [Data](DATA.md) · [Architecture](ARCHITECTURE.md)
