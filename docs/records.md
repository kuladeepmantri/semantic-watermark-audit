# Record guide

Author: Kuladeep Mantri.

The current manuscript input graph uses 534 numeric or identifier macros. The package regenerates all of them and checks 3,390 exported definitions, including all 114 round-six additions. Coverage follows the extracted inventory. Expected values only supply comparison targets and display bindings. The calculation modules read saved scores, protocol settings or audited aggregate operands. This is not a fresh execution of the experiments.

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

The module paths in this table are relative to `src/swaudit/`. `data/data/` preserves the original record namespace within the bundled data package. `data/data/used-macros.json` lists the captured manuscript occurrences; `expected-all.json` holds comparison values. `data/expected/repair-numbers.tex` holds the repair display targets. The legacy selector module replays audited operands rather than independently measuring their original sources. The independent crosscheck recalculates master counts and several headline quantities from scalar records; some naturalness, historical model summaries and bootstrap endpoints remain aggregate replays.

The external baseline uses all 714 reference bits with mismatch <= 0.06. P20 uses confidently decoded bits with a readability floor. The 64-bit dHash cutoff is one differing bit, calibrated on the original 40 calibration pairs. The RGB comparator uses a separate 32-pixel enrollment policy and threshold 0.02416506328451865. The recount recomputes decisions from saved mismatch, distance and RGB scores, then compares cohort totals to the recorded aggregates. It does not recalculate the image descriptors.

Selected CSI rows form subsets of all-candidate rows. The any-query Exp2 count uses 40 assigned victims; its 119 rendered rows exclude one failed query slot. These denominators must not be pooled or substituted. The distortion cohort has the same 50 victim IDs under seven transforms. Published strict M > 12 and inclusive M >= 12 are reported separately.

Volunteer agreement records contain pooled class totals, coincidence mass and aggregate bootstrap statistics. They permit a fixed-panel arithmetic replay without exposing individual volunteers or their answer sequences. They do not allow a new independent resampling of the original responses. Primary experimental outcome codes are separate de-identified records; numerical detection does not establish those labels.

The final SEAL summary and per-image precision ablations are included. The recount checks the final summary against the saved scalar counts: fresh FP16 and FP32 both accept 13/20, with zero paired acceptance gains or losses. Exact intervals and ROC-AUC diagnostics are recomputed; checkpoint identity and equivalence to the published endpoint remain unresolved. The local strict clean count is 13/20; the inclusive boundary gives 14/20. The negative count is 0/20 under both rules. These historical images do not form an independent confirmation of the published deployment.

`data/MANIFEST.json` covers every distributed record except its own bytes and the package initializer. It detects missing, changed and unexpected record files. `data/PROVENANCE.json` retains original source digests with neutralized internal locators. Those digests describe original evidence, not the reformatted public code. No source checkout is required at runtime.

## Validation and numerical policy

`data/data/protocol.json` supplies the detector thresholds. Named rules use those values, and the independent master-context declaration must agree. The public recount does not use a second table of literal cutoffs. Configuration values describing an experiment remain explicitly classified as configuration replays.

All rounded displays use decimal half-up rounding in `analysis/format_numbers.py`, with scaling before rounding. Exact serialized values retain their original representation. For example, 12.5 rounded to zero decimal places is 13. Integrity checks raise errors under both normal Python and `python -O`.

`data/data/crosscheck-policy.json` names the source-and-path-specific exceptions and allowed aggregate-only sources. A changed selector cannot silently become a replay. `RESULT.json` includes the four exceptions and a coverage breakdown. The current used-macro categories are:

| Verification method | Used macros |
|---|---:|
| Independent scalar crosscheck | 228 |
| Repair recount or design/context record | 137 |
| Follow-up scalar recount | 88 |
| Audited numerical selector or configuration replay | 30 |
| Follow-up frozen configuration replay | 25 |
| Volunteer aggregate or screening definition replay | 14 |
| Source-bound identifier or code location | 11 |
| Published comparison endpoint replay | 1 |

The manifest covers only the record directory, so Git metadata, license files and CI configuration cannot change its inventory. It still rejects unexpected files inside the records. `.gitattributes` pins text to LF. The privacy scanner checks decoded JSON strings and accent-folded names with whitespace, dot, underscore or hyphen separators; reports contain file locations and rule names, never matching content.
