# Accomplishments

Last updated on: 2026-07-17

This file summarizes what is already delivered and dependable in the current Brussels-first checkout.

## Repository Stabilization

- repository-relative path handling exists through `utils/paths.py`
- shared hourly parquet loading exists through `utils/data_loader.py`
- result I/O is standardized through `utils/io_helpers.py`
- active Brussels entry points no longer depend on old deployment paths

## Brussels M-DRAC

- lane pipeline is active
- crosswalk pipeline is active
- outputs are written under `results/mdrac/brussels/`
- replay links, pair plots, GIFs, and heatmaps are present

## Brussels IRSM

- lane risk-vector generation is active
- Isolation Forest and Gaussian anomaly scoring are active
- supervised training and inference code is present
- saved metrics and comparison reports exist in the repository

## Brussels Bhattacharyya

- a standalone envelope-overlap detector is present in `bhattacharyya/`
- day-level detections and summaries are written under `results/bhattacharyya/`
- the method now has dedicated documentation and is part of the documented current method surface

## Validation and Review Surface

- bounded Brussels smoke windows are the reproducible operating mode
- `checks/active_pipeline_checks.py` validates the active contracts
- `checks/summarize_active_results.py` rebuilds the active Brussels summary
- `plotter.py`, `irsm/irsm_plotter.py`, `helpers/plot_zones.py`, `helpers/heatmaps.py`, and `helpers/animator.py` support qualitative review

## Current Practical Meaning

The repository should now be understood as:

- operational for bounded Brussels reproduction
- suitable for M-DRAC, IRSM, and Bhattacharyya shortlist-quality work
- supported by existing result artifacts and visual review tools
- still limited by scaling issues on large lane windows
