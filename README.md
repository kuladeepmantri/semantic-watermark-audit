# Semantic watermark audit

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24268671.svg)](https://doi.org/10.5281/zenodo.24268671)

**Paper:** [What Does a Semantic Watermark Verify? An Audit of SEAL and a Tested Thumbnail Repair Candidate (PDF)](paper/semantic-watermark-audit.pdf). Archived on Zenodo: [10.5281/zenodo.24268671](https://doi.org/10.5281/zenodo.24268671). arXiv link coming soon.

This repository contains evaluation code and saved numerical records for *What Does a Semantic Watermark Verify? An Audit of SEAL and a Tested Thumbnail Repair Candidate* by Kuladeep Mantri. It checks every exported numeric or identifier macro used by the captured manuscript input graph, currently 534, including the white-box, SEAL reproduction, external-reference and distortion results. The checks run on a CPU with Python's standard library. They verify arithmetic, record integrity and recorded decisions; they do not regenerate images or rerun model inference.

## Selected results

SEAL's strict M > 12 rule accepts outputs that one score-blind rater labeled meaning-changing, while retaining the clean baseline images shown below. These results use mirror weights; equivalence to the authors' assets is unverified.

| Headline cohort | SEAL strict M > 12 acceptance |
|---|---:|
| Meaning-changing outputs, first batch | 8/40 |
| Meaning-changing outputs, fresh batch | 7/37 |
| Clean baseline images | 139/200 |

Counts are verifier acceptance, unless the row explicitly identifies a human-qualified endpoint. P20 requires at least 20 readable patches and at most 6% decoded mismatch. The conjunction also requires the local full rule: M > 3, C >= 7 and N >= 388.

| Fixed cohort | P20 | Conjunction | SEAL M > 12 |
|---|---:|---:|---:|
| White-box masked repaint | 30/30 | 28/30 | 19/30 |
| White-box iterative repaint | 29/30 | 25/30 | 22/30 |
| Local SEAL clean reproduction | n/a | n/a | 13/20 |
| Local SEAL independent-noise controls | n/a | n/a | 0/20 |

| External-reference comparison | Embedded P20 | External pre-payload bits |
|---|---:|---:|
| Honest JPEG75 | 88/100 | 100/100 |
| Selected CSI outputs | 0/100 | 0/100 |
| Fixed local repaints | 4/30 | 3/30 |
| Same-caption regeneration, first cohort | 0/40 | 0/40 |
| Same-caption regeneration, later cohort | 0/100 | 0/100 |

The distortion records cover seven transforms on the same 50 images, 350 rows total. P20 accepts 35/50 at JPEG50, 44/50 at JPEG75 and 0/50 after centered cropping. Run the recount for every rule and cohort. Numerical acceptance and pixel changes do not establish a successful change in meaning. These bounded white-box strategies do not establish security against stronger attacks. The 20-image SEAL diagnostic is retrospective; the published 0.980 endpoint is not a verified M > 12 true-positive rate and is not an equivalent comparison.

## Quickstart

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

The command then prints each added cohort's numerators and denominators. A failed integrity check, missing component or numerical mismatch returns a nonzero exit status. For machine-readable output and regenerated TeX, run `python -m swaudit.recompute_all --output ../audit-results`. Run only the follow-up cohort recount with `python -m swaudit.round5`. All 114 round-six definitions are regenerated and compared with their paper targets. Both the saved FP16 and fresh FP32 inversion diagnostics accept 13/20 clean images; the final summary is checked against the per-image ablation counts.

## Contents and paper mapping

`src/swaudit/` holds the package, `scripts/` contains convenience entry points, `data/` contains immutable records, and `tests/` checks thresholds, denominators, corruption handling and integration. [The record guide](docs/records.md) maps files and modules to paper table labels and distinguishes raw scalar recounts from audited aggregate replays. The inventory records macro occurrences and source hashes for the manuscript and its explicit inputs. The count comes from that inventory, not a fixed total. With manuscript sources available, run `python -m swaudit.recompute_all --manuscript /path/to/main.tex` to check the live input graph and current definition values. A new, uncomputed numeric macro fails coverage. Literal prose and bibliography entries are outside this exported-macro check.

No images, model weights, latent tensors, prompts, captions, raw volunteer sheets or volunteer identities are included. Volunteer agreement uses pooled sufficient statistics and aggregate bootstrap draws, with no per-volunteer rows. De-identified primary outcome codes used to join experimental cases to numerical scores are included separately; they are not volunteer response sheets. Source locators refer to withheld artifacts and are provenance labels, not files needed to run this package. Internal names in those locators have been replaced with neutral labels. The local record manifest hashes the distributed bytes.

The coverage report distinguishes 228 independent scalar crosschecks, 137 repair or design/context quantities, 88 follow-up scalar recounts, and 81 aggregate, configuration, publication or identifier replays. These categories describe the computation available in this distribution; a replay is not a new measurement. The report lists four specific selectors that the independent crosscheck cannot resolve, each checked by a headline component. Unexpected failures stop the recount.

## Responsible use

Use this code to inspect evidence, test verification assumptions and compare explicitly defined endpoints. A detector acceptance is not proof of authenticity, ownership or unchanged meaning. Test attacks only on assets you own or have permission to evaluate. See [SECURITY.md](SECURITY.md) for reporting errors or vulnerabilities.

## Citation and license

The arXiv identifier is pending. [CITATION.cff](CITATION.cff) contains citation metadata.

```bibtex
@misc{mantri2026semanticwatermark,
  author = {Kuladeep Mantri},
  title = {What Does a Semantic Watermark Verify? An Audit of SEAL and a Tested Thumbnail Repair Candidate},
  year = {2026},
  note = {Preprint; arXiv identifier pending}
}
```

Code and curated numerical records are distributed under the [MIT license](LICENSE). This distribution does not grant rights to the withheld images, datasets or model weights.
