## Key Features

### Multi-Zone Detection
- **Lane-based analysis:** Vehicle-vehicle conflicts in traffic lanes
- **Crosswalk analysis:** Pedestrian-vehicle interactions at crosswalks
- **Crossing zones:** Mixed-mode conflict detection

### Safety Metrics
- **M-DRAC (Modified DRAC):** Deceleration-based conflict detection
- **IRSM:** Intersection Risk Safety Metric (under development)
- **SPF:** Safety Potential Field (experimental-disabled)

### Smart Filtering
- **Label-based:** Filter by interaction types (ped-vehicle, vehicle-vehicle, etc.)
- **Zone-specific:** Different thresholds per zone type
- **Same-lane filtering:** Optional for crosswalks where users cross lanes
- **Config-driven:** All parameters in `config.yaml`

## Project Structure

```
prem/
├── config.yaml              # Master configuration
├── ssm/                     # Safety metrics
│   ├── m_drac.py           # Modified DRAC detector
│   ├── utils.py            # Pairing and filtering utilities
│   └── spf.py              # Experimental-disabled Safety Potential Field
├── filters/                 # Preprocessing filters
│   └── preprocessing.py    # Lifetime, static, zone filters
├── regions/                 # Region-specific analysis
│   ├── brussels/           
│   │   ├── main.py         # Brussels analysis (lanes + crosswalks)
│   │   └── zones.py        # Zone definitions
│   └── oulu/
│       ├── main.py         # Oulu analysis (crossing + lanes)
│       └── zones.py        # Zone definitions
├── utils/                   # General utilities
│   ├── io_helpers.py       # Save/load results
│   └── logger.py           # Memory logging
└── irsm/                    # IRSM implementation (WIP)
```

## Quick Start

### Installation

```bash
conda env create -f environment.yaml
conda activate flow_env
```

### Running Analysis

**Brussels Lanes (Vehicle-Vehicle):**
```bash
cd /path/to/prem
python regions/brussels/lane_main.py
```

**Brussels Crosswalks (Pedestrian-Vehicle):**
```bash
cd /path/to/prem
python regions/brussels/crosswalk_main.py
```

Oulu pipelines are currently deferred while the Brussels + M-DRAC + IRSM path is stabilized.

### Configuration

Use CLI flags for dates and smoke runs:
```bash
python regions/brussels/lane_main.py --start-date 2025-06-01 --end-date 2025-06-01 --max-hours 1
```

By default, Brussels scripts use the repository-local `data/` folder when it exists.

Optional environment variables:
```bash
export FLOW_ANALYTICS_DATA_BRUSSELS=/path/to/objects/clean
export FLOW_ANALYTICS_OUTPUT_ROOT=/path/to/results
```

Tune detection parameters in `config.yaml`:
```yaml
mdrac:
  zone_overrides:
    crosswalks:
      avg_window: 0.2    # Fast ped-vehicle detection
    lanes:
      avg_window: 1.0    # Slower vehicle-vehicle detection
```

## Output Structure

```
results/mdrac/
├── brussels/
│   ├── lanes/
│   │   └── 2025-06-01/
│   │       └── mdrac_2025-06-01.csv
│   └── crosswalks/
│       └── 2025-06-01/
│           └── mdrac_2025-06-01.csv
└── oulu/
    ├── crossing/
    ├── lanes/
    └── crosswalks/
```

## Recent Updates (Jan 2026)

### ✅ Multi-Zone Detection Implemented
- Zone-specific MDRAC parameters via `zone_type` parameter
- Crosswalk ped-vehicle detection with `skip_same_lane_filter`
- Config-driven zone overrides in `config.yaml`

### ✅ Default Detection: Heavy Vehicles
- Default: `label_sets=([4,6,7,8], [4,6,7,8])` (cars, trucks, buses, motorcycles)
- Override for ped-vehicle: `label_sets=([1], [4,6,7,8])`

### ✅ Clean Architecture
- No hardcoded values in scripts
- Professional config-driven design
- Single source of truth in `config.yaml`

## Label Reference

| ID | Type | Default Detection |
|----|------|-------------------|
| 1 | Pedestrian | ❌ |
| 2 | Bicycle | ❌ |
| 3 | Trailer | ❌ |
| 4 | Car | ✅ |
| 5 | Van | ❌ |
| 6 | Truck | ✅ |
| 7 | Bus | ✅ |
| 8 | Motorcycle | ✅ |

## Key Configuration Parameters

### MDRAC Detection
```yaml
mdrac:
  min_mdrac: 3.4              # Minimum threshold (m/s²)
  avg_window: 1.0             # Temporal averaging (seconds)
  min_avg_frames: 3           # Minimum sustained frames
  
  zone_overrides:
    crosswalks:
      avg_window: 0.2         # Faster for ped-vehicle
      min_avg_frames: 1
```

### Filtering
```yaml
filters:
  max_distance: 8.0           # Maximum pairing distance (m)
  max_lateral_distance: 2.0   # Same-lane threshold (m)
  min_speed_diff: 0.5         # Minimum speed difference
  max_ttc: 5.0               # Maximum TTC threshold
```

## Development Status

### Production Ready ✅
- M-DRAC detection with multi-zone support
- Brussels lane & crosswalk analysis
- Oulu crossing & lane analysis
- Config-driven zone-specific parameters

### In Progress 🔧
- IRSM (Intersection Risk Safety Metric)
- SPF (Safety Potential Field) validation

### Planned 📋
- Automated conflict classification
- Time-series aggregation
- Multi-region comparison tools

## Contact & Support

For questions or issues, refer to project documentation in `docs/` directory.

## License

Internal research project - Flow Analytics

## Recent Improvements (February 2026)

### ✅ Feb 4, 2026: Clean skip_label_filter Implementation
**Major Achievement**: Eliminated all label spoofing workarounds with professional parameter-based design

**Problem Solved**: Double label filtering in crosswalk detection
- Crosswalk scripts pre-filter for ped-vehicle pairs
- Detector re-applied default vehicle-only filter  
- Result: Zero pedestrian conflicts detected

**Solution**: New `skip_label_filter` parameter allows bypassing redundant label filtering

```python
# Clean usage (no workarounds!)
detector = ModifiedDRAC(config, zone_type='crosswalks')
conflicts = detector.detect(crosswalk_pairs, 
                           is_pairs_data=True,
                           skip_label_filter=True)
```

**Benefits**:
- ✅ Zero technical debt (removed 35+ lines of workarounds)
- ✅ Backward compatible (default behavior preserved)
- ✅ Self-documenting (clear parameter name)
- ✅ Production tested (Day 3: 3 conflicts detected correctly)

### ✅ CLI Batch Processing
Scripts now accept date ranges for automated batch processing:

```bash
# Process entire Brussels dataset (214 days)
python regions/brussels/lane_main.py \
    --start-date 2025-06-01 --end-date 2025-12-31

python regions/brussels/crosswalk_main.py \
    --start-date 2025-06-01 --end-date 2025-12-31

# Or use batch scripts
./regions/brussels/brussels_lanes.sh
./regions/brussels/brussels_crosswalks.sh
```

**Features**:
- `--start-date` and `--end-date` CLI arguments
- Fallback to hardcoded defaults if no args
- Progress tracking: `[N/214] Processing 2025-06-XX`
- Error handling with continue prompts

## Advanced Usage Examples

### Pedestrian-Vehicle Detection (Crosswalks)

```python
from ssm.m_drac import ModifiedDRAC
from ssm.utils import get_mdrac_pairs

# Pre-filter for ped-vehicle pairs
crosswalk_pairs = get_mdrac_pairs(
    base_pairs,
    config,
    skip_pair_generation=True,
    label_sets=([1], [4, 6, 7, 8, 3, 2]),  # Ped × Vehicles
    skip_same_lane_filter=True  # Peds cross lanes
)

# Detect conflicts with skip_label_filter
detector = ModifiedDRAC(config, zone_type='crosswalks')
conflicts = detector.detect(
    crosswalk_pairs,
    is_pairs_data=True,
    skip_label_filter=True  # Don't re-filter labels
)
```

### Vehicle-Vehicle Detection (Lanes)

```python
# Use default label filtering
lane_pairs = get_mdrac_pairs(
    base_pairs,
    config,
    skip_pair_generation=True
    # label_sets defaults to ([4,6,7,8], [4,6,7,8])
)

detector = ModifiedDRAC(config, zone_type='lanes')
conflicts = detector.detect(
    lane_pairs,
    is_pairs_data=True
    # skip_label_filter defaults to False
)
```

## Testing & Verification

**Day 3 (2025-06-03) Verification**:
- ✅ Detected: 3 crosswalk ped-vehicle conflicts
- ✅ Output: Correct labels (pedestrian_v_car, bicycle_v_pedestrian)
- ✅ Data quality: No NaN values, valid MDRAC/TTC ranges
- ✅ MDRAC: 6.29 - 10.33 m/s² (all above 3.4 threshold)
- ✅ Architecture: Clean implementation, zero workarounds

## Documentation

**Comprehensive documentation** in `docs/`:
- `docs/progress/` - Weekly progress reports (Week 1-8)
- `docs/progress/week8.md` - Latest developments (skip_label_filter, batch processing)
- `docs/MDRAC_implementation.md` - M-DRAC technical details
- `docs/SPF.md` - Safety Potential Field documentation

**Latest Updates**: See `docs/progress/week8.md` for Feb 4, 2026 developments
