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
├── docs/                         # Documentation
│   ├── base_code.md             # Base code documentation
│   ├── MDRAC_implementation.md  # M-DRAC technical details
│   ├── SPF.md                   # SPF technical details
│   └── progress/                # Weekly progress logs
│       ├── week1.md
│       ├── week2.md
│       └── week3.md
└── results/                      # Analysis outputs
    └── mdrac_conflicts.csv
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
  max_distance: 10.0                 # m
  max_lateral_distance: 2.5          # m (same-lane threshold)
  max_ttc: 3.0                       # seconds
  min_closing_speed: 2.0             # m/s
  min_speed_diff: 0.5                # m/s

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
```
timestamp, pair_id, interaction, distance, ttc, closing_speed, 
speed_diff, mdrac, severity
```

### SPF Output
```
timestamp, pair_id, interaction, conflict_type, distance, ttc, 
closing_speed, o_field, s_field, composite_risk, severity
```

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

### Week 3 (Dec 23+)
- Code refactoring and modularization
- Enhanced documentation
- Configuration management
- Function naming improvements

## References

### M-DRAC:
- Kuang Y, Qu X, Weng J, Etemad-Shahidi A (2015) "How Does the Driver's Perception Reaction Time Affect the Performances of Crash Surrogate Measures?" PLOS ONE 10(9): e0138617

### SPF:
- Zuo et al. (2025) "Composite Safety Potential Field for Highway Driving Risk Assessment"
