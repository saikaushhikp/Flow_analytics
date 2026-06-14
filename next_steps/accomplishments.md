# Accomplishments Report

**Date:** June 13, 2026  
**Repo:** Flow_analytics (formerly `prem`)  

> This is an Enhanced Report Documentation Summary from the daily progress content(.txt files) provided by the user.  
> This Summary is Generated from daily progress files (.txt)   
> Everything this summary talks about has been verified.  

---

## 1. Executive Summary
Following the take-over of the codebase, we inherited a half-refactored, non-runnable repository. While the underlying algorithm (M-DRAC) and the experimental structures (Safety Potential Fields, unsupervised IRSM, VLM Validation) were conceptually sound, the repository was broken due to hardcoded machine paths, missing modules, runtime bugs.

Over a series of development runs, we stabilized the codebase, resolved import and configuration blockers, completed end-to-end integration of the local 4.3 GB trajectory dataset, and created a fully reproducible, verified, and bounded hourly smoke-testing pipeline for both M-DRAC and IRSM.

All active milestones related to **Brussels M-DRAC (Lanes & Crosswalks)** and **IRSM Lane Vector Anomaly Detection** are complete and passing. Deprecated or non-priority scopes (Oulu region, SPF production, VLM validation, supervised IRSM) have been safely isolated and deferred to avoid polluting the core active pipelines.

---

## 2. Inherited Repository State & Issues Addressed
Before our effort, the codebase had major blockers:
*   **Hardcoded Absolute Paths:** Scripts and configuration files assumed a `/home/ubuntu/prem` environment, causing immediate crashes on different setups.
*   **Missing Utility Files:** The codebase imported `utils.load_data`, but `utils/data_loader.py` was absent. Similarly, the IRSM data generation script (`irsm/data_generation.py`) was entirely missing.
*   **File I/O Blocker:** In `utils/io_helpers.py`, the function `load_detection_results()` verified `.csv` file extensions but loaded them using `pd.read_parquet()`, causing crashes.
*   **Runtime Bugs:**
    *   VLM validation scripts crashed on an invalid `save_interval` keyword parameter.
    *   The package initializer eagerly imported a backend depending on `python-dotenv`, which was commented out in the project environment, causing importing the package to fail entirely.
    *   Pandas zone-combination step crashed when merging categorical `zone1` and `zone2` columns before string coercion.
    *   The IRSM Isolation Forest model suffered from duplicate prediction outputs for identical pair IDs, inflating anomaly counts.

---

## 3. Chronological Iterations of Work Done

### Phase 1: Import Stabilization & Runtime Repair
*   Established a new, stable Conda environment (`flow_env`) with all correct dependencies (`geopandas`, `shapely`, etc.).
*   Developed a repository-relative path utility (`utils/paths.py`) and configured environment variables (`FLOW_ANALYTICS_DATA_BRUSSELS`, `FLOW_ANALYTICS_OUTPUT_ROOT`) to override paths dynamically, completely removing references to `/home/ubuntu/prem`.
*   Reconstructed the missing `utils/data_loader.py` to support Brussels hourly parquet layouts.
*   Fixed the `.csv` load bug in `utils/io_helpers.py` .
*   Made the Brussels lane/crosswalk entrypoints configurable with command-line arguments (`--data-dir`, `--output-dir`, `--config`, `--max-hours`, `--sample-limit`).
*   Wrote the automated active checks module `checks/active_pipeline_checks.py`.

### Phase 2: Local Data & Parameter Patching
*   Hourly parquet dataset representing Brussels traffic trajectories (`data/` folder).
*   Addressed a critical bug in crosswalk M-DRAC filtering where the crosswalk pedestrian-vehicle detector was applying lane-filtering and dropping valid crosswalk pairs. Fixed by adding a `skip_same_lane_filter` parameter inside `ModifiedDRAC.detect()`.
*   Implemented the missing IRSM risk-vector generation script (`irsm/data_generation.py`) for Brussels lane zones.
*   Ran anomaly detection via Isolation Forest and compared output anomalies against M-DRAC outputs, generating visualizations and saving plots for selected candidate anomaly pairs.

### Phase 3: Automated Runners for Multi-Day
*   Created `checks/run_brussels_smoke_window.py` to automate multi-day bounded sweeps.
*   Created `checks/summarize_active_results.py` to parse logs and results into a structured markdown report.
*   Ran bounded (`--max-hours 22`) lane and crosswalk runs across the entire local dataset (June 1, 2025 to June 7, 2025), confirming 100% execution success across all 14 runs.
*   Identified that full-day lane processing exhausts memory. Documented hourly bounded processing as the stable, operational pattern.

### Phase 4: CLI Alignment & Quality Deduplication
*   Aligned CLI parameters across lane and crosswalk scripts by implementing `--start-time` in `regions/brussels/crosswalk_main.py`.
*   Patched a crash in `ssm/utils.py` where pandas `Categorical` zone columns crashed during zone-label normalization.
*   Enhanced prediction quality in `irsm/models/isolation_forest.py` by implementing deduplication logic that only keeps the strongest anomaly per `pair_id` (preventing duplicate event inflation).
*   Regenerated final validation summary artifacts.

---

## 4. Specific File Changes

### Created Files
1.  **[utils/paths.py](utils/paths.py)**: Resolves paths dynamically relative to the repository root and handles environment-variable overrides.
2.  **[utils/data_loader.py](/utils/data_loader.py)**: Repo-relative data loader for hourly parquet layouts.
3.  **[irsm/data_generation.py](/irsm/data_generation.py)**: Extracts risk vectors for traffic interactions, establishing the unsupervised IRSM pipeline.
4.  **[irsm/compare_mdrac_irsm.py](/irsm/compare_mdrac_irsm.py)**: CLI utility to evaluate M-DRAC conflicts against IRSM anomaly predictions.
5.  **[checks/active_pipeline_checks.py](/checks/active_pipeline_checks.py)**: Continuous-integration check script verifying active pipelines.
6.  **[checks/run_brussels_smoke_window.py](/checks/run_brussels_smoke_window.py)**: Script to run bounded hourly sweeps over a date range.
7.  **[checks/summarize_active_results.py](/checks/summarize_active_results.py)**: Parses results and builds the validation markdown summary.

### Key Modified Files
1.  **[regions/brussels/lane_main.py](/regions/brussels/lane_main.py)** & **[regions/brussels/crosswalk_main.py](/regions/brussels/crosswalk_main.py)**: Hardened for configurable arguments, smoke bounds, and structured empty CSV saves. Crosswalk CLI is fully aligned with `--start-time`.
2.  **[utils/io_helpers.py](/utils/io_helpers.py)**: Fixed `load_detection_results()` reading CSV as parquet. Added detection schema checks.
3.  **[ssm/m_drac.py](/ssm/m_drac.py)**: Implemented `skip_same_lane_filter` to fix crosswalk pedestrian-vehicle conflict drops.
4.  **[ssm/utils.py](/ssm/utils.py)**: Hardened zone normalization logic to handle pandas `Categorical` columns without crashing.
5.  **[irsm/models/isolation_forest.py](/irsm/models/isolation_forest.py)**: Deduplicated anomaly outputs to select the highest-scoring record per `pair_id`.
6.  **[config.yaml](/config.yaml)**: Marked Safety Potential Fields (SPF) as `experimental-disabled`.

---

## 5. Current Brussels Validation Summary

The following results were generated using the stabilized pipeline over a bounded 2-hour window per day (`--max-hours 22`):

### M-DRAC Conflict Counts
| Date | Lane Conflicts | Crosswalk Conflicts | Lane Schema | Crosswalk Schema |
| :--- | :---: | :---: | :---: | :---: |
| 2025-06-01 | 2 | 36 | ok | ok |
| 2025-06-02 | 5 | 81 | ok | ok |
| 2025-06-03 | 5 | 100 | ok | ok |
| 2025-06-04 | 11 | 74 | ok | ok |
| 2025-06-05 | 5 | 93 | ok | ok |
| 2025-06-06 | 5 | 65 | ok | ok |
| 2025-06-07 | 2 | 46 | ok | ok |

*   **Total M-DRAC Conflicts Found:** 530 (No Postprocessing Done Yet)
*   **MDRAC Severity Stats:** Min = `3.401`, Median = `5.452`, Max = `22.552`

### IRSM Validation (June 1, 2025)
*   **Lane Risk Vectors:** 3,589
*   **IRSM Anomaly Pairs:** 34 unique pairs (after deduplication)

---

## 6. Blockers, Limitations, & Next Steps

### Scaling & Performance Blocker
*   **The Memory Issue:** Full-day processing of Brussels lane data continues to exhaust system memory because the lane pipeline does not run in a chunked/batched configuration when reading trajectory chunks.
*   **Mitigation:** The current pipeline remains limited to bounded hourly runs.
*   **Proposed Next Step:** Design a chunked full-day orchestrator script that loads and processes hourly data batches incrementally, merging output schemas.

### Algorithmic Verification
*   **False-Positives:** The absolute correctness of the 530 detected conflicts relies on default config thresholds.
*   **Proposed Next Step:** Review the generated replay links (such as those compiled in `UPDATED_brussels_validation_summary.md`) to tune M-DRAC/IRSM thresholds against actual false-positives.
