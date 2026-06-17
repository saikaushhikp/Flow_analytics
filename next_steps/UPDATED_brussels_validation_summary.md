# Brussels Active Validation Summary

Date: 2026-06-15

Scope: active Brussels M-DRAC lane/crosswalk smoke validation and IRSM lane validation. Oulu, SPF production, VLM validation, and supervised IRSM remain deferred.

## M-DRAC Smoke Window

The current reproducible Brussels outputs under `results/mdrac/` were generated with bounded hourly smoke windows to avoid the known full-day lane memory issue.

| Date | Lane Conflicts | Crosswalk Conflicts | Lane Schema | Crosswalk Schema |
| --- | ---: | ---: | --- | --- |
| 2025-06-01 | 2 | 7 | ok | ok |
| 2025-06-02 | 5 | 39 | ok | ok |
| 2025-06-03 | 5 | 33 | ok | ok |
| 2025-06-04 | 8 | 30 | ok | ok |
| 2025-06-05 | 4 | 36 | ok | ok |
| 2025-06-06 | 4 | 17 | ok | ok |
| 2025-06-07 | 2 | 13 | ok | ok |

## Detection Breakdown

| Source | Zone | Count |
| --- | --- | ---: |
| crosswalks | 1015 | 27 |
| crosswalks | 1016 | 13 |
| crosswalks | 1017 | 50 |
| crosswalks | 1018 | 44 |
| crosswalks | 1019 | 41 |
| lanes | B-L2 | 1 |
| lanes | D-L1 | 16 |
| lanes | E-L1 | 8 |
| lanes | E-L2 | 5 |

MDRAC severity distribution for detected conflicts:

- Count: 205
- Min: 3.401
- Median: 7.005
- Max: 22.273

Top detected conflicts:

| Date | Source | Zone | IDs | MDRAC | TTC | Link |
| --- | --- | --- | --- | ---: | ---: | --- |
| 2025-06-04 | lanes | E-L1 | 13169970-13169979 | 22.273 | 0.816 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-04T05:15:51Z |
| 2025-06-01 | lanes | D-L1 | 10652881-10653051 | 22.208 | 0.831 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-01T12:12:15Z |
| 2025-06-06 | lanes | D-L1 | 15803196-15805017 | 21.659 | 0.881 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-06T13:47:00Z |
| 2025-06-02 | lanes | D-L1 | 11581626-11581878 | 18.727 | 0.998 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-02T12:42:09Z |
| 2025-06-05 | lanes | E-L2 | 14150306-14150496 | 17.555 | 0.659 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T05:39:39Z |
| 2025-06-07 | lanes | B-L2 | 16667627-16667664 | 16.854 | 0.938 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-07T12:51:17Z |
| 2025-06-05 | lanes | E-L2 | 14150154-14150306 | 16.272 | 0.896 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T05:39:24Z |
| 2025-06-02 | lanes | D-L1 | 11196762-11196842 | 16.163 | 0.807 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-02T05:19:51Z |
| 2025-06-05 | crosswalks | 1017 | 14788697-14789479 | 16.025 | 1.097 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T15:19:19Z |
| 2025-06-07 | crosswalks | 1017 | 16351930-16352212 | 15.356 | 1.015 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-07T06:58:15Z |

## IRSM

- Lane risk vectors for `2025-06-01`: 2318.
- Isolation Forest anomalies for `2025-06-01`: 6.
- Comparison report: `irsm/results/brussels/2025-06-01/mdrac_irsm_comparison.md`.

## Current Decision

The active stabilization target is complete for bounded Brussels validation. Full-day/all-hour processing should be treated as a scaling task because the lane pipeline still exhausts memory on large windows.

Manual false-positive review is not encoded in this repo. The current bounded candidates should be reviewed through their replay links before broadening the run window or retuning thresholds.
