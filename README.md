# What Does a Semantic Watermark Verify?

An Audit of SEAL and a Tested Thumbnail Repair Candidate.

Kuladeep Mantri.

[Paper (PDF)](paper/semantic-watermark-audit.pdf) · [Zenodo archive](https://doi.org/10.5281/zenodo.24268671) · [Reproduce](docs/REPRODUCE.md) · [Results](docs/RESULTS.md) · [Data](docs/DATA.md) · [Cite](#citation). arXiv identifier pending.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24268671.svg)](https://doi.org/10.5281/zenodo.24268671)
[![CI](https://github.com/kuladeepmantri/semantic-watermark-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/kuladeepmantri/semantic-watermark-audit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)

We ask whether SEAL's accept also supports the claim that an image's meaning is unchanged and, where it does not, whether one simple repair does better. This repository is the companion artifact: evaluation code plus saved numerical records. The checks run on a CPU with Python's standard library. They verify arithmetic, record integrity and recorded decisions; they do not regenerate images or rerun model inference.

## Key results

On one deployment of SEAL's released code, the published strict M > 12 rule accepts 8 of 40 and 7 of 37 outputs that one score-blind rater labeled meaning-changing, while retaining 139 of 200 clean baseline images. These results use mirror weights; equivalence to the authors' assets is unverified.

| Headline cohort | SEAL strict M > 12 acceptance |
|---|---:|
| Meaning-changing outputs, first batch | 8/40 |
| Meaning-changing outputs, fresh batch | 7/37 |
| Clean baseline images | 139/200 |

The masked-thumbnail repair candidate rejects whole-image regenerations, but an attacker repainting pixels excluded from its descriptor passes the thumbnail check on 30/30 images and its conjunction with the local full rule on 28/30. These are measured pixel edits without semantic labels. The repair is a negative result.

All result tables, with denominators and caveats: [docs/RESULTS.md](docs/RESULTS.md).

## Reproduce

Python 3.10 or later is required. From a local checkout:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m swaudit.recompute_all
python -m pytest -q
ruff check .
```

Successful recomputation starts with:

```text
PASS: 534/534 manuscript macros; 0 mismatches; 0 uncovered
Exports checked: 3390
```

The recount takes seconds; the test suite takes well under a minute on a laptop CPU. After installation, checks need no GPU, network or downloads.

A failed integrity check, missing component or numerical mismatch returns a nonzero exit status. See [docs/REPRODUCE.md](docs/REPRODUCE.md) for the claims-to-commands map and manuscript mode.

## Scope

- Included: recount code, saved scalar records, de-identified outcome codes, manifest and paper PDF.
- Not included: images, model weights, latent tensors, prompts, captions, raw volunteer sheets or volunteer identities.
- Not done: image regeneration, model inference or a fresh experiment.
- Coverage: every exported numeric or identifier macro in the manuscript input graph (currently 534); literal prose and bibliography entries are outside the check.

## Repository map

| Path | Purpose |
|---|---|
| `paper/` | The paper PDF. |
| `src/swaudit/` | The recount package. Standard library only. |
| `data/` | Frozen numerical records, with a SHA-256 manifest and provenance digests. |
| `tests/` | 80 tests: thresholds, denominators, corruption handling, integration. |
| `scripts/` | Two thin wrappers around the package entry points. |
| `docs/` | How to reproduce, what the results are, what each record holds, how the code is laid out. |
| `.github/` | CI (Python 3.10 to 3.12) and the issue template. |

## Documentation

| Doc | Answers |
|---|---|
| [docs/REPRODUCE.md](docs/REPRODUCE.md) | How do I check a specific claim, and what should I see? |
| [docs/RESULTS.md](docs/RESULTS.md) | What are the numbers and what do they not show? |
| [docs/DATA.md](docs/DATA.md) | What do the records hold, and what was withheld? |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How is the code laid out and how is each macro verified? |

## Responsible use

Use this code to inspect evidence, test verification assumptions and compare explicitly defined endpoints. A detector acceptance is not proof of authenticity, ownership or unchanged meaning. Test attacks only on assets you own or have permission to evaluate. See [SECURITY.md](SECURITY.md) for reporting errors or vulnerabilities.

## Citation

[CITATION.cff](CITATION.cff) contains citation metadata for the paper and artifact.

```bibtex
@misc{mantri2026semanticwatermark,
  author = {Kuladeep Mantri},
  title = {What Does a Semantic Watermark Verify? An Audit of SEAL and a Tested Thumbnail Repair Candidate},
  year = {2026},
  note = {Preprint}
}

@software{mantri2026semanticwatermarkartifact,
  author = {Kuladeep Mantri},
  title = {Semantic watermark audit: code and records},
  year = {2026},
  version = {1.0.0},
  doi = {10.5281/zenodo.24268671}
}
```

## License

Code and curated numerical records are distributed under the [MIT license](LICENSE). This distribution does not grant rights to the withheld images, datasets or model weights.
