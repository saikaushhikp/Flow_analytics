# VLM Near-Miss Validation

Vision-Language Model validation system for verifying M-DRAC near-miss detections using combined plot analysis.

## Features

✓ **Batch validation**: Process single or multiple pairs  
✓ **Combined plots**: 2×3 grid with 5 equal-sized subplots (80% token savings)  
✓ **Dual backend**: API-first (Gemini) with local fallback (Qwen)  
✓ **Progress checkpoints**: Save results every N pairs  
✓ **Modular design**: Clean separation of concerns  

## Quick Start

### 1. Set up API key

Create `.env` file in `/home/ubuntu/prem/`:
```bash
cd /home/ubuntu/prem
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

Get free API key from: https://aistudio.google.com/app/apikey

### 2. Activate environment

```bash
conda activate flow_env
cd /home/ubuntu/prem
```

### 3. Edit validate.py

Edit [vlm/validate.py](vlm/validate.py):
```python
# Define pairs to validate (single or multiple)
pairs = [(10520140, 10520195)]  # Or multiple: [(id1, id2), (id3, id4), ...]

# Set paths
csv_path = "/home/ubuntu/prem/results/brussels/mdrac/01/mdrac_01.csv"
data_path = "/home/ubuntu/data/processed/brussels/day_01_processed.parquet"
output_dir = "/home/ubuntu/prem/results/brussels/vlm_validation"
```

### 4. Run validation

```bash
python vlm/validate.py
```

## Usage

### Single Pair

```python
from vlm.batch_validator import validate_pairs_batch
import pandas as pd

# Load trajectory data
df = pd.read_parquet('trajectories.parquet')

# Validate one pair
results = validate_pairs_batch(
    csv_path='mdrac_results.csv',
    data_df=df,
    pairs=[(10520140, 10520195)],
    output_dir='results/validation'
)
```

### Multiple Pairs

```python
# Validate multiple pairs
pairs = [
    (10520140, 10520195),
    (10520200, 10520250),
    (10520300, 10520350)
]

results = validate_pairs_batch(
    csv_path='mdrac_results.csv',
    data_df=df,
    pairs=pairs,
    output_dir='results/validation',
    save_interval=10  # Checkpoint every 10 pairs
)
```

## Input Requirements

### CSV Schema (M-DRAC Results)

Required columns:
- `id1`, `id2` - Vehicle pair IDs
- `timestamp` - Event timestamp
- `zone` - Zone name (e.g., "C-L1")
- `interaction` - Interaction type (e.g., "car_v_car")
- `leader` - Leading vehicle ID
- `MDRAC` - Modified DRAC value (m/s²)
- `TTC` - Time to collision (seconds)
- `dist` - Minimum distance (meters)
- `closing_speed` - Relative closing speed (m/s)
- `speed_diff` - Speed difference (m/s)
- `yaw_diff` - Yaw angle difference (degrees)

### Trajectory Data (Parquet)

Full trajectory DataFrame with:
- `id` - Vehicle ID
- `timestamp` - Unix timestamp
- `x`, `y` - Position coordinates
- `speed`, `yaw` - Vehicle state

## Output Structure

```
results/validation/
├── validation_results.csv          # All results in one CSV
├── 10520140_10520195/
│   ├── combined_analysis.png       # 2×3 grid with 5 plots
│   └── validation.json             # Detailed result
├── 10520200_10520250/
│   ├── combined_analysis.png
│   └── validation.json
...
```

### Combined Plot Layout (2×3 Grid)

```
┌─────────────────┬─────────────────┬─────────────────┐
│   Trajectory    │  Distance vs    │ Closing Speed   │
│   (spatial)     │     Time        │   vs Time       │
├─────────────────┼─────────────────┼─────────────────┤
│   Velocity      │  Yaw Difference │                 │
│   vs Time       │    vs Time      │     (empty)     │
└─────────────────┴─────────────────┴─────────────────┘
```

All plots equal-sized, no metrics text overlay (data passed separately to VLM).

### validation.json

```json
{
  "id1": 10520140,
  "id2": 10520195,
  "classification": "confirmed_near_miss",
  "confidence": 85,
  "reasoning": "Detailed VLM analysis...",
  "backend": "gemini-1.5-flash",
  "MDRAC": 7.31,
  "TTC": 1.10,
  "dist": 4.51
}
```

### validation_results.csv

Consolidated results for all pairs with columns:
- `id1`, `id2`, `classification`, `confidence`, `reasoning`, `backend`
- All metrics from input CSV

## Configuration

Edit `/home/ubuntu/prem/config.yaml`:

```yaml
vlm:
  primary_backend: "gemini"  # or "local"
  gemini:
    model: "gemini-1.5-flash"
    api_key_env: "GEMINI_API_KEY"
    rate_limit_delay: 4
  local:
    model_id: "Qwen/Qwen2.5-VL-3B-Instruct"
    device: "auto"  # auto/cpu/cuda
```

## How It Works

1. **Load data**: CSV (event metrics) + Parquet (full trajectories)
2. **For each pair**:
   - Extract event data from CSV
   - Extract trajectory segments from Parquet
   - Generate 5 plots (trajectory, distance, closing speed, velocity, yaw diff)
   - Combine into single 2×3 grid image
   - Pass to VLM with metrics in prompt (not on image)
   - Parse structured response
3. **Save results**: Combined plot + JSON + consolidated CSV
4. **Progress checkpoints**: Save every N pairs

## Module Structure

```
vlm/
├── prompts.py              # Prompt templates
│   └── build_prompt()      # Main prompt builder
│
├── vlm_backend.py          # Core validation
│   ├── build_validation_prompt()
│   ├── validate_event()           # Main function (API + fallback)
│   ├── validate_with_gemini()
│   └── validate_with_qwen_local()
│
├── utils.py                # Helpers
│   ├── load_mdrac_csv()
│   ├── extract_pair_data()
│   └── save_combined_plot()       # Creates 2×3 grid
│
├── batch_validator.py      # Batch processing
│   └── validate_pairs_batch()     # Main entry point
│
└── validate.py             # User script
```

## Function Call Chain

```
validate.py
    └── batch_validator.validate_pairs_batch()
        ├── utils.load_mdrac_csv()
        ├── utils.extract_pair_data()
        ├── utils.save_combined_plot()
        └── vlm_backend.validate_event()
            ├── vlm_backend.build_validation_prompt()
            │   └── prompts.build_prompt()
            └── validate_with_gemini() or validate_with_qwen_local()
```

## Testing

```bash
conda activate flow_env
cd /home/ubuntu/prem
python vlm/test_refactored.py
```

Expected output:
```
Testing refactored VLM codebase...
============================================================
[1/4] Testing imports...
✓ All modules imported successfully
[2/4] Checking function names...
✓ All function names correct
[3/4] Checking for generic naming...
✓ No 'optimized' or 'robust' in function names/docs
[4/4] Verifying modular structure...
✓ Modular structure verified
============================================================
✓ All tests passed! VLM codebase is clean and modular.
```

## Troubleshooting

### Import errors
```bash
conda activate flow_env  # Make sure you're in the right environment
```

### API rate limits
Increase `rate_limit_delay` in config.yaml:
```yaml
vlm:
  gemini:
    rate_limit_delay: 6  # Increase from 4 to 6 seconds
```

### GPU memory issues (local backend)
```yaml
vlm:
  local:
    device: "cpu"  # Force CPU if GPU OOM
```

### Missing trajectory data
Check that your parquet file contains the required columns: `id`, `timestamp`, `x`, `y`, `speed`, `yaw`

## Recent Changes

### Refactoring (Jan 2026)
- ❌ Removed `validate_single_pair()` - use `validate_pairs_batch()` with single pair
- ✓ Renamed functions to generic naming (no "optimized", "robust")
- ✓ Single entry point for validation
- ✓ Cleaner module structure

## Notes

- **Token efficiency**: Combined plot reduces API cost by ~80% (1 image vs 5)
- **Equal sizing**: All 5 plots have identical dimensions in 2×3 grid
- **Generalized reasoning**: VLM analyzes cross-plot correlations, not individual plots
- **Error handling**: Continues processing on individual pair failures
- **Progress saving**: Prevents data loss on interruption

```json
{
  "event_data": {
    "id1": 10520140,
    "id2": 10520195,
    "TTC": 1.10,
    "MDRAC": 7.31,
    ...
  },
  "validation": {
    "classification": "confirmed_near_miss",
    "confidence": 85,
    "backend": "gemini-1.5-flash"    ← MODEL NAME
  }
}
```

## Troubleshooting

**API Key Error:**
- Make sure `GEMINI_API_KEY` is set in environment or .env file
- Get free API key from: https://aistudio.google.com/app/apikey

**Rate Limit:**
- Free tier: 1500 requests/day
- Adjust `rate_limit_delay` in config.yaml if hitting limits

**Local Fallback:**
- Downloads ~7GB model on first run
- Slow on CPU (30-60s per image)
- Use for offline validation or when API unavailable
