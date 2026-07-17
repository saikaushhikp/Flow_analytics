# Current State

Last updated on: 2026-07-17

## Executive Summary

This repository is now a Brussels-first near-miss detection codebase with three active technical paths:

- `M-DRAC`: deterministic lane and crosswalk conflict detection
- `IRSM`: interaction risk-vector modeling with unsupervised and supervised ranking
- `Bhattacharyya`: envelope-overlap-based lane near-miss detection

The active workflows are usable, bounded, and backed by generated results already present in the repository. The main remaining challenge is scale, not basic functionality.

## What Is Working

### Brussels M-DRAC

- `regions/brussels/lane_main.py` runs lane-based M-DRAC detection
- `regions/brussels/crosswalk_main.py` runs crosswalk pedestrian-vehicle detection
- the Brussels preprocessing chain is shared and stable enough for bounded runs
- outputs are written with a consistent CSV schema
- replay links, pair plots, GIFs, and city heatmaps are available

### Brussels IRSM

- `irsm/data_generation.py` generates lane risk vectors
- `irsm/models/isolation_forest.py` runs unsupervised anomaly detection
- `irsm/models/gaussian_anomaly.py` runs Gaussian anomaly scoring and visualizations
- `irsm/models/supervised.py --train` trains the supervised models from Brussels labels
- `irsm/supervised_detect.py` performs inference on the configured day
- `irsm/compare_mdrac_irsm.py` produces day-level comparison reports

### Brussels Bhattacharyya

- `bhattacharyya/detect.py` runs the day-level envelope detector
- `bhattacharyya/envelope.py` implements the vectorized BC overlap logic
- outputs are written under `results/bhattacharyya/brussels/lanes/`

### Validation and Support Tooling

- `checks/active_pipeline_checks.py` covers the active code paths with lightweight checks
- `checks/run_brussels_smoke_window.py` automates bounded multi-day M-DRAC runs
- `checks/summarize_active_results.py` rebuilds the active summary markdown
- `plotter.py`, `irsm/irsm_plotter.py`, `helpers/heatmaps.py`, and `helpers/plot_zones.py` provide the review surface

## Current Reproducible Validation Surface

The most reliable validation window in the repository is the bounded Brussels run summarized in [UPDATED_brussels_validation_summary.md](UPDATED_brussels_validation_summary.md).

Highlights:

- 7-day Brussels bounded smoke window
- 116 total M-DRAC detections across lanes and crosswalks
- reproducible risk heatmaps for M-DRAC and IRSM
- replay-ready top conflicts with saved plots and GIFs

The current validation summary also records:

- June 1 lane IRSM vectors: `1386`
- June 1 Isolation Forest anomalies: `3`

Separately, the heatmap-generation pass aggregates `22` IRSM unsupervised detections across June 1 to June 7.

## Model State

### M-DRAC

M-DRAC is the most operationally explainable detector in the repository. The current implementation includes:

- zone-specific logic for lanes vs crosswalks
- adaptive follower-response handling
- replay-friendly outputs

### IRSM Unsupervised

Isolation Forest remains the active unsupervised baseline. Gaussian anomaly detection is supported as a complementary scorer and visualization source.

### IRSM Supervised

The supervised stack is present and trained from Brussels labels. The current saved metrics favor the Random Forest path for practical use:

- Random Forest test AUC: `0.863`
- XGBoost test AUC: `0.708`
- Neural Network test AUC: `0.869`, but still treated as experimental

## What Is Not Fully Solved

- full-day Brussels lane runs still hit memory limits on large windows
- canonical prediction saving is disabled in `irsm/canonical_utils.py`
- `irsm/supervised_detect.py` still relies on module-level configuration rather than CLI arguments
- several historical documents still refer to old scopes, old metrics, or removed components

## Active Development Direction

The current engineering direction should be:

1. improve ranking quality for top daily shortlists
2. reduce false positives without breaking reviewability
3. keep bounded Brussels runs reproducible
4. harden the evaluation surface before adding heavier model classes

## What To Ignore Unless Needed

Treat these as archive context unless your task explicitly needs them:

- older planning documents
- week-by-week `working*.md` logs
- historical references to Oulu, SPF production, or VLM workflows
- any document that predates the Brussels-first stabilization and still describes this checkout as partially missing core files
