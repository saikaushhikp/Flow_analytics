# Brussels Active Validation Summary

Date: 2026-07-07

Scope: active Brussels M-DRAC lane/crosswalk smoke validation and IRSM lane validation. Oulu, SPF production, VLM validation, and supervised IRSM remain deferred.

## M-DRAC Smoke Window

The current reproducible Brussels outputs under `results/mdrac/` were generated with bounded hourly smoke windows to avoid the known full-day lane memory issue.

| Date | Lane Conflicts | Crosswalk Conflicts | 
| --- | ---: | ---: |
| 2025-06-01 | 1 | 4 |
| 2025-06-02 | 7 | 13 |
| 2025-06-03 | 8 | 12 |
| 2025-06-04 | 5 | 14 |
| 2025-06-05 | 12 | 11 |
| 2025-06-06 | 5 | 13 |
| 2025-06-07 | 6 | 9 |

## Detection Breakdown

| Source | Zone | Count |
| --- | --- | ---: |
| crosswalks | 1015 | 8 |
| crosswalks | 1017 | 35 |
| crosswalks | 1018 | 14 |
| crosswalks | 1019 | 16 |
| crosswalks | 1052 | 3 |
| lanes | Intersection | 1 |
| lanes | Road Amandiers | 2 |
| lanes | Road Houba North Ext-Int | 6 |
| lanes | Road Houba South Ext-Int | 10 |
| lanes | Road Houba South Int-Ext [1] | 1 |
| lanes | Road Houba South Int-Ext [2] | 2 |
| lanes | Road Magnolias Ext-Int | 22 |

MDRAC severity distribution for detected conflicts:

- Count: 120
- Min: 3.459
- Median: 6.438
- Max: 23.337

Top detected conflicts:

| Date | Source | Zone | IDs | MDRAC | TTC | Link |
| --- | --- | --- | --- | ---: | ---: | --- |
| 2025-06-05 | lanes | Road Magnolias Ext-Int | 14697579-14697780 | 23.337 | 0.794 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T14:09:50Z |
| 2025-06-03 | lanes | Road Magnolias Ext-Int | 12269933-12270233 | 23.052 | 0.345 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-03T07:45:46Z |
| 2025-06-05 | lanes | Road Magnolias Ext-Int | 14660702-14662073 | 22.646 | 0.792 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T13:42:42Z |
| 2025-06-05 | lanes | Road Magnolias Ext-Int | 14573531-14573936 | 22.151 | 0.898 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T12:43:07Z |
| 2025-06-02 | lanes | Road Houba South Ext-Int | 11443714-11443999 | 21.272 | 0.478 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-02T09:52:07Z |
| 2025-06-07 | lanes | Road Houba South Ext-Int | 16528379-16529412 | 21.173 | 0.485 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-07T10:38:01Z |
| 2025-06-05 | lanes | Road Houba South Ext-Int | 14349273-14349410 | 20.838 | 0.496 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-05T08:41:37Z |
| 2025-06-06 | lanes | Road Houba South Ext-Int | 16012485-16015699 | 20.613 | 0.718 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-06T17:28:43Z |
| 2025-06-03 | lanes | Road Magnolias Ext-Int | 12856400-12856458 | 20.086 | 0.946 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-03T16:10:01Z |
| 2025-06-03 | lanes | Road Houba South Ext-Int | 12522217-12522338 | 19.855 | 0.506 | https://di-india-collab.flow-analytics.io/tools/replay/2025-06-03T11:52:42Z |

## IRSM

- Lane risk vectors for `2025-06-01`: 4205.
- Isolation Forest anomalies for `2025-06-01`: 5.
- Comparison report: `irsm/results/brussels/2025-06-01/mdrac_irsm_comparison.md`.

## Current Decision

The active stabilization target is complete for bounded Brussels validation. Full-day/all-hour processing should be treated as a scaling task because the lane pipeline still exhausts memory on large windows.

Manual false-positive review is not encoded in this repo. The current bounded candidates should be reviewed through their replay links before broadening the run window or retuning thresholds.
