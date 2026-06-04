# Operational Runbook

This runbook describes the intended operations after the stabilization blockers are fixed. Some commands below will not work in the current checkout until [known_issues.md](known_issues.md) is addressed.

## Environment Setup

Intended setup:

```bash
conda env create -f environment.yaml
conda activate flow_env
```

Current local note from review:

- `flow_env` is not present on this machine.
- Active `base` does not include core dependencies such as `numpy` and `psutil`.

## Recommended Path Variables

The code currently hardcodes `/home/ubuntu/...` paths. Replace that with env/config-driven paths. Recommended variables:

```bash
export PREM_ROOT=/home/kaushik/Kezual/Flow_analytics
export PREM_DATA_BRUSSELS=/path/to/brussels/objects/clean
export PREM_DATA_OULU=/path/to/oulu/objects/clean/objects/clean
export PREM_OUTPUT_ROOT=/home/kaushik/Kezual/Flow_analytics/results
```

## Brussels Lane M-DRAC

Purpose: vehicle-vehicle conflicts in Brussels lane zones.

Intended command:

```bash
python regions/brussels/lane_main.py \
  --start-date 2025-06-03 \
  --end-date 2025-06-03
```

Expected output:

```text
results/brussels/lanes/2025-06-03/mdrac_2025-06-03.csv
```

Current result example exists with 4 detections.

## Brussels Crosswalk M-DRAC

Purpose: pedestrian/cyclist/vehicle conflicts in Brussels crosswalk zones.

Intended command:

```bash
python regions/brussels/crosswalk_main.py \
  --start-date 2025-06-03 \
  --end-date 2025-06-03
```

Expected output:

```text
results/brussels/crosswalks/2025-06-03/mdrac_2025-06-03.csv
```

Current result example exists with 3 detections. This script is the cleanest current crosswalk implementation because it uses `skip_label_filter=True`.

## Oulu Lane M-DRAC

Purpose: vehicle-vehicle conflicts in Oulu lane zones.

Intended command after fixing defaults/paths:

```bash
python regions/oulu/lane_main.py \
  --start-date 2025-09-04 \
  --end-date 2025-09-04
```

Expected output:

```text
results/oulu/lanes/2025-09-04/mdrac_2025-09-04.csv
```

Caution: the current script default spans multiple dates and saves under the start date. Always pass explicit same-day start/end until that is fixed.

## Oulu Crosswalk M-DRAC

Purpose: pedestrian/cyclist/vehicle conflicts in the Oulu crosswalk zone.

Do not run the current file as production code before cleanup. It contains duplicated execution blocks and old label-spoofing logic.

After cleanup, intended command:

```bash
python regions/oulu/crosswalk_main.py \
  --start-date 2025-09-04 \
  --end-date 2025-09-04
```

Expected output:

```text
results/oulu/crosswalks/2025-09-04/mdrac_2025-09-04.csv
```

## Batch Scripts

Existing batch scripts:

```bash
./brussels_lanes.sh
./brussels_crosswalks.sh
./oulu_lanes.sh
./oulu_crosswalks.sh
```

Notes:

- They assume conda `flow_env`.
- They assume `/home/ubuntu/...` data paths in the Python scripts.
- Oulu batch scripts prompt before running.
- Use only after one-day smoke runs pass.

## Plot Zones

Plot configured region zones:

```bash
python plot_zones.py --region brussels
python plot_zones.py --region oulu
```

Outputs:

```text
regions/brussels/zone_plots/all_zones.png
regions/oulu/zone_plots/all_zones.png
```

Only the Oulu plot exists in the current repository.

## Plot Detected Pair Trajectories

Using root plotter:

```python
from plotter import load_data, plot_all_pairs_from_csv

df = load_data("/path/to/brussels/objects/clean", "2025-06-03", "2025-06-03")
plot_all_pairs_from_csv(
    csv_path="results/brussels/lanes/2025-06-03/mdrac_2025-06-03.csv",
    data_df=df,
    show_plots=False,
)
```

## VLM Validation

Intended command:

```bash
python vlm/validate.py
```

Current blockers:

- `vlm/batch_validator.py` references undefined `save_interval`.
- `vlm/vlm_backend.py` has a package import issue.
- Gemini requires `GEMINI_API_KEY` or local Qwen dependencies/model.

After fixes, start with a dry-run mode that only generates combined plots and parses a fake response.

## IRSM

Intended future flow:

```bash
python irsm/data_generation.py
python irsm/models/isolation_forest.py
python irsm/models/gaussian_anomaly.py
```

Current blocker:

- `irsm/data_generation.py` is absent, so the first command cannot run.

The first operational IRSM task is restoring data generation to produce:

```text
irsm/data/{region}/{date}/lanes.csv
```

Then Isolation Forest should write:

```text
irsm/results/{region}/{date}/lanes_detections.csv
```

## Quick Health Checks

After environment and import fixes:

```bash
python -c "import utils; import ssm.utils; from ssm.m_drac import ModifiedDRAC; print('imports ok')"
python -c "from regions.brussels.zones import get_lane_zones; print(len(get_lane_zones()))"
python -c "from regions.oulu.zones import get_lane_zones; print(len(get_lane_zones()))"
python -c "from vlm.utils import parse_validation_response; print(parse_validation_response('Classification: confirmed_near_miss\nConfidence: 80\nReasoning: ok'))"
```

