# Brussels Active Validation Summary

Last updated on: 2026-07-17

Source summary date: 2026-07-13

Scope: active Brussels M-DRAC lane/crosswalk smoke validation and IRSM lane validation. Oulu, SPF production, VLM validation, and supervised IRSM remain deferred.

## M-DRAC Smoke Window

The current reproducible Brussels outputs under `results/mdrac/` were generated with bounded hourly smoke windows to avoid the known full-day lane memory issue.

| Date | Lane Conflicts | Crosswalk Conflicts | 
| --- | ---: | ---: |
| 2025-06-01 | 1 | 4 |
| 2025-06-02 | 6 | 13 |
| 2025-06-03 | 8 | 12 |
| 2025-06-04 | 4 | 14 |
| 2025-06-05 | 11 | 11 |
| 2025-06-06 | 5 | 13 |
| 2025-06-07 | 5 | 9 |

## Detection Breakdown

| Source | Zone | Count |
| --- | --- | ---: |
| crosswalks | 1015 | 8 |
| crosswalks | 1017 | 35 |
| crosswalks | 1018 | 14 |
| crosswalks | 1019 | 16 |
| crosswalks | 1052 | 3 |
| lanes | Intersection | 1 |
| lanes | Road Amandiers | 1 |
| lanes | Road Houba North Ext-Int | 6 |
| lanes | Road Houba South Ext-Int | 8 |
| lanes | Road Houba South Int-Ext [1] | 1 |
| lanes | Road Houba South Int-Ext [2] | 2 |
| lanes | Road Magnolias Ext-Int | 21 |

MDRAC severity distribution for detected conflicts:

- Count: 116
- Min: 3.459
- Median: 6.438
- Max: 23.337

Top detected conflicts:

| Date | Source | Zone | IDs | MDRAC | TTC | Link |
| --- | --- | --- | --- | ---: | ---: | --- |
| 2025-06-05 | lanes | Road Magnolias Ext-Int | 14697579-14697780 | 23.337 | 0.794 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T14:09:50Z |
| 2025-06-03 | lanes | Road Magnolias Ext-Int | 12269933-12270233 | 23.052 | 0.345 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-03T07:45:46Z |
| 2025-06-05 | lanes | Road Magnolias Ext-Int | 14660702-14662073 | 22.646 | 0.792 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T13:42:42Z |
| 2025-06-05 | lanes | Road Magnolias Ext-Int | 14573531-14573936 | 22.184 | 0.808 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T12:43:08Z |
| 2025-06-03 | lanes | Road Houba South Ext-Int | 12522217-12522338 | 21.558 | 0.429 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-03T11:52:42Z |
| 2025-06-05 | lanes | Road Houba South Ext-Int | 14349273-14349410 | 20.838 | 0.496 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T08:41:37Z |
| 2025-06-06 | lanes | Road Houba South Ext-Int | 16012485-16015699 | 20.613 | 0.718 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-06T17:28:43Z |
| 2025-06-03 | lanes | Road Magnolias Ext-Int | 12856400-12856458 | 20.169 | 0.821 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-03T16:10:01Z |
| 2025-06-02 | lanes | Road Houba South Ext-Int | 11579282-11579498 | 19.505 | 0.530 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-02T12:37:03Z |
| 2025-06-05 | lanes | Road Magnolias Ext-Int | 14696578-14698353 | 17.820 | 0.293 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T14:09:00Z |

## IRSM

- Lane risk vectors for `2025-06-01`: 1386.
- Isolation Forest anomalies for `2025-06-01`: 3.
- Comparison report: `irsm/results/brussels/2025-06-01/mdrac_irsm_comparison.md`.

## Current Decision

The active stabilization target is complete for bounded Brussels validation. Full-day/all-hour processing should be treated as a scaling task because the lane pipeline still exhausts memory on large windows.

Manual false-positive review is not encoded in this repo. The current bounded candidates should be reviewed through their replay links before broadening the run window or retuning thresholds.
