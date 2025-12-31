# Near-Miss Detection Framework

## Overview

This project implements a comprehensive near-miss detection framework for traffic safety analysis using Surrogate Safety Measures (SSM). The system analyzes vehicle trajectory data to identify dangerous interactions and potential collision scenarios.

## Project Structure

```
prem/
├── ssm/                          # Surrogate Safety Measures modules
│   ├── utils.py                  # Pair extraction and filtering utilities
│   ├── m_drac.py                 # Modified DRAC implementation
│   ├── spf.py                    # Safety Potential Field implementation
│   └── evt.py                    # Extreme Value Theory (placeholder)
├── base_v2.ipynb                 # Main analysis notebook
├── config.yaml                   # Configuration parameters
├── plotter.py                    # Trajectory visualization module
├── docs/                         # Documentation
│   ├── base_code.md             # Base code documentation
│   ├── MDRAC_implementation.md  # M-DRAC technical details
│   ├── SPF.md                   # SPF technical details
│   └── progress/                # Weekly progress logs
│       ├── week1.md
│       ├── week2.md
│       └── week3.md
├── others/                       # Analysis notebooks
│   ├── threshold_analysis.ipynb # M-DRAC/SPF threshold visualization
│   └── debug_mdrac_missing.ipynb # Detection debugging
└── results/                      # Analysis outputs
    ├── mdrac_conflicts.csv       # M-DRAC detections (47 pairs)
    ├── spf_conflicts.csv         # SPF detections (2351 rows)
    └── plots/                    # Visualization outputs
        ├── mdrac/               # M-DRAC pair plots (16 folders)
        └── spf/                 # SPF pair plots
```

## Implemented Methods

### 1. Modified DRAC (M-DRAC)
**File:** `ssm/m_drac.py`

- **Purpose:** Longitudinal conflict detection for car-following scenarios
- **Formula:** `MDRAC = closing_speed / [2 × (TTC - PRT)]`
- **Applicable to:** Same-lane, same-direction vehicle interactions
- **Output:** Severity classification (normal/moderate/severe/critical)

**Key Features:**
- Perception-Reaction Time (PRT) by vehicle type
- Vectorized calculations for performance
- Modular filter pipeline
- Batch timestamp processing

### 2. Safety Potential Field (SPF)
**File:** `ssm/spf.py`

- **Purpose:** General conflict detection for all geometry types
- **Components:**
  - **O-field:** Physical collision probability (trajectory-based)
  - **S-field:** Driver discomfort (proximity-based)
  - **C-SPF:** Composite risk assessment
- **Applicable to:** Crossing, merging, head-on, perpendicular conflicts
- **Output:** Risk values [0.0, 1.0] with severity levels

**Key Features:**
- Trajectory intersection analysis
- Speed-dependent safety bubble modeling
- Multiple composite risk methods (max, probabilistic, weighted)
- Conflict type classification

### 3. Pair Extraction Utilities
**File:** `ssm/utils.py`

**Modular Filter Pipeline:**
1. `find_all_nearby_pairs()` - Base layer with distance/speed filters
2. `filter_approaching()` - Keep only converging pairs
3. `filter_same_lane()` - Lateral distance check for car-following
4. `classify_conflict_type()` - Geometry-based classification
5. `identify_leader_follower()` - Determine roles in interaction

**Method-Specific Pipelines:**
- `get_mdrac_pairs()` - Same-lane car-following conflicts
- `get_spf_pairs()` - All conflict types (no lane restriction)

## Configuration

**File:** `config.yaml`

### Key Parameters:

```yaml
filters:
  vehicle_labels: [4, 6, 7, 8]      # Car, van, truck, bus
  min_vehicle_speed: 1.5             # m/s
  max_distance: 8.0                  # m (reduced from 10.0 for stricter filtering)
  max_lateral_distance: 2.0          # m (same-lane threshold, reduced from 2.5)
  max_ttc: 2.0                       # seconds (reduced from 3.0 for imminent conflicts)
  min_closing_speed: 1.0             # m/s (increased from 0.5)
  min_speed_diff: 1.0                # m/s (increased from 0.5)

mdrac:
  prt:                               # Perception-Reaction Time by vehicle
    4: 0.92  # Car
    6: 1.5   # Van
    7: 2.0   # Truck
    8: 2.0   # Bus
  min_mdrac: 3.4                     # m/s²
  severity:
    severe: 7.0                      # Emergency braking
    moderate: 5.0                    # Hard braking
    normal: 3.4                      # Noticeable braking

spf:
  objective:
    beta_p: 10                       # Spatial shape factor
    beta_t: 2                        # Temporal shape factor
    t_star: 7.5                      # Time horizon (s)
  subjective:
    gamma_y: 1.4310                  # Lateral scale (m)
    beta_y: 4.9956                   # Lateral shape
  thresholds:
    warning: 0.37                    # e^-1 threshold
    danger: 0.70
    critical: 0.90
  min_risk: 0.37
  composite_method: 'max'
```

## Usage

### Basic M-DRAC Detection

```python
import pandas as pd
from ssm.m_drac import ModifiedDRAC

# Load vehicle trajectory data
df = pd.read_parquet('data/objects.parquet')

# Initialize detector
mdrac = ModifiedDRAC()

# Detect conflicts
conflicts = mdrac.detect(df)

# Save results
conflicts.to_csv('results/mdrac_conflicts.csv', index=False)
```

### Basic SPF Detection

```python
from ssm.spf import SafetyPotentialField

# Initialize detector
spf = SafetyPotentialField()

# Detect conflicts
conflicts = spf.detect(df)

# Save results
conflicts.to_csv('results/spf_conflicts.csv', index=False)
```

### Optimized Workflow (Recommended)

**Problem:** Traditional approach generates pairs twice (once for each detector)  
**Solution:** Generate base pairs once, reuse for both methods

```python
from ssm.utils import find_all_nearby_pairs, get_mdrac_pairs, get_spf_pairs
from ssm.m_drac import ModifiedDRAC
from ssm.spf import SafetyPotentialField

# Initialize detectors
config = load_config()
mdrac = ModifiedDRAC(config)
spf = SafetyPotentialField(config)

# Step 1: Generate base pairs ONCE (expensive O(n²) operation)
base_pairs = find_all_nearby_pairs(df, config)

# Step 2: Apply SPF-specific filters and detect
spf_pairs = get_spf_pairs(base_pairs, config, skip_pair_generation=True)
spf_conflicts = spf.detect(spf_pairs, is_pairs_data=True)

# Step 3: Apply M-DRAC-specific filters and detect
mdrac_pairs = get_mdrac_pairs(base_pairs, config, skip_pair_generation=True)
mdrac_conflicts = mdrac.detect(mdrac_pairs, is_pairs_data=True)
```

**Performance:** ~2-3x faster than traditional approach  
**Key parameters:**
- `skip_pair_generation=True`: Skip expensive pair generation in filter functions
- `is_pairs_data=True`: Treat input as pre-generated pairs in detect methods

### Custom Configuration

```python
from ssm.utils import load_config

# Load and modify config
config = load_config('config.yaml')
config['filters']['max_distance'] = 15.0
config['mdrac']['min_mdrac'] = 4.0

# Use custom config
mdrac = ModifiedDRAC(config=config)
conflicts = mdrac.detect(df)
```

## Input Data Format

**Required columns:**
```python
df = pd.DataFrame({
    'timestamp': float,      # Time in seconds
    'id': int,              # Unique vehicle ID
    'label': int,           # Vehicle type (1-8)
    'pos_x': float,         # X position (meters)
    'pos_y': float,         # Y position (meters)
    'vel_x': float,         # X velocity (m/s)
    'vel_y': float,         # Y velocity (m/s)
    'vel': float,           # Speed magnitude (m/s)
    'yaw': float            # Heading angle (radians)
})
```

**Vehicle labels:**
- 1: Pedestrian
- 2: Bicycle
- 3: Motorcycle
- 4: Car
- 5: E-scooter
- 6: Van
- 7: Truck
- 8: Bus

## Output Format

### M-DRAC Output
```csv
timestamp, id1, id2, interaction, leader, dist, TTC, MDRAC, 
closing_speed, speed_diff, yaw_diff, link
```

**Key fields:**
- `interaction`: Format `[label1]_v_[label2]` (e.g., `car_v_truck`)
- `leader`: ID of the leading vehicle
- `yaw_diff`: Absolute angular difference (degrees, normalized to [0, 180])
- `link`: Replay URL with 10-second rewind for visualization
  - Format: `https://di-india-collab.flow-analytics.io/tools/replay/{date}T{time-10s}Z`

### SPF Output
```csv
timestamp, id1, id2, interaction, dist, TTC, composite_risk, 
closing_speed, speed_diff, yaw_diff, link
```

**Key fields:**
- `interaction`: Format `[label1]_v_[label2]`
- `composite_risk`: Combined O-field + S-field risk score [0.0, 1.0]
- `yaw_diff`: Absolute angular difference (degrees)
- `speed_diff`: Absolute velocity difference (m/s)
- `link`: Replay URL for event visualization

## Performance

### Optimizations Implemented:
1. **Vectorized operations** - NumPy/Pandas for speed
2. **Batch timestamp processing** - Configurable chunk size
3. **Early distance filtering** - Reduces O(N²) complexity
4. **Memory management** - Immediate cleanup, dtype optimization
5. **Modular filters** - Only compute what's needed

### Typical Processing Times:
- **Small dataset** (1 hour, ~10K objects): 10-30 seconds
- **Medium dataset** (1 day, ~100K objects): 2-5 minutes
- **Large dataset** (1 week, ~700K objects): 15-30 minutes

## Visualization

### Trajectory Plotter
**File:** `plotter.py`

Generates comprehensive conflict analysis plots:

```python
from plotter import plot_conflict_analysis

# Analyze a specific pair
plot_conflict_analysis(
    df,
    id1=10538900,
    id2=10539068,
    output_dir='results/plots',
    show_plot=True
)
```

**Output plots:**
- `trajectory.png` - 2D spatial trajectories with minimum distance
- `distance.png` - Distance over time
- `closing_speed.png` - Closing speed over time (approaching/separating)
- `velocity.png` - Individual vehicle velocities over time

**Features:**
- Automatic pair-specific folder creation (`results/plots/{id1}_{id2}/`)
- Synchronized timestamp analysis
- Professional styling with consistent colors
- Minimum distance highlighting

## Development Timeline

### Week 1 (Dec 9-15)
- Initial filtering logic improvements
- Base code structure
- Memory optimization

### Week 2 (Dec 16-22)
- M-DRAC implementation and testing
- Performance optimization (distance filter reordering)
- SPF implementation
- Trajectory visualization module

### Week 3 (Dec 23-29)
- Code refactoring and modularization
- Enhanced documentation
- Configuration management
- Function naming improvements
- Plotter refactoring with velocity plot addition
- Workflow optimization (2.27x speedup)
- Lane-only detection for higher accuracy
- Output schema redesign with replay links

### Week 4 (Dec 30-31)
- Threshold analysis notebook (`others/threshold_analysis.ipynb`)
- Debug investigation for M-DRAC vs SPF detection differences
- M-DRAC/SPF time-series visualization with distance filtering
- Cleanup of plot folders (removed non-detected pairs)

## References

### M-DRAC:
- Kuang Y, Qu X, Weng J, Etemad-Shahidi A (2015) "How Does the Driver's Perception Reaction Time Affect the Performances of Crash Surrogate Measures?" PLOS ONE 10(9): e0138617

### SPF:
- Zuo et al. (2025) "Composite Safety Potential Field for Highway Driving Risk Assessment"
