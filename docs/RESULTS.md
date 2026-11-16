# Results

Author: Kuladeep Mantri.

These counts are recomputed by the package; the paper is the authority on interpretation.

## Headline cohorts

On one deployment of SEAL's released code, the published strict M > 12 rule accepts 8 of 40 and 7 of 37 outputs that one score-blind rater labeled meaning-changing, while retaining 139 of 200 clean baseline images. These results use mirror weights; equivalence to the authors' assets is unverified.

| Headline cohort | SEAL strict M > 12 acceptance |
|---|---:|
| Meaning-changing outputs, first batch | 8/40 |
| Meaning-changing outputs, fresh batch | 7/37 |
| Clean baseline images | 139/200 |

## Fixed cohorts

Counts are verifier acceptance, unless the row explicitly identifies a human-qualified endpoint. P20 requires at least 20 readable patches and at most 6% decoded mismatch. The conjunction also requires the local full rule: M > 3, C >= 7 and N >= 388.

| Fixed cohort | P20 | Conjunction | SEAL M > 12 |
|---|---:|---:|---:|
| White-box masked repaint | 30/30 | 28/30 | 19/30 |
| White-box iterative repaint | 29/30 | 25/30 | 22/30 |
| Local SEAL clean reproduction | n/a | n/a | 13/20 |
| Local SEAL independent-noise controls | n/a | n/a | 0/20 |

Numerical acceptance and pixel changes do not establish a successful change in meaning. These bounded white-box strategies do not establish security against stronger attacks.

## External-reference comparison

| External-reference comparison | Embedded P20 | External pre-payload bits |
|---|---:|---:|
| Honest JPEG75 | 88/100 | 100/100 |
| Selected CSI outputs | 0/100 | 0/100 |
| Fixed local repaints | 4/30 | 3/30 |
| Same-caption regeneration, first cohort | 0/40 | 0/40 |
| Same-caption regeneration, later cohort | 0/100 | 0/100 |

The external baseline uses all 714 reference bits with mismatch <= 0.06. P20 uses confidently decoded bits with a readability floor. The 64-bit dHash cutoff is one differing bit, calibrated on the original 40 calibration pairs. The RGB comparator uses a separate 32-pixel enrollment policy and threshold 0.02416506328451865. The recount recomputes decisions from saved mismatch, distance and RGB scores, then compares cohort totals to the recorded aggregates. It does not recalculate the image descriptors.

## Honest distortions

The distortion records cover seven transforms on the same 50 images, 350 rows total. P20 accepts 35/50 at JPEG50, 44/50 at JPEG75 and 0/50 after centered cropping. Run the recount for every rule and cohort.

## Local SEAL precision diagnostic

The final SEAL summary and per-image precision ablations are included. The recount checks the final summary against the saved scalar counts: fresh FP16 and FP32 both accept 13/20, with zero paired acceptance gains or losses. Exact intervals and ROC-AUC diagnostics are recomputed; checkpoint identity and equivalence to the published endpoint remain unresolved. The local strict clean count is 13/20; the inclusive boundary gives 14/20. The negative count is 0/20 under both rules. These historical images do not form an independent confirmation of the published deployment.

The 20-image SEAL diagnostic is retrospective; the published 0.980 endpoint is not a verified M > 12 true-positive rate and is not an equivalent comparison.

## Reading these numbers

A detector acceptance is not proof of authenticity, ownership or unchanged meaning. The limits on mirror weights, white-box attacks and the local SEAL diagnostic accompany their results above.

Selected CSI rows form subsets of all-candidate rows. The any-query Exp2 count uses 40 assigned victims; its 119 rendered rows exclude one failed query slot. These denominators must not be pooled or substituted. The distortion cohort has the same 50 victim IDs under seven transforms. Published strict M > 12 and inclusive M >= 12 are reported separately.

[Repository README](../README.md) · [Reproduce](REPRODUCE.md) · [Data](DATA.md) · [Architecture](ARCHITECTURE.md)
