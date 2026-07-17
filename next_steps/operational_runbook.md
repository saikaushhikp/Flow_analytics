# Operational Runbook

Last updated on: 2026-07-17

This runbook is the practical reference for reproducing the active Brussels workflows in the current checkout.

## 1. Environment

Create and activate the repository environment:

```bash
conda env create -f environment.yaml
conda activate flow_env
```

Optional overrides:

```bash
export FLOW_ANALYTICS_DATA_BRUSSELS=/path/to/brussels/parquet/root
export FLOW_ANALYTICS_OUTPUT_ROOT=/path/to/output/root
```

If `FLOW_ANALYTICS_DATA_BRUSSELS` is unset, the scripts will use the repository-local `data/` folder when it exists.

## 2. Validate The Environment

Run the lightweight checks first:

```bash
python checks/active_pipeline_checks.py
```

## 3. Run Brussels M-DRAC

### Lane pipeline

```bash
python regions/brussels/lane_main.py \
  --start-date 2025-06-01 \
  --end-date 2025-06-01 \
  --start-time 00 \
  --max-hours 22
```

Output:

```text
results/mdrac/brussels/lanes/2025-06-01/mdrac_2025-06-01.csv
```

### Crosswalk pipeline

```bash
python regions/brussels/crosswalk_main.py \
  --start-date 2025-06-01 \
  --end-date 2025-06-01 \
  --start-time 00 \
  --max-hours 22
```

Output:

```text
results/mdrac/brussels/crosswalks/2025-06-01/mdrac_2025-06-01.csv
```

### Multi-day bounded window

```bash
python checks/run_brussels_smoke_window.py \
  --start-date 2025-06-01 \
  --end-date 2025-06-07 \
  --max-hours 22
```

## 4. Run Brussels IRSM

### Generate lane risk vectors

```bash
python irsm/data_generation.py \
  --date 2025-06-01 \
  --start-time 00 \
  --max-hours 22
```

Output:

```text
irsm/data/brussels/2025-06-01/lanes.csv
```

### Isolation Forest

```bash
python irsm/models/isolation_forest.py
```

Output:

```text
irsm/results/brussels/2025-06-01/lanes_detections.csv
```

### Gaussian anomaly model

```bash
python irsm/models/gaussian_anomaly.py
```

Typical outputs:

```text
irsm/results/brussels/2025-06-01/gaussian_results.csv
irsm/results/brussels/2025-06-01/gaussian_detections.csv
irsm/results/brussels/2025-06-01/gaussian_distributions.png
```

### Supervised training and inference

```bash
python irsm/models/supervised.py --train
python irsm/supervised_detect.py
```

Note: `irsm/supervised_detect.py` reads its date and output paths from module-level configuration. Check the file before batch use.

## 5. Run Brussels Bhattacharyya

```bash
python bhattacharyya/detect.py \
  --date 2025-06-01 \
  --max-hours 22
```

Outputs:

```text
results/bhattacharyya/brussels/lanes/2025-06-01/detections.csv
results/bhattacharyya/brussels/lanes/2025-06-01/summary.yaml
```

## 6. Evaluation and Comparison

Compare M-DRAC and IRSM on a day:

```bash
python irsm/compare_mdrac_irsm.py --date 2025-06-01
```

Run the Brussels evaluator:

```bash
python irsm/evaluator.py \
  --start-date 2025-06-01 \
  --end-date 2025-06-07 \
  --gold-path brussels_june_in.csv
```

Important caveat: canonical output generation is currently incomplete because `irsm/canonical_utils.py` does not write files.

## 7. Visualization

Plot Brussels zones:

```bash
python helpers/plot_zones.py --region brussels
```

Generate M-DRAC pair plots:

```bash
python plotter.py
```

Generate IRSM pair plots:

```bash
python irsm/irsm_plotter.py
```

Generate Brussels heatmaps:

```bash
python helpers/heatmaps.py
```

Generate object animations:

```bash
python helpers/animator.py 11791470 --data-dir data --out-dir animations
```

## 8. Refresh The Current Summary

```bash
python checks/summarize_active_results.py
```

This rebuilds:

```text
next_steps/UPDATED_brussels_validation_summary.md
```

## 9. Operating Guidance

- always pass explicit dates
- prefer bounded windows unless you are actively working on scaling
- record the command, date window, and config used for any reported metric
- do not assume old archive docs reflect the current code surface
