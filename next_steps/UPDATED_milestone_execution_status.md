# Updated Milestone Execution Status

Date: 2026-05-27

## Completed In This Pass

- Restored `utils.load_data()` via `utils/data_loader.py`.
- Added repository path helpers in `utils/paths.py`.
- Fixed `load_detection_results()` so CSV files use `pd.read_csv()`.
- Added detection output schema validation for M-DRAC CSV writes.
- Made Brussels lane and crosswalk entrypoints configurable:
  - `--data-dir`
  - `--output-dir`
  - `--config`
  - `--max-hours`
  - `--sample-limit`
- Removed active Brussels dependency on the old `/home/ubuntu/prem` path.
- Marked SPF as `experimental-disabled` in `config.yaml` and README.
- Added Brussels IRSM lane risk-vector generation in `irsm/data_generation.py`.
- Fixed IRSM package lazy exports.
- Made Isolation Forest and Gaussian anomaly scripts resolve paths from the repository/config.
- Added `irsm/compare_mdrac_irsm.py` to compare M-DRAC detections with IRSM anomalies.
- Made the deprecated VLM batch validator importable without optional VLM dependencies.
- Added lightweight automated checks in `checks/active_pipeline_checks.py`.

## Verified

The following checks pass in `flow_env`:

```bash
conda run -n flow_env python checks/active_pipeline_checks.py
conda run -n flow_env python -c "import utils; import ssm.utils; from ssm.m_drac import ModifiedDRAC; from regions.brussels import zones; from vlm.batch_validator import validate_pairs_batch; print('import checks ok', len(zones.get_lane_zones()))"
conda run -n flow_env python regions/brussels/lane_main.py --help
conda run -n flow_env python regions/brussels/crosswalk_main.py --help
conda run -n flow_env python irsm/data_generation.py --help
conda run -n flow_env python irsm/compare_mdrac_irsm.py --help
```

## Completed After Local Data Was Added

The Brussels data is now present at `data/` with hourly parquet folders from `2025-06-01-00` through `2025-06-07-23`.

Real one-hour smoke runs were completed for `2025-06-01` using `--max-hours 1`:

- Brussels lanes:
  - Loaded 950,575 rows.
  - After preprocessing/static removal: 210,959 rows.
  - Lane rows: 70,966.
  - Base pairs: 1,242.
  - Final M-DRAC pairs: 7.
  - Conflicts above threshold: 0.
  - Output: `results/mdrac/brussels/lanes/2025-06-01/mdrac_2025-06-01.csv`.
- Brussels crosswalks:
  - Loaded 950,575 rows.
  - Crosswalk-zone rows: 6,243.
  - Nearby pairs: 169.
  - Pedestrian-vehicle pairs after M-DRAC filters: 3.
  - Conflicts above threshold: 0.
  - Output: `results/mdrac/brussels/crosswalks/2025-06-01/mdrac_2025-06-01.csv`.
- IRSM lane vectors:
  - Base pairs: 3,659.
  - Same-lane IRSM pairs: 784.
  - Approaching pairs within IRSM thresholds: 248.
  - Risk vectors saved: 16.
  - Output: `irsm/data/brussels/2025-06-01/lanes.csv`.
- IRSM Isolation Forest:
  - Input vectors: 16.
  - Anomalies detected: 2.
  - Output: `irsm/results/brussels/2025-06-01/lanes_detections.csv`.
- M-DRAC vs IRSM comparison:
  - M-DRAC lane pairs: 0.
  - IRSM anomaly pairs: 2.
  - Overlap: 0.
  - Output: `irsm/results/brussels/2025-06-01/mdrac_irsm_comparison.md`.
- Selected anomaly plots:
  - Generated for 2/2 IRSM anomaly pairs.
  - Output directory: `irsm/results/brussels/2025-06-01/plots/`.

The Brussels scripts now save schema-valid CSVs even when a smoke run finds zero conflicts.

- Brussels lane M-DRAC code by running `python regions/brussels/lane_main.py` can confortably run ONLY WHEN --max-hours is set to some value less than 22 hours of data, otherwise it runs into memory issues.

## Completed In Final Stabilization Pass

- Added `checks/run_brussels_smoke_window.py` so the bounded Brussels lane/crosswalk validation can be repeated without manually launching each date.
- Added `checks/summarize_active_results.py` to generate a compact current validation report.
- Ran bounded Brussels lane and crosswalk smoke windows for every local data day from `2025-06-01` through `2025-06-07` with `--max-hours 1`.
- All 14 bounded runs completed successfully:
  - 7 lane runs.
  - 7 crosswalk runs.
- Current reproducible M-DRAC outputs live under `results/mdrac/brussels/`.
- Per-run logs live under `results/mdrac/brussels/smoke_logs/`.
- Generated summary report: `next_steps/UPDATED_brussels_validation_summary.md`.

Bounded smoke-window detection counts:

| Date | Lane Conflicts | Crosswalk Conflicts |
| --- | ---: | ---: |
| 2025-06-01 | 0 | 0 |
| 2025-06-02 | 1 | 0 |
| 2025-06-03 | 0 | 0 |
| 2025-06-04 | 0 | 0 |
| 2025-06-05 | 0 | 0 |
| 2025-06-06 | 0 | 0 |
| 2025-06-07 | 0 | 0 |

## Remaining / Deferred

- Full-day/all-hour Brussels processing remains a scaling task because the lane pipeline exhausts memory on large windows. The current stabilized workflow uses bounded hourly windows.
- Oulu, SPF production use, VLM validation, and supervised IRSM remain deferred per the updated implementation plan.
