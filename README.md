# Flow Analytics

Last updated on: 2026-07-17

Flow Analytics is a Brussels-first traffic safety repository for detecting and reviewing near-miss events from object-trajectory parquet data.

The active codebase has three main tracks:

- `M-DRAC`: deterministic near-miss detection for lane and crosswalk interactions.
- `IRSM`: feature-based interaction risk modeling using unsupervised and supervised ranking methods.
- `Bhattacharyya`: Gaussian safety-envelope overlap detection for Brussels lane interactions.

This repository is aimed at technical users who want to reproduce the Brussels June benchmark, inspect generated conflicts, and continue model development.

## Active Scope

The maintained operational scope is Brussels only:

- Brussels lane M-DRAC
- Brussels crosswalk M-DRAC
- Brussels IRSM lane risk-vector generation
- Brussels IRSM anomaly detection and supervised inference
- Brussels Bhattacharyya envelope lane detection
- Plotting, GIF generation, comparison reports, and city heatmaps

Oulu, SPF production, and VLM validation are not part of the current active workflow in this checkout.

## Repository Layout

```text
config.yaml                     Master runtime config for M-DRAC workflows
environment.yaml                Conda environment definition
regions/brussels/               Brussels entry points and zone definitions
ssm/                            Core surrogate-safety logic
filters/                        Preprocessing and postprocessing filters
utils/                          Shared path, data-loading, memory, and I/O helpers
irsm/                           Risk-vector generation, models, evaluation, plotting
bhattacharyya/                  Bhattacharyya envelope near-miss detector
checks/                         Smoke-window runner and lightweight validation checks
helpers/                        Standalone visualization and utility scripts
results/mdrac/                  M-DRAC outputs, plots, and heatmaps
irsm/results/                   IRSM outputs, plots, and heatmaps
next_steps/                     Current handoff docs and dated status/archive notes
```

## Environment Setup

```bash
conda env create -f environment.yaml
conda activate flow_env
```

Optional path overrides:

```bash
export FLOW_ANALYTICS_DATA_BRUSSELS=/path/to/brussels/parquet/root
export FLOW_ANALYTICS_OUTPUT_ROOT=/path/to/output/root
```

If `FLOW_ANALYTICS_DATA_BRUSSELS` is unset, the Brussels scripts prefer the repository-local `data/` folder.

There is also a minimal `Justfile` for common repo operations:

```bash
just --list
```

## Quick Start

Run bounded Brussels M-DRAC smoke windows:

```bash
python regions/brussels/lane_main.py \
  --start-date 2025-06-01 --end-date 2025-06-01 --start-time 00 --max-hours 22

python regions/brussels/crosswalk_main.py \
  --start-date 2025-06-01 --end-date 2025-06-01 --start-time 00 --max-hours 22
```

Generate IRSM lane vectors and run the unsupervised detector:

```bash
python irsm/data_generation.py --date 2025-06-01 --start-time 00 --max-hours 22
python irsm/models/isolation_forest.py
python irsm/models/gaussian_anomaly.py
```

Run the Bhattacharyya envelope detector:

```bash
python bhattacharyya/detect.py --date 2025-06-01 --max-hours 22
```

Optional supervised track:

```bash
python irsm/models/supervised.py --train
python irsm/supervised_detect.py
```

Operational utilities:

```bash
python checks/active_pipeline_checks.py
python checks/run_brussels_smoke_window.py --start-date 2025-06-01 --end-date 2025-06-07 --max-hours 22
python checks/summarize_active_results.py
python irsm/compare_mdrac_irsm.py --date 2025-06-01
python helpers/plot_zones.py --region brussels
python helpers/heatmaps.py
```

## What The Pipelines Produce

M-DRAC writes conflict CSVs under:

```text
results/mdrac/brussels/{lanes|crosswalks}/{date}/mdrac_{date}.csv
```

IRSM writes lane vectors and model outputs under:

```text
irsm/data/brussels/{date}/lanes.csv
irsm/results/brussels/{date}/lanes_detections.csv
irsm/results/brussels/{date}/gaussian_*.csv
irsm/results/brussels/{date}/{random_forest|xgboost|neural_network}.csv
```

Bhattacharyya writes lane detections under:

```text
results/bhattacharyya/brussels/lanes/{date}/detections.csv
results/bhattacharyya/brussels/lanes/{date}/summary.yaml
```

Review artifacts include:

- trajectory plots
- distance / closing-speed / yaw-difference plots
- `animation.gif` pair replays
- risk-space visualizations
- Brussels risk heatmaps

## Current Repository Status

As of July 17, 2026:

- The Brussels M-DRAC, IRSM, and Bhattacharyya paths are present in the current workflow surface.
- Bounded Brussels validation is the reproducible operating mode.
- Full-day Brussels lane processing is still a scaling problem because memory usage grows too high on large windows.
- The repository already contains generated Brussels outputs and validation summaries under `results/`, `irsm/results/`, and `next_steps/`.
- `irsm/canonical_utils.py` currently formats canonical predictions but does not write them to disk because the `to_csv()` call is commented out.
- `irsm/supervised_detect.py` is runnable, but it still uses module-level configuration instead of CLI arguments.

## Where To Read Next

- [CONTRIBUTING.md](CONTRIBUTING.md): contributor workflow and repo conventions
- [irsm/README.md](irsm/README.md): IRSM methodology, outputs, and model notes
- [bhattacharyya/README.md](bhattacharyya/README.md): Bhattacharyya envelope detector overview and run instructions
- [next_steps/README.md](next_steps/README.md): current handoff docs and archive map
- [next_steps/operational_runbook.md](next_steps/operational_runbook.md): reproduction steps and command reference
- [next_steps/current_state.md](next_steps/current_state.md): current project status and active outputs
