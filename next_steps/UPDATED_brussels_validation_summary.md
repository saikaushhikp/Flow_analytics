# Brussels Active Validation Summary

Date: 2026-06-10

Scope: active Brussels M-DRAC lane/crosswalk smoke validation and IRSM lane validation. Oulu, SPF production, VLM validation, and supervised IRSM remain deferred.

## M-DRAC Smoke Window

The current reproducible Brussels outputs under `results/mdrac/` were generated with bounded hourly smoke windows to avoid the known full-day lane memory issue.

| Date | Lane Conflicts | Crosswalk Conflicts | Lane Schema | Crosswalk Schema |
| --- | ---: | ---: | --- | --- |
| 2025-06-01 | 2 | 36 | ok | ok |
| 2025-06-02 | 5 | 81 | ok | ok |
| 2025-06-03 | 5 | 100 | ok | ok |
| 2025-06-04 | 11 | 74 | ok | ok |
| 2025-06-05 | 5 | 93 | ok | ok |
| 2025-06-06 | 5 | 65 | ok | ok |
| 2025-06-07 | 2 | 46 | ok | ok |

## Detection Breakdown

| Source | Zone | Count |
| --- | --- | ---: |
| crosswalks | 1015 | 51 |
| crosswalks | 1016 | 7 |
| crosswalks | 1017 | 89 |
| crosswalks | 1018 | 31 |
| crosswalks | 1019 | 35 |
| crosswalks | 1015 | 51 |
| crosswalks | 1016 | 16 |
| crosswalks | 1017 | 114 |
| crosswalks | 1018 | 55 |
| crosswalks | 1018|1019 | 5 |
| crosswalks | 1019 | 40 |
| crosswalks | 1019|1018 | 1 |
| lanes | B-L2 | 1 |
| lanes | D-L1 | 18 |
| lanes | E-L1 | 11 |
| lanes | E-L2 | 5 |

MDRAC severity distribution for detected conflicts:

- Count: 530
- Min: 3.401
- Median: 5.452
- Max: 22.552

Top detected conflicts:

| Date | Source | Zone | IDs | MDRAC | TTC | Link |
| --- | --- | --- | --- | ---: | ---: | --- |
| 2025-06-04 | lanes | D-L1 | 13425364-13425577 | 22.552 | 0.413 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-04T10:01:45Z |
| 2025-06-04 | lanes | E-L1 | 13169970-13169979 | 22.273 | 0.816 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-04T05:15:51Z |
| 2025-06-01 | lanes | D-L1 | 10652881-10653051 | 22.208 | 0.831 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-01T12:12:15Z |
| 2025-06-05 | lanes | E-L2 | 14150306-14150496 | 22.082 | 0.659 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T05:39:39Z |
| 2025-06-06 | lanes | D-L1 | 15803196-15805017 | 21.822 | 0.346 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-06T13:47:00Z |
| 2025-06-02 | lanes | D-L1 | 11581626-11581878 | 18.727 | 0.998 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-02T12:42:09Z |
| 2025-06-03 | lanes | D-L1 | 12242871-12243469 | 17.817 | 1.116 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-03T07:13:39Z |
| 2025-06-07 | lanes | B-L2 | 16667627-16667664 | 16.854 | 0.938 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-07T12:51:17Z |
| 2025-06-03 | crosswalks | 1018|1019 | 12468066-12468191 | 16.785 | 0.919 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-03T11:02:02Z |
| 2025-06-04 | crosswalks | 1015 | 13931597-13931866 | 16.385 | 0.676 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-04T18:21:41Z |

## IRSM

- Lane risk vectors for `2025-06-01`: 3589.
- Isolation Forest anomalies for `2025-06-01`: 34.
- Comparison report: `irsm/results/brussels/2025-06-01/mdrac_irsm_comparison.md`.

## Current Decision

The active stabilization target is complete for bounded Brussels validation. Full-day/all-hour processing should be treated as a scaling task because the lane pipeline still exhausts memory on large windows.

Manual false-positive review is not encoded in this repo. The current bounded candidates should be reviewed through their replay links before broadening the run window or retuning thresholds.
