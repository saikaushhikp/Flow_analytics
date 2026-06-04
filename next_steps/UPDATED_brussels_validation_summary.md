# Brussels Active Validation Summary

Date: 2026-05-27

Scope: active Brussels M-DRAC lane/crosswalk smoke validation and IRSM lane validation. Oulu, SPF production, VLM validation, and supervised IRSM remain deferred.

## M-DRAC Smoke Window

The current reproducible Brussels outputs under `results/mdrac/` were generated with bounded hourly smoke windows to avoid the known full-day lane memory issue.

| Date | Lane Conflicts | Crosswalk Conflicts | Lane Schema | Crosswalk Schema |
| --- | ---: | ---: | --- | --- |
| 2025-06-01 | 0 | 0 | ok | ok |
| 2025-06-02 | 1 | 0 | ok | ok |
| 2025-06-03 | 0 | 0 | ok | ok |
| 2025-06-04 | 0 | 0 | ok | ok |
| 2025-06-05 | 0 | 0 | ok | ok |
| 2025-06-06 | 0 | 0 | ok | ok |
| 2025-06-07 | 0 | 0 | ok | ok |

## Detection Breakdown

| Source | Zone | Count |
| --- | --- | ---: |
| lanes | C-L1 | 1 |

MDRAC severity distribution for detected conflicts:

- Count: 1
- Min: 9.785
- Median: 9.785
- Max: 9.785

Top detected conflicts:

| Date | Source | Zone | IDs | MDRAC | TTC | Link |
| --- | --- | --- | --- | ---: | ---: | --- |
| 2025-06-02 | lanes | C-L1 | 11086610-11086617 | 9.785 | 0.850 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-02T00:47:44Z |

## IRSM

- Lane risk vectors for `2025-06-01`: 16.
- Isolation Forest anomalies for `2025-06-01`: 2.
- Comparison report: `irsm/results/brussels/2025-06-01/mdrac_irsm_comparison.md`.

## Current Decision

The active stabilization target is complete for bounded Brussels validation. Full-day/all-hour processing should be treated as a scaling task because the lane pipeline still exhausts memory on large windows.

Manual false-positive review is not encoded in this repo. The bounded run produced one lane candidate, so that candidate is the current priority for visual review using its replay link before scaling the pipeline.
