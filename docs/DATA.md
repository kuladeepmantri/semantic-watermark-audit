# Data and records

Author: Kuladeep Mantri.

## Record layout

| Path | Contents |
|---|---|
| `data/data/` | Saved scores, protocol settings, macro inventory and comparison values. |
| `data/headline/part1/` through `part4/` | Headline recount records and comparison targets. |
| `data/round5/` | White-box, SEAL diagnostic, external-reference and distortion records. |
| `data/expected/` | Repair display targets. |
| `data/MANIFEST.json`, `data/PROVENANCE.json` | Distributed-byte hashes and original source digests. |

`data/data/` preserves the original record namespace within the bundled data package.

## Follow-up record files

The counts below come from the stored arrays and macro dictionary. Files with only configuration or aggregate objects are identified separately. These counts describe stored entries, not independent samples.

| File in `data/round5/` | Stored entries | Contents |
|---|---|---|
| `design.json` | Configuration or aggregate object; no image rows | Frozen thumbnail, repaint and distortion settings; source bindings. |
| `distortion-clean.json` | `rows`: 50 | Clean-image comparator and detector scores for the distortion baseline. |
| `distortions.json` | `rows`: 350 | Comparator and detector scores for each image-transform pair. |
| `expected-macros.json` | 114 macro targets | Comparison targets for the later manuscript definitions. |
| `external.json` | `rows`: 989 | External-reference and embedded-check scores, with cohort aggregates. |
| `provenance.json` | `sources`: 4; no image rows | Original and distributed digests for the source records. |
| `seal-repro-final.json` | `rows`: 40; `ablation`: 20 | Final clean/control scores and per-image precision ablations. |
| `seal-repro-summary.json` | Configuration or aggregate object; no image rows | Aggregate rates, precision comparisons, intervals, AUCs and limitations. |
| `seal-repro.json` | `rows`: 40 | Earlier clean/control scores for the local SEAL diagnostic. |
| `whitebox-edits.json` | `rows`: 60 | Measured pixel changes and change-gate outcomes for local repaints. |
| `whitebox.json` | `rows`: 90 | Detector scores and decisions for local repaints and source controls. |

## Paper results, records and modules

| Paper table or result | Distributed records | Recount module |
|---|---|---|
| Master acceptance and honest retention, `tab:master` | `data/data/frontier-rows.json`, `data/headline/part1/` | `analysis/headline.py`, `headline/part1/recompute.py` |
| Operating-point frontier, `tab:operating` | `data/headline/part2/` | `headline/part2/recompute.py` |
| Volunteer agreement and exact intervals | `data/headline/part3/`, `data/data/agreement-aggregates.json` | `headline/part3/recompute.py` |
| Prediction, configuration and identifier macros | `data/headline/part4/` | `headline/part4/recompute.py` |
| Repair, `tab:repair`, `tab:repair-two` | `data/data/exp1b.json`, `exp2.json`, allocation, query and calibration records | `recompute.py` |
| White-box repaint, `tab:repair-whitebox` | `data/round5/whitebox.json`, 90 rows including source controls | `round5.py` |
| Local SEAL diagnostic and precision | `data/round5/seal-repro.json`, `seal-repro-final.json`, `seal-repro-summary.json` | `round5.py`, `round6.py` |
| External reference, `tab:repair-external` | `data/round5/external.json`, 989 distinct image rows | `round5.py` |
| Honest distortions, `tab:repair-distortions` | `data/round5/distortions.json`, 350 image-transform rows | `round5.py` |

The module paths in this table are relative to `src/swaudit/`. `data/data/used-macros.json` lists the captured manuscript occurrences; `expected-all.json` holds comparison values. `data/expected/repair-numbers.tex` holds the repair display targets.

## Denominators that must not be pooled

Selected CSI rows form subsets of all-candidate rows. The any-query Exp2 count uses 40 assigned victims; its 119 rendered rows exclude one failed query slot. These denominators must not be pooled or substituted. The distortion cohort has the same 50 victim IDs under seven transforms. Published strict M > 12 and inclusive M >= 12 are reported separately.

## What was withheld and why

No images, model weights, latent tensors, prompts, captions, raw volunteer sheets or volunteer identities are included. Volunteer agreement uses pooled sufficient statistics and aggregate bootstrap draws, with no per-volunteer rows. De-identified primary outcome codes used to join experimental cases to numerical scores are included separately; they are not volunteer response sheets. Source locators refer to withheld artifacts and are provenance labels, not files needed to run this package. Internal names in those locators have been replaced with neutral labels. The local record manifest hashes the distributed bytes.

Volunteer agreement records contain pooled class totals, coincidence mass and aggregate bootstrap statistics. They permit a fixed-panel arithmetic replay without exposing individual volunteers or their answer sequences. They do not allow a new independent resampling of the original responses. Primary experimental outcome codes are separate de-identified records; numerical detection does not establish those labels.

## Integrity

`data/MANIFEST.json` covers every distributed record except its own bytes and the package initializer. It detects missing, changed and unexpected record files. `data/PROVENANCE.json` retains original source digests with neutralized internal locators. Those digests describe original evidence, not the reformatted public code. No source checkout is required at runtime.

Do not add files under `data/`; the manifest check rejects them.

[Repository README](../README.md) · [Reproduce](REPRODUCE.md) · [Results](RESULTS.md) · [Architecture](ARCHITECTURE.md)
