# Repository Inventory

Last updated on: 2026-07-17

This inventory is a practical code map for engineers who understand the traffic-safety domain but are new to this repository.

## Top-Level Structure

```text
README.md                      Current project overview
CONTRIBUTING.md                Contributor workflow
config.yaml                    Master config for M-DRAC and shared preprocessing
environment.yaml               Conda environment definition
regions/brussels/              Brussels pipelines and zone definitions
ssm/                           M-DRAC and shared pair-generation utilities
filters/                       Preprocessing and postprocessing filters
utils/                         Path resolution, data loading, memory, and I/O
irsm/                          Risk-vector generation, models, evaluation, plotting
bhattacharyya/                 Bhattacharyya envelope near-miss detector
checks/                        Lightweight checks and bounded-run helpers
helpers/                       Standalone utilities and visualization scripts
results/mdrac/                 M-DRAC outputs and analysis artifacts
irsm/results/                  IRSM outputs and analysis artifacts
next_steps/                    Current handoff docs plus dated project records
```

## Core M-DRAC Files

- `ssm/m_drac.py`
  - modified DRAC detector
  - handles zone-specific overrides for lanes vs crosswalks
  - formats final conflict output rows

- `ssm/utils.py`
  - shared config loading
  - pair generation and filtering
  - same-lane filtering
  - TTC and closing-speed related utilities

- `regions/brussels/lane_main.py`
  - Brussels lane entry point

- `regions/brussels/crosswalk_main.py`
  - Brussels crosswalk entry point
  - uses crosswalk-specific label handling and `skip_label_filter=True`

## Filters

Preprocessing lives in `filters/preprocessing/`:

- `lifetime_filter.py`
- `footpath_filter.py`
- `crosswalk_filter.py`
- `static_filter.py`
- `ghost_filter.py`
- `overlap_filter.py`
- `zone_assignment.py`

Postprocessing lives in `filters/postprocessing/`:

- `teleportation_filter.py`

## Shared Utilities

- `utils/paths.py`
  - repository-relative path resolution
  - environment-variable overrides

- `utils/data_loader.py`
  - loads hourly parquet folders over a date window
  - supports bounded runs through `start_time`, `max_hours`, and `sample_limit`

- `utils/io_helpers.py`
  - saves and reloads detection CSV/XLSX results
  - enforces the M-DRAC output schema

- `utils/irsm_preprocessing.py`
  - reuses the Brussels cleaning chain for IRSM generation

- `utils/memory.py`
  - process and DataFrame memory logging

## IRSM Files

- `irsm/data_generation.py`
  - generates one lane-vector file per date

- `irsm/risk_vector.py`
  - feature extraction and aggregation

- `irsm/models/isolation_forest.py`
  - unsupervised anomaly detector

- `irsm/models/gaussian_anomaly.py`
  - Gaussian anomaly detector and plots

- `irsm/models/supervised.py`
  - supervised training and metrics

- `irsm/supervised_detect.py`
  - supervised inference runner

- `irsm/evaluator.py`
  - gold-label evaluation utilities

- `irsm/compare_mdrac_irsm.py`
  - day-level comparison between M-DRAC and IRSM outputs

- `irsm/tune_mdrac.py`
  - M-DRAC tuning utilities

- `irsm/tune_unsupervised.py`
  - unsupervised-model tuning utilities

- `irsm/irsm_plotter.py`
  - IRSM pair plotting and GIF generation

- `irsm/visualize_risk.py`
  - risk-space visualizations

## Bhattacharyya Files

- `bhattacharyya/detect.py`
  - day-level runner for Brussels lane envelope detection

- `bhattacharyya/envelope.py`
  - safety-envelope construction
  - vectorized Bhattacharyya overlap computation
  - future-horizon near-miss extraction

- `bhattacharyya/bhattacharyya_config.yaml`
  - method-specific config reference

## Alternative IRSM Experiments

- `irsm/alternative_methods/meta_ensemble/`
- `irsm/alternative_methods/temporal_sequence/`
- `irsm/alternative_methods/surrogate_fusion/`

These are staged experiments, not the default path.

## Validation and Operations

- `checks/active_pipeline_checks.py`
  - lightweight integrity checks for the active Brussels stack

- `checks/run_brussels_smoke_window.py`
  - multi-day bounded M-DRAC runner

- `checks/summarize_active_results.py`
  - regenerates the active Brussels markdown summary

- `helpers/heatmaps.py`
  - city-level risk heatmaps from detection CSVs

- `plotter.py`
  - per-pair M-DRAC review plots

- `helpers/plot_zones.py`
  - zone layout visualization

- `helpers/animator.py`
  - object-level trajectory GIF generator

## Artifact Layout

M-DRAC:

```text
results/mdrac/brussels/lanes/{date}/
results/mdrac/brussels/crosswalks/{date}/
results/mdrac/brussels/analysis/
```

IRSM:

```text
irsm/data/brussels/{date}/
irsm/results/brussels/{date}/
irsm/results/brussels/analysis/
```

Bhattacharyya:

```text
results/bhattacharyya/brussels/lanes/{date}/
```

The repository also contains archive markdown reports and generated images under `next_steps/` and `images/`.
