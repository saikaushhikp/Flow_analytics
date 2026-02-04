# IRSM (Interaction Risk Space Modelling)

**Unsupervised near-miss detection using Isolation Forest on interaction risk vectors.**

## Overview

IRSM models vehicular interactions to identify near-misses using machine learning. Unlike MDRAC (which flags high-risk moments), IRSM generates data containing BOTH near-misses AND normal interactions, then uses Isolation Forest to learn patterns that distinguish them.

## Quick Start

### 1. Configure Settings

Edit `irsm/irsm_config.yaml`:
```yaml
region: 'brussels'
date: '2025-06-01'

pair_generation:
  max_distance: 12.0          # How close vehicles must be (meters)
  max_lateral: 2.0            # Max side distance for "same lane" (meters)
  max_ttc: 15.0               # Max time to collision (seconds)
  min_closing_speed: 0.1      # Min approach speed (m/s)
  
model:
  contamination: 0.1          # Expected 10% anomalies
```

### 2. Generate Risk Vectors

```bash
conda run -n prem_env python irsm/data_generation.py
```

Output: `irsm/data/brussels/2025-06-01/lanes.csv` (~369 same-lane pairs)

### 3. Run Detection

```bash
conda run -n prem_env python irsm/models/isolation_forest.py
```

Output: `irsm/results/brussels/2025-06-01/lanes_detections.csv` (~37 detections at 10%)

## Pipeline Walkthrough

### Step-by-Step Process:

**1. Load Raw Data** → 39M trajectory rows from Brussels

**2. Preprocessing** (clean the data):
   - Remove short-lived vehicles (< 5 seconds)
   - Remove pedestrian area vehicles
   - Remove crossing pedestrians  
   - Remove parked/static vehicles
   - **Output:** ~15M clean rows

**3. Zone Assignment** → Assign each vehicle to lane zones
   - **Output:** ~4.6M rows in lanes

**4. Pair Generation**:
   - Find nearby pairs (within 12m)
   - Filter same-lane (lateral distance ≤ 2m)
   - Filter approaching (gap is closing)
   - **Output:** Thousands of pair observations

**5. Risk Vector Extraction**:
   - Apply TTC filter (≤ 15s) and closing speed filter (≥ 0.1 m/s)
   - Calculate MDRAC for each observation
   - **Aggregate by pair** (key step):
     - Calculate rolling average MDRAC (~1 second window)
     - Select timestamp with **HIGHEST** avg MDRAC
     - Return: `mdrac` = averaged; **other metrics = point values at that timestamp**
   - **NO threshold filtering** (IRSM needs both normal and risky cases)
   - **Output:** ~369 unique pairs

**6. Isolation Forest** → Train on all pairs, detect top 10% anomalies

## Configuration

All settings in `irsm_config.yaml`:

### Pair Generation
```yaml
pair_generation:
  max_distance: 12.0          # Spatial proximity (meters)
  max_lateral: 2.0            # Same lane threshold (meters)
  max_ttc: 15.0               # TTC threshold (seconds)
  min_closing_speed: 0.1      # Minimum approach speed (m/s)
```

### Vehicle-Specific PRT
```yaml
prt:
  default: 1.5                # Seconds
  car: 1.5
  truck: 2.0
  bus: 1.8
  motorcycle: 1.3
  bicycle: 1.0
```

### Model Settings
```yaml
model:
  contamination: 0.1          # 10% expected anomalies
  n_estimators: 100
  random_state: 42
```

## Data Schema

### lanes.csv (Risk Vectors)
Each row = one unique vehicle pair at peak avg MDRAC moment

**Columns:**
- **Metadata:** `pair_id`, `timestamp`, `label1`, `label2`, `link`, `same_zone`
- **Risk Features:**
  - `mdrac` - **Averaged** MDRAC over ~1 second window
  - `distance` - Point value at peak timestamp (meters)
  - `closing_speed` - Point value at peak timestamp (m/s)
  - `closing_accel` - Point value at peak timestamp (m/s²)
  - `ttc` - Point value at peak timestamp (seconds)
  - `yaw_diff` - Point value at peak timestamp (degrees)
  - `yaw_rate` - Point value at peak timestamp (deg/s)

### lanes_detections.csv (Anomalies)
Same columns as above, plus:
- `prediction` - -1 for anomaly, 1 for normal
- `anomaly_score` - Isolation Forest score (lower = more anomalous)

## Key Implementation Details

### Aggregation Logic
**For each unique pair:**
1. Calculate rolling average MDRAC (~10 frames/~1 second)
2. Find timestamp with HIGHEST avg MDRAC (no threshold)
3. Replace `mdrac` with avg value
4. Keep OTHER metrics as point values at that timestamp

**Why only MDRAC is averaged?**
- MDRAC benefits from averaging (smooths noise)
- Other metrics (distance, TTC) should reflect actual state at critical moment
- Matches ModifiedDRAC logic

**Why no threshold filtering?**
- IRSM learns from BOTH normal and risky interactions
- Isolation Forest needs full spectrum for pattern recognition
- MDRAC detection uses threshold (≥3.4), IRSM does not

### IRSM vs MDRAC

| Aspect | MDRAC Detection | IRSM |
|--------|----------------|------|
| **Purpose** | Flag near-misses | Learn patterns |
| **Data** | Only high-risk (≥3.4 m/s²) | Normal + risky |
| **Method** | Rule-based threshold | ML (Isolation Forest) |
| **Aggregation** | Peak moment above threshold | Peak moment (no filter) |
| **MDRAC value** | Averaged (same) | Averaged (same) |
| **Other metrics** | Point values (same) | Point values (same) |

## Example Results (Brussels 2025-06-01)

**With current config:**
```
max_distance: 12.0m, max_lateral: 2.0m, min_closing_speed: 0.1 m/s

Input:  39M rows
        ↓ Preprocessing
        15M rows → 4.6M in lanes
        ↓ Pair generation (12m, 2m lateral)
        Nearby → Same-lane → Approaching
        ↓ Risk extraction (TTC ≤15s, speed ≥0.1)
        369 unique pairs
        ↓ Isolation Forest (10%)
        37 anomalies detected
```

## Customization

### Capture More Interactions
```yaml
pair_generation:
  max_distance: 15.0          # Increase from 12m
  max_ttc: 20.0               # Increase from 15s
  min_closing_speed: 0.05     # Lower from 0.1
```

### Change Detection Rate
```yaml
model:
  contamination: 0.05         # 5% instead of 10%
```

## Directory Structure

```
irsm/
├── irsm_config.yaml          # All configuration
├── data_generation.py        # Generate same-lane pairs
├── risk_vector.py            # Extract & aggregate features
├── models/
│   └── isolation_forest.py  # Train & detect
├── data/
│   └── {region}/{date}/
│       └── lanes.csv         # Generated risk vectors
└── results/
    └── {region}/{date}/
        └── lanes_detections.csv  # Detected anomalies
```

## Requirements

- Python 3.10+
- pandas, numpy, scikit-learn
- Existing SSM utilities (filter_approaching, etc.)
- Region-specific zone definitions

## Region Support

Currently supported:
- ✅ Brussels (lane zones)
- ✅ Oulu (to be tested)

Add new regions by:
1. Defining lane zones in `regions/{region}/zones.py`
2. Updating `irsm_config.yaml`


## Supervised Near-Miss Detection

**NEW**: IRSM includes supervised learning models for near-miss classification.

> **⚠️ IMPORTANT**: Current supervised models trained on high-MDRAC data (5-10 m/s²) are **not compatible** with general IRSM lanes.csv data (MDRAC ~0.3 m/s²). Models will over-predict near-misses. Use **Isolation Forest** for IRSM data or retrain supervised models on IRSM-compatible training data.

### Quick Start

**1. Train Models** (one-time):
```bash
python3 irsm/models/supervised.py --train
```

**2. Run Detection**:

Edit `irsm/supervised_detect.py` variables:
```python
DATA_PATH = 'irsm/data/brussels/2025-06-01/lanes.csv'
OUTPUT_DIR = 'irsm/results/brussels/2025-06-01'
MODELS = ['random_forest', 'xgboost', 'neural_network']
THRESHOLD = 0.5
```

Then run:
```bash
python3 irsm/supervised_detect.py
```

**Output**: `{OUTPUT_DIR}/{model_name}.csv` (detected near-misses only)

### Models

Three trained classifiers:
- **Random Forest**: Ensemble decision trees
- **XGBoost**: Gradient boosting (best performance)
- **Neural Network**: MLP with early stopping

**Features used** (interactive only, 7 features):
- `distance`, `closing_speed`, `closing_accel`
- `ttc`, `mdrac`, `yaw_diff`, `yaw_rate`

**Performance** (on Brussels data):
- AUC: 1.000
- F1: 0.996-1.000
- Training: 2,752 balanced samples
- Test: 400 original pairs

### Supervised vs Unsupervised

| Method | Isolation Forest | Supervised Models |
|--------|-----------------|-------------------|
| Type | Unsupervised | Supervised |
| Training | No labels needed | Requires labeled data |
| Detection Rate | Configurable (contamination param) | Learned from data |
| Advantage | Works without labels | Higher accuracy with labels |
| Use Case | Initial exploration | Production detection |

### Files

```
irsm/
├── create_supervised_dataset.py    # Build training data
├── supervised_detect.py             # Detection script
├── models/
│   ├── supervised.py                # Classifier + training
│   ├── isolation_forest.py          # Unsupervised
│   ├── gaussian_anomaly.py          # Unsupervised
│   └── saved/                       # Trained models
└── data/supervised/                 # Train/val/test splits
```

## Notes

- All values configurable via `irsm_config.yaml` (no hardcoded values)
- Uses existing SSM functions (no reimplementation)
- Replay links: `https://di-india-collab-2.flow-analytics.io/tools/replay/`
- Only MDRAC is averaged; other metrics are point values
- No threshold filtering (unlike MDRAC detection)
