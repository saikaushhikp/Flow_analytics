# PREM - Pedestrian Risk Evaluation & Monitoring

Traffic safety analysis system for detecting near-miss conflicts using vehicle trajectory data.

## Overview

PREM (Pedestrian Risk Evaluation & Monitoring) is a comprehensive traffic safety analysis framework that detects near-miss conflicts between road users using trajectory-based safety metrics. The system processes vehicle/pedestrian detection data and identifies dangerous interactions using Modified DRAC (Deceleration Rate to Avoid Crash) and other SSMs.

## Key Features

### Multi-Zone Detection
- **Lane-based analysis:** Vehicle-vehicle conflicts in traffic lanes
- **Crosswalk analysis:** Pedestrian-vehicle interactions at crosswalks
- **Crossing zones:** Mixed-mode conflict detection

### Safety Metrics
- **M-DRAC (Modified DRAC):** Deceleration-based conflict detection
- **IRSM:** Intersection Risk Safety Metric (under development)
- **SPF:** Safety Potential Field (planned)

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
│   └── spf.py              # Safety Potential Field
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
conda activate prem_env
```

### Running Analysis

**Brussels Lanes (Vehicle-Vehicle):**
```bash
cd /home/ubuntu/prem
python regions/brussels/lane_main.py
```

**Brussels Crosswalks (Pedestrian-Vehicle):**
```bash
cd /home/ubuntu/prem
python regions/brussels/crosswalk_main.py
```

**Oulu Lanes (Vehicle-Vehicle):**
```bash
cd /home/ubuntu/prem
python regions/oulu/lane_main.py
```

**Oulu Crosswalks (Pedestrian-Vehicle):**
```bash
cd /home/ubuntu/prem
python regions/oulu/crosswalk_main.py
```

### Configuration

Edit dates in each region's scripts:
```python
START_DATE = "2025-06-01"
END_DATE = "2025-06-01"
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
/home/ubuntu/results/prem/mdrac/
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
