# Near-Miss Detection Framework

## Overview

This project implements a near-miss detection framework for traffic safety analysis in the regions of **Brussels (Belgium)** and **Oulu (Finland)**. The system analyzes vehicle trajectory data to identify dangerous interactions using validated safety measures and machine learning-based risk assessment.

**Primary Methods:**
1. **MDRAC (Modified DRAC)**: Production system for lane-based near-miss detection
2. **IRSM (Intelligent Risk Scoring Mechanism)**: ML-based risk modeling using Isolation Forest
3. **VLM Validation**: AI-assisted verification to accelerate manual review process

---

## Project Structure

```
prem/
├── ssm/                          # Surrogate Safety Measures modules
│   ├── utils.py                  # Pair extraction with acceleration/yaw/decel
│   └── m_drac.py                 # Modified DRAC with temporal averaging
├── filters/                      # Data quality filtering modules
│   ├── preprocessing/            # Pre-detection filters
│   │   ├── ghost_filter.py       # Ghost vehicle detection (spawn/despawn)
│   │   ├── teleportation_filter.py # Position jump detection
│   │   ├── overlap_filter.py     # SAT-based overlap detection
│   │   ├── lifetime_filter.py    # Short-lived detection removal
│   │   ├── static_filter.py      # Stationary vehicle removal
│   │   └── ...                   # Additional filters
│   └── postprocessing/           # Post-detection filters
│       └── teleportation_filter.py # Final cleanup
├── vlm/                          # VLM validation system
│   ├── __init__.py
│   ├── README.md                 # Comprehensive user guide
│   ├── prompts.py                # Prompt templates
│   ├── vlm_backend.py            # Gemini API + Qwen local
│   ├── utils.py                  # Plot generation utilities
│   ├── batch_validator.py        # Batch processing
│   └── validate.py               # User script
├── irsm/                         # Intelligent Risk Scoring Mechanism
│   ├── README.md                 # IRSM documentation
│   ├── configuration.yaml        # IRSM configuration
│   ├── data_generation.py        # Risk vector extraction
│   ├── risk_vector.py            # Feature extraction logic
│   └── models/                   # Classification models (in development)
├── regions/                      # Region-specific configurations
│   ├── brussels/                 # Brussels zone definitions
│   └── oulu/                     # Oulu zone definitions
├── utils/                        # Helper utilities
│   ├── data_loader.py            # Optimized data loading
│   ├── io_helpers.py             # File I/O operations
│   └── memory.py                 # Memory monitoring
├── plotter.py                    # Trajectory visualization
├── config.yaml                   # Master configuration
├── environment.yaml              # Conda environment spec
├── docs/                         # Documentation
│   ├── MDRAC_implementation.md   # M-DRAC technical details
│   └── progress/                 # Weekly progress logs
│       ├── week1-3.md            # Initial development
│       ├── week4.md              # Multi-criteria detection
│       ├── week5.md              # Data quality filters
│       ├── week6.md              # VLM validation system
│       ├── week7.md              # VLM enhancements + Oulu
│       └── week8.md              # Current week
└── results/                      # Analysis outputs
    ├── brussels/                 # Brussels results
    │   └── mdrac/                # MDRAC detections by day
    │       ├── 01/               # Daily results
    │       │   ├── mdrac_01.csv
    │       │   ├── mdrac_01_postprocessed.csv
    │       │   └── plots/        # VLM validation plots
    │       └── ...
    └── oulu/                     # Oulu results
        └── mdrac/                # Oulu MDRAC detections
```

---

## Primary Detection Method: Modified DRAC (M-DRAC)

**Status:** ✅ Production (actively used for Brussels and Oulu)

### Purpose
Detect near-miss events in lane-based scenarios using deceleration-based safety measures.

### Formula
```
MDRAC = closing_speed / [2 × (TTC - PRT)]
```

Where:
- **TTC**: Time-To-Collision (acceleration-aware)
- **PRT**: Perception-Reaction Time (vehicle type-specific)

### Detection Criteria

**Longitudinal conflicts** (yaw_diff < 30°):
- MDRAC > 3.4 m/s²

**Non-longitudinal conflicts** (yaw_diff ≥ 30°):
- MDRAC > 3.4 m/s² **AND** yaw_diff_rate > 15°/s
- (Dual-metric AND-logic for stricter validation)

### Key Features
- ✅ Perception-Reaction Time (PRT) by vehicle type (cars: 0.92s, trucks: 2.0s)
- ✅ Acceleration-aware TTC calculation (18.6% more accurate than constant velocity)
- ✅ Temporal averaging with 1-second rolling window (~25% noise reduction)
- ✅ Dual-metric detection for non-longitudinal conflicts
- ✅ Comprehensive data quality filters (ghost vehicles, teleportation)
- ✅ SAT-based physical impossibility filtering
- ✅ Multi-day batch processing
- ✅ Region-agnostic (Brussels + Oulu)

### Implementation
**File:** `ssm/m_drac.py`

**Usage:**
```python
from filters.preprocessing.ghost_filter import filter_ghost_vehicles
from filters.postprocessing.teleportation_filter import filter_teleportation
from ssm.m_drac import ModifiedDRAC

# Stage 1: Data quality filtering
df_clean = filter_ghost_vehicles(df, zone_wkt=GHOST_ZONE_WKT)
df_clean = filter_teleportation(df_clean, max_jump=3.5)

# Stage 2: MDRAC detection with temporal averaging
mdrac = ModifiedDRAC()
conflicts = mdrac.detect(df_clean)

# Stage 3: Save results
conflicts.to_csv('results/mdrac_conflicts.csv', index=False)
```

### Output Schema
```csv
timestamp, id1, id2, zone, interaction, leader, dist, TTC, MDRAC,
closing_speed, speed_diff, yaw_diff, conflict_type, severity, link
```

**Key fields:**
- `interaction`: Vehicle types (e.g., `car_v_truck`)
- `conflict_type`: `rear_end` or `head_on`
- `severity`: `normal`, `moderate`, `severe`
- `link`: Replay URL (10-second rewind for context)

---

## Secondary Method: IRSM (Intelligent Risk Scoring Mechanism)

**Status:** 🔄 In Development

### Purpose
Unsupervised near-miss classification using anomaly detection on multi-dimensional risk feature vectors.

### Approach
1. **Extract risk features** from ALL nearby vehicle pairs (not just detected conflicts)
2. **Model risk in 14D vector space**: distance, closing_speed, TTC, MDRAC, velocities, accelerations, etc.
3. **Apply Isolation Forest** to identify anomalies (potential near-misses)
4. **Compare with MDRAC** to find under/over-detected scenarios

### Benefits
- Unsupervised (no manual labeling required)
- Discovers patterns MDRAC might miss
- Provides alternative risk assessment
- Can be combined with MDRAC for ensemble approach

### Current Status
- ✅ Risk vector extraction implemented (`irsm/data_generation.py`)
- ✅ 14 features calculated per pair observation
- 🔄 Isolation Forest classification in refinement
- ⏳ Parameter optimization needed (contamination threshold)
- ⏳ Integration with VLM confidence scores planned

### Implementation
**File:** `irsm/data_generation.py`, `irsm/risk_vector.py`

**Usage:**
```bash
# Generate risk vectors for Brussels
conda run -n prem_env python irsm/data_generation.py \
  --region brussels \
  --date 2025-06-01 \
  --data-dir /data/uploads/brussels
```

**Output:** CSV with instantaneous risk features for each nearby pair

**See:** [irsm/README.md](irsm/README.md) for details

---

## VLM Validation System

**Status:** ✅ Production (actively used for verification)

### Purpose
Accelerate manual validation of MDRAC detections using Vision-Language Models (AI-assisted analysis).

### How It Works
1. Generate 5 trajectory plots for each detected pair
2. Combine into single 2×3 grid (80% token cost savings)
3. Send to VLM (Gemini API or local Qwen) with event metrics
4. Receive structured classification (confirmed/false positive) + confidence score

### Features
- ✅ Auto-detection of pairs from MDRAC CSV
- ✅ Dual backend: Gemini API (fast) + Qwen local (offline fallback)
- ✅ Batch validation with progress tracking
- ✅ Simplified prompts (70% token reduction from Week 6 to Week 7)
- ✅ Configuration-driven workflow via config.yaml

### Usage
```python
from vlm.batch_validator import validate_pairs_batch

results = validate_pairs_batch(
    csv_path='results/brussels/mdrac/01/mdrac_01.csv',
    data_df=df,
    pairs=None,  # Auto-detect all pairs
    output_dir='results/brussels/mdrac/01/plots'
)
```

**Output:** JSON classification + confidence + reasoning per pair

**See:** [vlm/README.md](vlm/README.md) for comprehensive guide

---

## Data Quality Filters

### Preprocessing (Applied before MDRAC detection)

1. **Ghost Vehicle Filter** (`filters/preprocessing/ghost_filter.py`)
   - Removes spawn/despawn artifacts (~3-5% of vehicles)
   - Polygon-based detection zone approach
   - 15-20% false positive reduction

2. **Teleportation Filter** (`filters/preprocessing/teleportation_filter.py`)
   - Detects unrealistic position jumps (~2-4% of vehicles)
   - Max jump: 3.5m @ 10Hz (calibrated to 126 km/h max speed)
   - 10-15% false positive reduction

3. **Lifetime Filter** (`filters/preprocessing/lifetime_filter.py`)
   - Removes short-lived detections (tracking noise)
   - Vehicle-type-specific minimum lifespan

4. **Static Filter** (`filters/preprocessing/static_filter.py`)
   - Removes stationary vehicles (parked cars)
   - Sustained low-speed detection

5. **Footpath/Crosswalk Filters**
   - Zone-based filtering for pedestrian areas
   - Angle-based crosswalk parallel movement removal

6. **Overlap Filter** (`filters/preprocessing/overlap_filter.py`)
   - SAT (Separating Axis Theorem) for physical impossibility
   - Orientation-aware collision detection
   - 0% false positives (validated)

### Postprocessing (Applied after MDRAC detection)

1. **Duration Filter**
   - Minimum 0.5s or 5 frames sustained event
   - Removes single-frame noise spikes

2. **Aggregation**
   - Groups by unique vehicle pairs
   - Max MDRAC per pair (worst-case scenario)

**Combined Impact:** ~40-50% false positive reduction

---

## Configuration

**Master config:** `config.yaml` (210 lines)

### Key sections:

```yaml
# MDRAC detection parameters
mdrac:
  prt:                           # Perception-Reaction Time by vehicle type
    4: 0.92                      # Car
    6: 1.5                       # Van
    7: 2.0                       # Truck
  min_mdrac: 3.4                 # m/s²
  avg_window: 1.0                # Temporal averaging window (seconds)
  yaw_diff_rate_threshold: 15.0  # °/s for non-longitudinal
  longitudinal_yaw_threshold: 30.0  # °

# Pair generation filters
filters:
  vehicle_labels: [4, 6, 7, 8]   # Car, van, truck, bus
  min_vehicle_speed: 1.5         # m/s
  max_distance: 8.0              # m
  max_ttc: 1.8                   # seconds

# VLM validation
vlm:
  primary_backend: "gemini"      # "gemini" or "local"
  paths:
    base_results: "/home/ubuntu/prem/results/brussels/mdrac"
    base_data: "/home/ubuntu/data/uploads/objects/clean"
  confidence_threshold: 70        # Minimum for "confirmed_near_miss"
```

---

## Regions Supported

### Brussels (Belgium)
- ✅ Urban intersection data
- ✅ Multi-day MDRAC analysis (7+ days processed)
- ✅ VLM validation operational
- ✅ Comprehensive zone definitions

### Oulu (Finland)
- ✅ Pedestrian crossing focus
- ✅ Region-specific filtering (footpath, crosswalk zones)
- ✅ Daily near-miss statistics
- ✅ Risk heatmap generation

**Extensibility:** Add new regions via `regions/` directory and `config.yaml`

---

## Input Data Format

**Required columns:**
```python
{
    'timestamp': float,      # Time in seconds
    'id': int,              # Unique vehicle ID
    'label': int,           # Vehicle type (1-8)
    'pos_x': float,         # X position (meters)
    'pos_y': float,         # Y position (meters)
    'vel_x': float,         # X velocity (m/s)
    'vel_y': float,         # Y velocity (m/s)
    'vel': float,           # Speed magnitude (m/s)
    'yaw': float            # Heading angle (radians)
}
```

**Vehicle labels:**
1=Pedestrian, 2=Bicycle, 3=Motorcycle, 4=Car, 5=E-scooter, 6=Van, 7=Truck, 8=Bus

---

## Performance

### Processing Times
- **Small dataset** (1 hour, ~10K objects): 10-30 seconds
- **Medium dataset** (1 day, ~100K objects): 2-5 minutes
- **Large dataset** (1 week, ~700K objects): 15-30 minutes

### Optimizations
- Vectorized NumPy/Pandas operations (no Python loops)
- Numba JIT compilation for critical paths
- Batch timestamp processing
- Early distance filtering (reduces O(N²) complexity)
- Efficient memory management

### False Positive Reduction
- Ghost filter: ~15-20%
- Teleportation filter: ~10-15%
- Temporal averaging: ~25%
- **Combined: ~40-50% overall reduction**

---

## Visualization

**File:** `plotter.py`

Generate comprehensive trajectory analysis:

```python
from plotter import plot_conflict_analysis

plot_conflict_analysis(
    df,
    id1=10520140,
    id2=10520195,
    output_dir='results/plots'
)
```

**Output (5 plots):**
1. 2D trajectory (spatial paths)
2. Distance over time
3. Closing speed over time
4. Velocity comparison
5. Yaw difference over time

**Features:** Auto folder creation, synchronized timestamps, professional styling

---

## Development Timeline

### Week 1-3 (Dec 10-31, 2025)
- Initial setup and filtering logic
- MDRAC implementation
- Memory optimization
- Code refactoring

### Week 4 (Dec 30 - Jan 5, 2026)
- Multi-criteria detection (rear-end vs head-on)
- Realistic TTC with acceleration (18.6% improvement)
- SAT-based overlap filtering
- Post-processing pipeline

### Week 5 (Jan 5-12, 2026)
- Ghost vehicle filter
- Teleportation filter
- Temporal averaging (1-second window)
- Dual-metric AND-logic for non-longitudinal
- Multi-day batch processing (7 days)
- **~40-50% false positive reduction achieved**

### Week 6 (Jan 12-19, 2026)
- VLM validation system implementation
- Gemini API + Qwen local backends
- Combined 2×3 plot grid (80% token savings)
- Batch validation pipeline
- Data reorganization (Brussels/Oulu structure)

### Week 7 (Jan 19-27, 2026)
- VLM workflow enhancements (auto-detection, simplified prompts)
- Oulu pedestrian crossing analysis
- Configuration-driven validation
- 70% token reduction (prompt optimization)
- Code refactoring for maintainability

### Week 8 (Jan 27+, 2026)
- Documentation updates (this README)
- IRSM refinement
- Cross-region analysis (planned)

---

## Archived/Experimental Methods

### Safety Potential Field (SPF)

**Status:** 🗄️ Experimental (not actively used)

**Note:** SPF was tested during early development but is **not currently used in production**. The framework includes SPF implementation (`ssm/spf.py`) for reference, but all active analysis relies on MDRAC and IRSM.

**Why not used:**
- MDRAC provides better results for lane-based scenarios
- SPF designed for general conflicts (crossing, merging) but current focus is lane-based
- Computational overhead not justified for current use cases

**Future potential:**
- May be revisited for specific non-lane scenarios
- Useful for perpendicular conflicts if scope expands
- Code preserved for future research

**Implementation:** See `ssm/spf.py` and `docs/SPF.md` if interested in historical context

---

## Environment Setup

```bash
# Create conda environment
conda env create -f environment.yaml

# Activate environment
conda activate prem_env

# Verify installation
python -c "from ssm.m_drac import ModifiedDRAC; print('Setup successful!')"
```

**Key dependencies:**
- Python 3.10
- NumPy, Pandas, SciPy
- Geopandas, Shapely (spatial operations)
- Numba (JIT compilation)
- Matplotlib, Seaborn (visualization)
- PyArrow (parquet files)
- google-genai, transformers (VLM)

---

## Quick Start

### 1. MDRAC Detection (Brussels)

```python
import pandas as pd
from ssm.m_drac import ModifiedDRAC

# Load data
df = pd.read_parquet('data/brussels/day_01.parquet')

# Detect near-misses
mdrac = ModifiedDRAC()
conflicts = mdrac.detect(df)

# Save results
conflicts.to_csv('results/brussels/mdrac/01/mdrac_01.csv', index=False)
```

### 2. VLM Validation

```python
from vlm.batch_validator import validate_pairs_batch

# Auto-validate all detections
results = validate_pairs_batch(
    csv_path='results/brussels/mdrac/01/mdrac_01.csv',
    data_df=df,
    pairs=None  # Auto-detect
)
```

### 3. IRSM Risk Vector Generation

```bash
conda run -n prem_env python irsm/data_generation.py \
  --region brussels \
  --date 2025-06-01
```

---

## Documentation

- **Technical details:** [docs/MDRAC_implementation.md](docs/MDRAC_implementation.md)
- **Weekly progress:** [docs/progress/](docs/progress/)
- **VLM guide:** [vlm/README.md](vlm/README.md)
- **IRSM guide:** [irsm/README.md](irsm/README.md)

---

## References

### MDRAC:
- Kuang Y, Qu X, Weng J, Etemad-Shahidi A (2015) "How Does the Driver's Perception Reaction Time Affect the Performances of Crash Surrogate Measures?" PLOS ONE 10(9): e0138617

### IRSM:
- Isolation Forest: Unsupervised anomaly detection algorithm
- Risk vector approach: Custom feature engineering

### Filters:
- SAT (Separating Axis Theorem): Convex collision detection
- Tracking artifact detection: Computer vision best practices
- Temporal averaging: Digital signal processing fundamentals

---

## Recent Updates (Week 7-8, Jan 2026)

- ✅ VLM auto-detection (no manual pair specification)
- ✅ Simplified prompts (70% token reduction)
- ✅ Oulu pedestrian crossing analysis
- ✅ Configuration-driven VLM workflow
- ✅ Documentation overhaul (README + progress reports)
- 🔄 IRSM Isolation Forest optimization (in progress)

---

**Developed by:** Prem  
**Environment:** Python 3.10 (Conda: `prem_env`)  
**Regions:** Brussels (Belgium), Oulu (Finland)  
**Last Updated:** January 27, 2026
