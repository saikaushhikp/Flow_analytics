# Current State

## Project Purpose

PREM appears to mean Proactive Road Event Monitoring. The repository processes traffic object trajectories from parquet files and detects near-miss events for intersections/crosswalks. The main operational method is M-DRAC, with experimental or supporting work around SPF, IRSM, VLM validation, plotting, heatmaps, and postprocessing.

## Completed Work

### 1. Config-Driven M-DRAC Detection

The best-developed subsystem is M-DRAC:

- Pair generation is vectorized and batched in `ssm/utils.py`.
- Same-lane lane detection and crosswalk pedestrian-vehicle detection are separated.
- The M-DRAC detector has zone-specific averaging parameters.
- Brussels crosswalks use the clean `skip_label_filter=True` design instead of label spoofing.
- Outputs include replay links, interaction type, leader ID, distance, TTC, MDRAC, closing speed, speed difference, and yaw difference.

### 2. Multi-Region Support

The repository supports two regions:

- Brussels: lane zones, footpath zones, and five crosswalk zones.
- Oulu: lane zones, footpath zones, an exclusion zone, a crosswalk zone, and near-miss analysis zones.

Brussels scripts are more current than Oulu scripts.

### 3. Preprocessing Filter Library

Reusable filters exist for:

- Lifetime filtering.
- Footpath zone filtering.
- Crosswalk parallel-vehicle filtering.
- Static-object removal.
- Ghost vehicle filtering.
- SAT-based overlap filtering.
- Teleportation filtering.

These filters capture much of the former employee's false-positive reduction work.

### 4. Generated MDRAC Results

The `results/` folder already contains outputs:

- 74 M-DRAC CSV files.
- 2711 plot PNGs under `results/`.
- Brussels and Oulu lane/crosswalk result sets.
- Brussels daily statistics and risk heatmap.

Sample counts from current CSV files:

| Dataset | Example | Rows |
| --- | --- | ---: |
| Brussels lanes | `results/brussels/lanes/2025-06-03/mdrac_2025-06-03.csv` | 4 detections |
| Brussels crosswalks | `results/brussels/crosswalks/2025-06-03/mdrac_2025-06-03.csv` | 3 detections |
| Oulu lanes | `results/oulu/lanes/2025-08-22/mdrac_2025-08-22.csv` | 25 detections, but contains timestamps beyond 2025-08-22 |
| Oulu crosswalks | `results/oulu/crosswalks/2025-09-04/mdrac_2025-09-04.csv` | 34 detections |

### 5. Visualization and Analysis

Available tools:

- `plotter.py`: creates per-pair trajectory, distance, closing-speed, velocity, and yaw-difference plots.
- `plot_zones.py`: plots region zone layouts.
- `irsm/irsm_plotter.py`: plots IRSM pair IDs.
- Notebooks generate postprocessed outputs, daily stats, and heatmaps.

### 6. IRSM Prototype

IRSM is intended to create risk vectors for all interactions and then use anomaly detection rather than fixed MDRAC thresholds. Current implemented pieces:

- Risk vector extraction in `irsm/risk_vector.py`.
- Isolation Forest detector.
- Gaussian anomaly detector.
- Supervised classifier code.
- Visualization code.

However, the data-generation entrypoint referenced by docs is missing, so IRSM is not a complete runnable pipeline in this checkout.

### 7. VLM Validation Prototype

The VLM workflow is intended to validate M-DRAC detections by generating combined plots and sending them to Gemini or local Qwen. Core pieces exist, but the batch validator has a runtime bug and imports need cleanup.

### 8. Documentation History

The weekly progress docs are detailed and valuable for context:

- Week 1: memory optimization of base notebook.
- Week 2: initial M-DRAC, pair generation, SPF, plotting.
- Week 3: modularization.
- Week 4: overlap filters, multi-criteria ideas, duration filtering.
- Week 5: ghost/teleportation filters, temporal averaging.
- Week 6: VLM system.
- Week 7: VLM simplification, Oulu analysis, IRSM implementation.
- Week 8: crosswalk bug fix, clean `skip_label_filter`, batch scripts.

Treat them as historical notes, not source-of-truth. Several referenced files are absent or stale.

## Current Reality

The intended architecture is solid, but the repository is in a half-refactored state:

- Python syntax parses for all 41 Python files.
- The active base conda environment does not have project dependencies installed.
- The intended `flow_env` environment is not present locally.
- Several imports and references are currently broken.
- Many paths are hardcoded to `/home/ubuntu/prem`, while this checkout is at `/home/kaushik/Kezual/Flow_analytics`.
- The generated outputs are useful but not guaranteed to have been produced by the latest code.

The next phase should be a stabilization phase before adding new features.

