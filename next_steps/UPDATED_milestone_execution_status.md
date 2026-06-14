# Updated Milestone Execution Status

Date: 2026-06-12

## Completed In Active Pass

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

## Completed In Post-Stabilization Sweep (June 7, 2026)

- Aligned CLI options by adding `--start-time` support to `regions/brussels/crosswalk_main.py` and passing it to the data loader.
- Hardened pair-zone normalization in `ssm/utils.py` so categorical `zone1`/`zone2` columns no longer crash crosswalk M-DRAC filtering.
- Optimized IRSM anomaly detection in `irsm/models/isolation_forest.py` to keep only the strongest anomaly per unique `pair_id`, deduplicating near-miss predictions.
- Cleaned the report generator in `checks/summarize_active_results.py` to dynamically report actual run statistics.

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

## Bounded Verification Run Outputs (Local Data)

The Brussels data is present at `data/` with hourly parquet folders from `2025-06-01-00` through `2025-06-07-23`.

Real smoke runs completed for `2025-06-01` using `--max-hours 1` (with the stabilized and deduplicated pipeline):

- **Brussels Lanes:**
  - Loaded 950,575 rows.
  - Active lane rows processed: 70,966.
  - Final M-DRAC lane conflicts: 2.
  - Output: `results/mdrac/brussels/lanes/2025-06-01/mdrac_2025-06-01.csv`.
- **Brussels Crosswalks:**
  - Loaded 950,575 rows.
  - Active crosswalk-zone rows processed: 6,243.
  - Final ped-vehicle M-DRAC crosswalk conflicts: 36.
  - Output: `results/mdrac/brussels/crosswalks/2025-06-01/mdrac_2025-06-01.csv`.
- **IRSM Lane Vectors:**
  - Risk vectors saved: 3,589.
  - Output: `irsm/data/brussels/2025-06-01/lanes.csv`.
- **IRSM Isolation Forest:**
  - Input vectors: 3,589.
  - Deduplicated anomalies detected: 34.
  - Output: `irsm/results/brussels/2025-06-01/lanes_detections.csv`.
- **M-DRAC vs IRSM Comparison:**
  - Comparison report: `irsm/results/brussels/2025-06-01/mdrac_irsm_comparison.md`.
- **Selected Anomaly Plots:**
  - Generated plots saved under `irsm/results/brussels/2025-06-01/plots/`.

*Note: The Brussels scripts now save schema-valid CSVs even when a run finds zero conflicts.*

## Bounded Sweep Execution Status

We successfully ran `checks/run_brussels_smoke_window.py` and `checks/summarize_active_results.py` to sweep Brussels lane and crosswalk smoke windows for every local day from `2025-06-01` through `2025-06-07` with `--max-hours 1`. 

All 14 bounded runs completed successfully:

| Date | Lane Conflicts | Crosswalk Conflicts |
| --- | ---: | ---: |
| 2025-06-01 | 2 | 36 |
| 2025-06-02 | 5 | 81 |
| 2025-06-03 | 5 | 100 |
| 2025-06-04 | 11 | 74 |
| 2025-06-05 | 5 | 93 |
| 2025-06-06 | 5 | 65 |
| 2025-06-07 | 2 | 46 |

- Current reproducible outputs live under `results/mdrac/brussels/`.
- Per-run execution logs live under `results/mdrac/brussels/smoke_logs/`.
- Generated summary report: `next_steps/UPDATED_brussels_validation_summary.md`.

## Remaining / Deferred

- **Scaling & Performance:** Full-day/all-hour Brussels processing remains a scaling task because the lane pipeline exhausts memory on large windows. The current stabilized workflow uses bounded hourly windows. Chunked run orchestration is planned as a future performance iteration.
- **Experimental & Deferred Areas:** Oulu region support, SPF production use, VLM validation, and supervised IRSM remain deferred per the updated implementation plan.

