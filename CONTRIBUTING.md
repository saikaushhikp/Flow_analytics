# Contributing Guide

> [!NOTE]  
> This guide summarizes the work completed up to Last commit [`05855ddd8f29a805b78d07301f733c41fdae0f51`](https://github.com/saikaushhikp/Flow_analytics/tree/05855ddd8f29a805b78d07301f733c41fdae0f51)  
> and also explains how to execute the main commands in this repository.

> [!TIP]
> Do not push changes directly to the `main` branch. 
> Create a branch named in the form `<name>/<feature-name>`, open a pull request for review, and merge only after verification.

---

This repository is a Brussels-first traffic safety analytics project. The active work centers on M-DRAC conflict detection and IRSM risk modeling for Brussels, with the current direction and open work captured in the documents under `next_steps/` such as `README.md`, `current_state.md`, `implementation_plan.md`, `UPDATED_NEW_implementation_plan.md`, `UPDATED_milestone_execution_status.md`, `UPDATED_brussels_validation_summary.md`, `known_issues.md`, and `operational_runbook.md`.

The practical goal of the codebase is to load trajectory parquet data, clean it with reusable filters, assign vehicles to region-specific zones, generate pairwise interactions, score them with M-DRAC or IRSM variants, and write reviewable outputs under `results/` and `irsm/results/`.

## Environment Setup

Contributors are expected to create and use a conda environment that matches `environment.yaml` before running the codebase. The documented environment name is `flow_env`, and the repo assumes the packages listed there are available for the Brussels and IRSM workflows.

## Current Project Direction

The active plan is to stabilize and improve the Brussels pipeline first. The main themes documented in `next_steps/` are:

- Brussels lane and crosswalk validation as the source-of-truth workflow.
- M-DRAC tuning and canonical output generation.
- IRSM lane risk-vector generation, anomaly detection, and supervised ranking.
- Comparison and evaluation tooling for shortlists and false-positive review.

## Planned Work

The planned work is intentionally staged:

- Keep Brussels lane and crosswalk runs reproducible and bounded.
- Maintain canonical output schemas for downstream evaluation.
- Continue IRSM development around risk-vector generation, anomaly scoring, supervised inference, and comparison reports.
- Build alternate IRSM methods in the documented experimental folders only after the baseline Brussels path is stable.

## Deprecated or Deferred Work

The following items are currently deprecated, deferred, or out of scope for the active Brussels-first phase:

- Oulu pipelines are deferred while Brussels is stabilized.
- SPF is experimental / disabled in the current configuration.
- VLM validation is out of the current active scope.
- Broad cross-region generalization is deferred until Brussels metrics improve.
- Full-day unbounded Brussels lane runs are treated as a scaling problem, not the default operating mode, because the current validation flow uses bounded smoke windows.
- IRSM supervised models are present, but the current docs warn that they must be used carefully and aligned with compatible training data.

## Code Map

### `filters/`

This package holds the reusable filtering steps that clean raw trajectories before detection.

- `filters/preprocessing/lifetime_filter.py`: removes short-lived objects that are unlikely to be meaningful interactions.
- `filters/preprocessing/zone_assignment.py`: attaches spatial zones to object trajectories.
- `filters/preprocessing/footpath_filter.py`: removes objects in pedestrian-only or false-detection footpath areas.
- `filters/preprocessing/crosswalk_filter.py`: handles crosswalk orientation logic and removes vehicles moving parallel to crossings.
- `filters/preprocessing/static_filter.py`: removes stationary or parked objects.
- `filters/preprocessing/ghost_filter.py`: holds ghost/spawn-despawn artifact filtering logic.
- `filters/preprocessing/overlap_filter.py`: filters overlapping pair artifacts.
- `filters/preprocessing/__init__.py`: exports the preprocessing helpers used by the pipelines.
- `filters/postprocessing/teleportation_filter.py`: removes unrealistic jumps after detection.
- `filters/postprocessing/__init__.py`: package marker for postprocessing filters.
- `filters/__init__.py`: package marker and high-level documentation only.

### `utils/`

This package provides shared infrastructure used by the Brussels and IRSM pipelines.

- `utils/data_loader.py`: loads hourly parquet folders over a date range, with optional dtype coercion and smoke-run limits.
- `utils/io_helpers.py`: defines the current M-DRAC result schema and saves or reloads detection CSV/XLSX files.
- `utils/memory.py`: prints process and DataFrame memory usage for operational debugging.
- `utils/paths.py`: centralizes repository, input-data, output-root, and config-path resolution.
- `utils/irsm_preprocessing.py`: reuses the Brussels cleaning pipeline for IRSM lane risk-vector generation.
- `utils/__init__.py`: re-exports the most commonly used helpers for scripts.

### `config.yaml`

This is the main runtime configuration for the Brussels pipeline and shared SSM helpers.

- `data`: parquet dtype hints and batch-loading settings.
- `preprocessing`: lifetime, footpath, crosswalk, static, ghost, and overlap filters.
- `filters`: pair-generation thresholds such as distance, lateral distance, TTC, and closing speed.
- `mdrac`: core M-DRAC thresholds, zone overrides, and severity settings.
- `spf`: retained experimental configuration for the disabled SPF path.
- `postprocessing`: teleportation and duration filters.
- `processing`: runtime batch-size and threading settings.
- `visualization`: plotting flags and output quality.
- `vlm`: validation settings kept for the optional VLM workflow.
- `output`: file format, metadata, and replay-link settings.

### `irsm/irsm_config.yaml`

This is the IRSM-specific configuration used by the Brussels lane risk-vector and anomaly-detection workflows.

- `region` and `date`: default Brussels evaluation context.
- `data`: input and output base paths for IRSM artifacts.
- `preprocessing`: switches for IRSM preprocessing stages.
- `zones`: current IRSM focus area, usually lanes.
- `pair_generation`: distance, lateral, TTC, and closing-speed thresholds for IRSM pair creation.
- `prt`: per-vehicle perception-reaction-time values.
- `aggregation`: aggregation method and window settings for risk-vector construction.
- `model`: feature columns and anomaly-model hyperparameters.
- `output`: whether outputs are written per zone or as a single file.
- `evaluation`: gold-label and canonical-output paths.
- `thresholds`: optimized M-DRAC thresholds for lanes and crosswalks.
- `feature_sets`: curated feature subsets for unsupervised and supervised models.
- `ensemble`: weights for the unsupervised ensemble score.
- `calibration`: probability calibration settings for supervised classifiers.

### `irsm/`

This package contains IRSM data generation, evaluation, canonicalization, model runners, and experimental alternatives.

- `irsm/risk_vector.py`: extracts the feature vectors used by IRSM.
- `irsm/data_generation.py`: generates Brussels IRSM lane risk vectors and writes `lanes.csv` outputs.
- `irsm/canonical_utils.py`: converts detector outputs into the canonical schema used by evaluation.
- `irsm/evaluator.py`: evaluates canonical predictions against `brussels_june_in.csv` and computes shortlist metrics.
- `irsm/compare_mdrac_irsm.py`: compares Brussels M-DRAC detections with IRSM anomalies for the same day.
- `irsm/supervised_detect.py`: runs supervised near-miss inference using saved models.
- `irsm/tune_mdrac.py`: tuning entry point for M-DRAC parameter search.
- `irsm/tune_unsupervised.py`: tuning entry point for unsupervised IRSM scorers.
- `irsm/irsm_plotter.py`: generates IRSM visualizations and review plots.
- `irsm/models/supervised.py`: defines supervised classifiers, training helpers, feature handling, and threshold logic.
- `irsm/models/isolation_forest.py`: trains and applies Isolation Forest anomaly detection.
- `irsm/models/gaussian_anomaly.py`: applies Gaussian anomaly detection.
- `irsm/models/__init__.py`: model package marker.
- `irsm/alternative_methods/meta_ensemble/meta_ensemble.py`: experimental ensemble ranking approach.
- `irsm/alternative_methods/temporal_sequence/temporal_classifier.py`: experimental temporal sequence classifier.
- `irsm/alternative_methods/surrogate_fusion/surrogate_fusion.py`: experimental surrogate-fusion pipeline.

### `regions/brussels/`

This folder contains the Brussels-specific operational pipelines and region geometry.

- `regions/brussels/lane_main.py`: Brussels lane M-DRAC pipeline for vehicle-vehicle conflict detection.
- `regions/brussels/crosswalk_main.py`: Brussels crosswalk M-DRAC pipeline for pedestrian-vehicle conflict detection.
- `regions/brussels/zones.py`: lane, crosswalk, and footpath zone definitions for Brussels.
- `regions/brussels/zone_plots/`: generated zone plots and visual references.
- `regions/brussels/Brussels.png`: Brussels map / reference image used by the notebooks and analysis.

## How The Main Pieces Fit Together

The typical flow is:

1. Load Brussels parquet data with `utils/data_loader.py`.
2. Clean the trajectories with `filters/preprocessing/*`.
3. Assign regions and zones from `regions/brussels/zones.py`.
4. Generate nearby pairs and score them with the M-DRAC logic in `ssm/` and the Brussels entry points.
5. Save results with `utils/io_helpers.py` and, for IRSM, canonicalize them with `irsm/canonical_utils.py`.
6. Evaluate and compare outputs with `irsm/evaluator.py` and `irsm/compare_mdrac_irsm.py`.

## How To Run The Main Executables

All commands below assume you are at the repository root. The Brussels parquet data used for the active validation window is expected to live under the repository-local `data/` folder.

<details>
<summary><b>Brussels M-DRAC pipelines</b></summary>

Run the Brussels lane pipeline:

```bash
python regions/brussels/lane_main.py --start-date 2025-06-01 --end-date 2025-06-01
```

Run the Brussels crosswalk pipeline:

```bash
python regions/brussels/crosswalk_main.py --start-date 2025-06-01 --end-date 2025-06-01
```

Run both Brussels pipelines over a bounded smoke window:

```bash
python checks/run_brussels_smoke_window.py --start-date 2025-06-01 --end-date 2025-06-01 --max-hours 24
```

Summarize the active Brussels validation artifacts:

```bash
python checks/summarize_active_results.py
```

Run the active pipeline sanity checks:

```bash
python checks/active_pipeline_checks.py
```
</details>

---

<details>
<summary><b>IRSM generation and detection</b></summary>

Generate IRSM lane risk vectors:

```bash
python irsm/data_generation.py --date 2025-06-01
```

Run Isolation Forest anomaly detection:

```bash
python irsm/models/isolation_forest.py
```

Run Gaussian anomaly detection if you are using that path:

```bash
python irsm/models/gaussian_anomaly.py
```

Run supervised IRSM detection:

```bash
python irsm/supervised_detect.py
```

Compare M-DRAC and IRSM outputs for a day:

```bash
python irsm/compare_mdrac_irsm.py --date 2025-06-01
```
</details>

Oulu shell wrappers exist in the repository, but they are currently deferred in the active plan.

## Notes For Contributing

- Keep changes aligned with the Brussels-first direction documented in `next_steps/`.
- Prefer updating shared helpers in `filters/` and `utils/` over duplicating logic in entry-point scripts.
- Preserve canonical result schemas when adding new detectors or evaluation paths.
- If you add a new executable entry point, document it in this file under “How To Run The Main Executables.”