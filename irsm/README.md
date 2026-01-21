# IRSM (Intelligent Risk Scoring Mechanism)

Unsupervised near-miss classification system using anomaly detection on risk feature vectors.

## Directory Structure

```
irsm/
├── configuration.yaml       # All configuration (paths, features, models)
├── data_generation.py       # Generate risk vectors from detections
├── risk_vector.py           # Feature extraction logic
├── main.py                  # Classification pipeline (to be implemented)
├── data/                    # Generated risk vector datasets
│   ├── brussels/
│   │   └── YYYY-MM-DD.csv
│   └── oulu/
│       └── YYYY-MM-DD.csv
├── models/
│   └── isolation_forest.py  # Anomaly detection (to be implemented)
└── utils/
    └── __init__.py          # Helper functions
```

## Quick Start

### 1. Generate Risk Vectors

Extract risk features from **raw trajectory data** (generates ALL potential nearby pairs):

```bash
# Single date - Brussels
conda run -n prem_env python irsm/data_generation.py \
  --region brussels \
  --date 2025-06-01 \
  --data-dir /data/uploads/brussels

# Single date - Oulu
conda run -n prem_env python irsm/data_generation.py \
  --region oulu \
  --date 2025-06-01 \
  --data-dir /data/uploads/oulu_data
```

This will:
1. Load raw vehicle trajectories for the date
2. Extract ALL nearby pairs (using SSM's `find_all_nearby_pairs`)
3. Compute instantaneous risk features for EACH row
4. Save to `irsm/data/{region}/{date}.csv`

### 2. Classify Near-Misses (Coming Soon)

```bash
# Run Isolation Forest on generated risk vectors
conda run -n prem_env python irsm/main.py --region brussels --date 2025-06-01
```

## Data Schema

### Input: Raw Trajectory Data
```
Parquet files in date-partitioned directories
Columns: timestamp, id, label, pos_x, pos_y, vel, yaw, etc.
```

### Output: Risk Vector CSV
```csv
pair_id,timestamp,link,dist,closing_speed,speed_diff,vel1,vel2,yaw_diff,ttc,mdrac,...
10520140_10520195,2025-06-01 09:06:29.673,https://...,4.51,4.10,4.46,12.5,8.1,2.01,1.10,7.31,...
```

**Columns:**
- **Metadata:** `pair_id` (id1_id2), `timestamp`, `link`
- **Instantaneous measurements:** dist, closing_speed, speed_diff, vel1, vel2, yaw_diff, ttc, mdrac, lateral_offset, accel1, accel2, label1, label2, same_zone

**Note:** Each row is an instantaneous measurement at a specific timestamp (not aggregated statistics).

## Configuration

Edit [configuration.yaml](configuration.yaml) to customize:

```yaml
data:
  regions:
    brussels:
      csv_path: "/path/to/detections.csv"
      output_dir: "/path/to/output"

features:
  # Enable/disable feature groups
  temporal: [...]
  kinematic: [...]
  
models:
  isolation_forest:
    contamination: 0.05  # Expected % of near-misses
```

## Feature Extraction

The system extracts **14 instantaneous risk features** per pair observation:

| Feature | Description |
|---------|-------------|
| dist | Euclidean distance between vehicles (m) |
| closing_speed | Rate of gap closure (m/s) |
| speed_diff | Absolute speed difference (m/s) |
| vel1, vel2 | Individual vehicle speeds (m/s) |
| yaw_diff | Heading difference (degrees) |
| ttc | Time-to-Collision (seconds) |
| mdrac | Modified DRAC value |
| lateral_offset | Cross-track distance (m) |
| accel1, accel2 | Individual accelerations (m/s²) |
| label1, label2 | Vehicle types (1-8) |
| same_zone | Binary flag: 1 if same lane, 0 otherwise |

All calculations use formulas from SSM module (TTC, M-DRAC, etc.).

## Region Support

The system is **fully modular** and supports any region:
- Brussels ✓
- Oulu ✓
- Add new regions by updating `configuration.yaml`

## Next Steps

1. ✅ Risk vector extraction implemented
2. 🔄 Isolation Forest model (in progress)
3. 🔄 Main classification pipeline (in progress)
4. ⏳ VLM validation integration
5. ⏳ Batch processing automation

## Testing

Test risk vector extraction:
```bash
conda run -n prem_env python irsm/risk_vector.py
```

Test data generation:
```bash
conda run -n prem_env python irsm/data_generation.py --region brussels --date 2025-06-01
```
