# Contributing Guide

Last updated on: 2026-07-17

This guide is for engineers who understand traffic-safety analytics but are new to this repository. It covers both contribution expectations and the detailed command surface needed to run the active Brussels workflows correctly.

> [!IMPORTANT]  
> This contribution guide is current with the latest commit [`3dbecb4178769040e2fb6874d57c923637b1eff1`](https://github.com/saikaushhikp/Flow_analytics/tree/3dbecb4178769040e2fb6874d57c923637b1eff1).  
> It provides essential guidance for executing all primary commands and workflows within this repository.


## 1. Scope and Expectations

This checkout is Brussels-first.

The maintained workflows are:

- Brussels lane M-DRAC
- Brussels crosswalk M-DRAC
- Brussels IRSM lane risk-vector generation
- Brussels IRSM unsupervised scoring
- Brussels IRSM supervised training and inference
- Brussels Bhattacharyya envelope lane detection
- review plots, GIFs, comparisons, and heatmaps

Do not treat older plans or archived notes as active operating guidance. Use:

- [README.md](README.md)
- [irsm/README.md](irsm/README.md)
- [next_steps/current_state.md](next_steps/current_state.md)
- [next_steps/known_issues.md](next_steps/known_issues.md)
- [next_steps/operational_runbook.md](next_steps/operational_runbook.md)

## 2. Branching and Contribution Rules

- do not commit directly to `main`
- use a branch like `name/feature-short-description`
- keep changes scoped
- if runtime behavior changes, update docs in the same branch
- if output schema changes, update checks and docs in the same branch

Useful commit shapes:

- `mdrac: tighten crosswalk filtering`
- `irsm: refresh supervised metrics docs`
- `docs: update Brussels runbook`

## 3. Environment Setup

This repository belongs to the conda environment `flow_env`.

Create it once if needed:

```bash
conda env create -f environment.yaml
```

Activate it for interactive work:

```bash
conda activate flow_env
```

Or run commands without activating:

```bash
conda run -n flow_env python checks/active_pipeline_checks.py
```

If you prefer wrappers for common commands, use the repository `Justfile`:

```bash
just --list
```

Optional path overrides:

```bash
export FLOW_ANALYTICS_DATA_BRUSSELS=/path/to/brussels/parquet/root
export FLOW_ANALYTICS_OUTPUT_ROOT=/path/to/output/root
```

If `FLOW_ANALYTICS_DATA_BRUSSELS` is unset, Brussels scripts use the repository-local `data/` folder when it exists.

## 4. Code Map

### Active execution entry points

- `regions/brussels/lane_main.py`
- `regions/brussels/crosswalk_main.py`
- `irsm/data_generation.py`
- `irsm/models/isolation_forest.py`
- `irsm/models/gaussian_anomaly.py`
- `irsm/models/supervised.py`
- `irsm/supervised_detect.py`
- `bhattacharyya/detect.py`
- `irsm/compare_mdrac_irsm.py`
- `checks/active_pipeline_checks.py`
- `checks/run_brussels_smoke_window.py`
- `checks/summarize_active_results.py`

### Core implementation

- `ssm/m_drac.py`: near-miss detector
- `ssm/utils.py`: pair generation and shared safety utilities
- `filters/preprocessing/`: trajectory cleaning filters
- `utils/data_loader.py`: hourly parquet loader
- `utils/io_helpers.py`: output schema and result I/O
- `utils/paths.py`: path resolution and environment overrides
- `irsm/risk_vector.py`: IRSM feature extraction
- `bhattacharyya/envelope.py`: Bhattacharyya safety-envelope overlap math

## 5. Contribution Workflow

Recommended sequence for any non-trivial change:

1. read the current docs
2. run the lightweight checks
3. reproduce the relevant bounded workflow
4. make the change
5. rerun the checks
6. rerun the relevant bounded workflow
7. update docs if behavior changed

## 6. Commands: What To Run and Why

All commands below assume you are at the repository root.

### 6.1 Validate imports and active contracts

Run this first after environment setup or before opening a PR:

```bash
conda run -n flow_env python checks/active_pipeline_checks.py
```

What it does:

- validates core config loading
- validates result schema round-tripping
- checks synthetic M-DRAC behavior
- checks active pair-generation assumptions

### 6.2 Brussels lane M-DRAC

Use this for vehicle-vehicle lane near-miss detection.

Single bounded day:

```bash
conda run -n flow_env python regions/brussels/lane_main.py \
  --start-date 2025-06-01 \
  --end-date 2025-06-01 \
  --start-time 00 \
  --max-hours 22
```

What it does:

- loads Brussels parquet data for the requested window
- applies lifetime, footpath, crosswalk-parallel, and static filters
- assigns lane zones
- generates nearby same-lane candidate pairs
- runs M-DRAC detection
- saves a conflict CSV

Output:

```text
results/mdrac/brussels/lanes/2025-06-01/mdrac_2025-06-01.csv
```

Important notes:

- use explicit `--start-date`, `--end-date`, and `--start-time`
- prefer `--max-hours 22` for reproducibility on a normal workstation
- full-day large-window lane processing is still memory-heavy

### 6.3 Brussels crosswalk M-DRAC

Use this for pedestrian-vehicle crosswalk detection.

Single bounded day:

```bash
conda run -n flow_env python regions/brussels/crosswalk_main.py \
  --start-date 2025-06-01 \
  --end-date 2025-06-01 \
  --start-time 00 \
  --max-hours 22
```

What it does:

- loads Brussels parquet data
- applies the shared preprocessing stack
- assigns crosswalk zones
- filters parallel vehicles
- generates crosswalk candidate pairs
- applies pedestrian-vs-vehicle label logic
- runs crosswalk-tuned M-DRAC

Output:

```text
results/mdrac/brussels/crosswalks/2025-06-01/mdrac_2025-06-01.csv
```

### 6.4 Multi-day bounded Brussels smoke window

Use this when you want the current stable multi-day reproduction pattern.

```bash
conda run -n flow_env python checks/run_brussels_smoke_window.py \
  --start-date 2025-06-01 \
  --end-date 2025-06-07 \
  --max-hours 22
```

What it does:

- runs the lane and crosswalk pipelines day by day
- keeps the runs bounded
- writes outputs under `results/mdrac/brussels/`

### 6.5 Summarize active results

Use this after smoke runs or artifact refreshes.

```bash
conda run -n flow_env python checks/summarize_active_results.py
```

What it does:

- scans the current bounded outputs
- rebuilds the active markdown summary

Output:

```text
next_steps/UPDATED_brussels_validation_summary.md
```

### 6.6 IRSM lane risk-vector generation

Generate the lane interaction feature table for a date:

```bash
conda run -n flow_env python irsm/data_generation.py \
  --date 2025-06-01 \
  --start-time 00 \
  --max-hours 22
```

What it does:

- reuses the Brussels preprocessing chain
- assigns lane zones
- generates nearby same-lane pairs
- extracts one risk vector per pair at the peak averaged M-DRAC moment

Output:

```text
irsm/data/brussels/2025-06-01/lanes.csv
```

### 6.7 IRSM Isolation Forest

```bash
conda run -n flow_env python irsm/models/isolation_forest.py
```

What it does:

- loads the configured `lanes.csv`
- selects the configured feature set
- trains Isolation Forest
- scores all pairs
- keeps anomaly rows
- deduplicates repeated anomaly rows by `pair_id`

Output:

```text
irsm/results/brussels/2025-06-01/lanes_detections.csv
```

### 6.8 IRSM Gaussian anomaly

```bash
conda run -n flow_env python irsm/models/gaussian_anomaly.py
```

What it does:

- loads the same IRSM lane vectors
- fits a stabilized multivariate Gaussian model
- saves score tables and distribution plots

Typical outputs:

```text
irsm/results/brussels/2025-06-01/gaussian_results.csv
irsm/results/brussels/2025-06-01/gaussian_detections.csv
irsm/results/brussels/2025-06-01/gaussian_distributions.png
```

### 6.9 IRSM supervised training

```bash
conda run -n flow_env python irsm/models/supervised.py --train
```

What it does:

- aligns Brussels labels from `brussels_june_in.csv`
- builds train / val / test splits
- trains Random Forest, XGBoost, and Neural Network models
- saves model artifacts and metrics

Important note:

- this is the training command
- it is heavier than the M-DRAC smoke checks
- use it when working on supervised IRSM, not as a first smoke test

### 6.10 IRSM supervised inference

```bash
conda run -n flow_env python irsm/supervised_detect.py
```

What it does:

- loads the configured day’s `lanes.csv`
- loads saved supervised models
- writes one output CSV per model

Important note:

- this script still uses module-level configuration instead of CLI flags
- inspect the file before running it for a different date or batch scenario

### 6.11 Compare M-DRAC and IRSM

```bash
conda run -n flow_env python irsm/compare_mdrac_irsm.py --date 2025-06-01
```

Use this to compare lane M-DRAC outputs against IRSM anomaly outputs for a specific Brussels day.

### 6.12 Evaluator

```bash
conda run -n flow_env python irsm/evaluator.py \
  --start-date 2025-06-01 \
  --end-date 2025-06-07 \
  --gold-path brussels_june_in.csv
```

Important caveat:

- canonical output generation is currently incomplete because `irsm/canonical_utils.py` does not write files to disk

### 6.13 Bhattacharyya envelope detection

Use this for Brussels lane near-miss detection based on Gaussian safety-envelope overlap.

```bash
conda run -n flow_env python bhattacharyya/detect.py \
  --date 2025-06-01 \
  --max-hours 22
```

What it does:

- loads Brussels parquet data
- applies the shared preprocessing chain
- generates nearby pairs
- computes future-horizon Bhattacharyya envelope overlap
- applies post-filters and temporal deduplication
- writes detections and a YAML summary

Outputs:

```text
results/bhattacharyya/brussels/lanes/2025-06-01/detections.csv
results/bhattacharyya/brussels/lanes/2025-06-01/summary.yaml
```

### 6.14 Visual review tools

Plot zones:

```bash
conda run -n flow_env python helpers/plot_zones.py --region brussels
```

Generate M-DRAC plots:

```bash
conda run -n flow_env python plotter.py
```

Generate IRSM plots:

```bash
conda run -n flow_env python irsm/irsm_plotter.py
```

Generate Brussels heatmaps:

```bash
conda run -n flow_env python helpers/heatmaps.py
```

Generate object animation GIFs:

```bash
conda run -n flow_env python helpers/animator.py 11791470 --data-dir data --out-dir animations
```

## 7. Current Operational Guidance

- use `flow_env`
- pass explicit dates
- prefer bounded windows unless working on scaling
- record the exact command when reporting counts or metrics
- do not assume a historical report is current just because it exists in the repository

## 8. What To Update When You Change Behavior

If you change behavior, update the relevant docs:

- `README.md`
- `irsm/README.md`
- `next_steps/current_state.md`
- `next_steps/known_issues.md`
- `next_steps/operational_runbook.md`
- `next_steps/UPDATED_brussels_validation_summary.md` if artifacts changed

## 9. Pre-PR Checklist

- `conda run -n flow_env python checks/active_pipeline_checks.py`
- rerun the specific workflow you changed
- confirm output paths still match the docs
- update docs if anything user-visible changed
- note limitations instead of hiding them
