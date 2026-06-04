# Repository Inventory

## Size and File Types

The repository contains 2859 tracked files excluding `.git` internals:

| Type | Count | Notes |
| --- | ---: | --- |
| Python | 41 | Core implementation, scripts, models, plotting |
| Markdown | 14 | README, progress reports, method docs |
| YAML | 3 | Main config, environment, IRSM config |
| Shell | 4 | Batch runners for Brussels/Oulu lanes/crosswalks |
| Notebooks | 6 | Earlier pipelines, analysis, postprocessing |
| CSV | 76 | Generated results and summaries |
| PNG | 2714 | Generated plots and heatmaps |

The codebase itself is modest. Most repository size is generated artifacts:

- `results/`: about 345 MB, mostly plots and MDRAC CSVs.
- `.git/`: about 903 MB.
- `regions/`: about 3.3 MB, including maps/notebooks.

## Top-Level Structure

- `config.yaml`: central runtime configuration for data dtypes, preprocessing filters, MDRAC thresholds, SPF, VLM, output paths.
- `environment.yaml`: intended conda environment named `flow_env`.
- `README.md`: high-level project overview. It is useful but partially stale.
- `ssm/`: surrogate safety metric implementations.
- `filters/`: preprocessing and postprocessing filters.
- `regions/`: region-specific zones and run scripts for Brussels and Oulu.
- `utils/`: memory and I/O helpers, plus IRSM preprocessing helper.
- `irsm/`: ML/anomaly-detection experiments for interaction risk vectors.
- `vlm/`: VLM-assisted validation workflow.
- `docs/`: historical method docs and weekly progress reports.
- `results/`: generated M-DRAC results, plots, and heatmap artifacts.
- `plotter.py`, `plot_zones.py`: visualization tools.

## Core M-DRAC Files

- `ssm/utils.py`
  - Loads YAML config.
  - Assigns zones with GeoPandas spatial joins.
  - Generates nearby pairs with timestamp batching.
  - Applies overlap filtering, approaching filtering, same-lane filtering, leader/follower identification, label filtering, TTC/closing-speed filters, yaw-diff-rate, and closing acceleration.
  - Provides `get_mdrac_pairs()` and `get_spf_pairs()`.

- `ssm/m_drac.py`
  - `ModifiedDRAC` detector.
  - Supports `zone_type` overrides from `config.yaml`.
  - Supports `is_pairs_data=True` for pre-generated pairs.
  - Supports `skip_label_filter=True`, which is the clean path for crosswalk pedestrian-vehicle pairs.
  - Applies instantaneous MDRAC threshold, dual-metric non-longitudinal filter, rolling-average peak selection, severity classification, and output formatting.

- `config.yaml`
  - Current MDRAC threshold: `min_mdrac: 3.4`.
  - Main vehicle labels default to `[4, 6, 7, 8]`.
  - Crosswalk zone override uses shorter averaging windows.

## Region Scripts

Brussels:

- `regions/brussels/zones.py`: lane, footpath, and crosswalk WKT polygons.
- `regions/brussels/lane_main.py`: lane vehicle-vehicle M-DRAC pipeline.
- `regions/brussels/crosswalk_main.py`: crosswalk pedestrian/cyclist/vehicle M-DRAC pipeline using `skip_label_filter=True`.

Oulu:

- `regions/oulu/zones.py`: single crosswalk zone, footpaths, near-miss zones, exclusion zone, and lane polygons.
- `regions/oulu/lane_main.py`: lane vehicle-vehicle M-DRAC pipeline.
- `regions/oulu/crosswalk_main.py`: crosswalk pipeline, but currently duplicated and still using old label-spoofing workaround.

Batch runners:

- `brussels_lanes.sh`
- `brussels_crosswalks.sh`
- `oulu_lanes.sh`
- `oulu_crosswalks.sh`

## Filters

Preprocessing:

- `filters/preprocessing/lifetime_filter.py`: removes IDs with too few frames.
- `filters/preprocessing/footpath_filter.py`: removes disallowed or too-fast vehicle labels in footpath zones.
- `filters/preprocessing/crosswalk_filter.py`: removes vehicles traveling parallel to crosswalk axes.
- `filters/preprocessing/static_filter.py`: removes mostly stationary IDs.
- `filters/preprocessing/zone_assignment.py`: spatially attaches zone IDs.
- `filters/preprocessing/ghost_filter.py`: removes vehicles spawning/despawning inside an inner polygon.
- `filters/preprocessing/overlap_filter.py`: SAT-based oriented-rectangle overlap filter for impossible pairs.

Postprocessing:

- `filters/postprocessing/teleportation_filter.py`: flags or removes teleportation/jump artifacts.
- `filters/postprocessing/__init__.py` mentions a duration filter, but no duration-filter file exists in the current checkout.

## IRSM

Current files:

- `irsm/irsm_config.yaml`: region/date, input/output paths, pair-generation thresholds, PRT values, model parameters.
- `irsm/risk_vector.py`: extracts risk vectors from pairs, computes MDRAC, aggregates to peak averaged MDRAC.
- `irsm/models/isolation_forest.py`: unsupervised anomaly detector.
- `irsm/models/gaussian_anomaly.py`: Gaussian anomaly detector and plots.
- `irsm/models/supervised.py`: supervised classifiers and training CLI.
- `irsm/supervised_detect.py`: manual runner for saved supervised models.
- `irsm/visualize_risk.py`: 3D/2D risk-space visualization.
- `irsm/irsm_plotter.py`: trajectory plots for IRSM pair IDs.

Referenced but missing:

- `irsm/data_generation.py`
- `irsm/create_supervised_dataset.py`
- `irsm/data/supervised/*`
- `irsm/models/saved/*` is intentionally gitignored.

## VLM

- `vlm/prompts.py`: prompt construction.
- `vlm/vlm_backend.py`: Gemini-first validation with local Qwen fallback.
- `vlm/utils.py`: response parsing, MDRAC CSV extraction, combined 2x3 plot generation.
- `vlm/batch_validator.py`: validates many pairs from a CSV.
- `vlm/validate.py`: day-based Brussels validation script.

The VLM code needs fixes before use. See [known_issues.md](known_issues.md).

## Notebooks

- `postprocessing.ipynb`: general M-DRAC/SPF postprocessing.
- `regions/brussels/main.ipynb`: original Brussels pipeline.
- `regions/brussels/postprocessing.ipynb`: Brussels post-detection filters.
- `regions/brussels/analyze_nearmiss.ipynb`: Brussels statistics and heatmap.
- `regions/oulu/main.ipynb`: original Oulu crossing and lane analysis.
- `regions/oulu/analyze_nearmiss_oulu.ipynb`: Oulu statistics and heatmaps.

The notebooks are useful as historical references, but the Python scripts should become the maintained operational path.

## Generated Results

Detected result CSV coverage in `results/`:

- Brussels lanes: 2025-06-01 through 2025-06-14.
- Brussels crosswalks: selected days from 2025-06-01 through 2025-06-14, excluding 2025-06-05 and 2025-06-08 in the current CSV set.
- Oulu lanes: selected dates from 2025-07-10 through 2025-09-09.
- Oulu crosswalks: selected dates from 2025-07-10 through 2025-09-11.
- Brussels analysis: `daily_nearmiss_stats.csv` and `risk_heatmap.png`.

Result CSV schema is generally:

```text
timestamp,id1,id2,zone,interaction,leader,dist,TTC,MDRAC,closing_speed,speed_diff,yaw_diff,link
```

Some Oulu crosswalk CSVs also include `label1,label2` because they came from the older label-spoofing workaround.

