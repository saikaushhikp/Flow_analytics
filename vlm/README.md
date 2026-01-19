# VLM Near-Miss Validation

Simple validation system using Vision-Language Models to verify **Brussels M-DRAC** near-miss detections.

## Quick Start

1. **Set up API key** (create .env file):
```bash
cd /home/ubuntu/prem
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

Get free API key from: https://aistudio.google.com/app/apikey

2. **Install dependencies**:
```bash
pip install -r vlm/requirements.txt
```

3. **Edit variables in validate.py**:
```python
id1 = 10520140
id2 = 10520195
csv_path = "/home/ubuntu/prem/results/brussels/mdrac/01/mdrac_01.csv"
plots_path = "/home/ubuntu/prem/results/brussels/mdrac/01/plots"
output_path = "/home/ubuntu/prem/vlm_results"
```

4. **Run validation**:
```bash
cd /home/ubuntu/prem/vlm
python validate.py
```

## Brussels M-DRAC Schema

Your CSV columns:
- `timestamp`, `id1`, `id2`
- `zone` (e.g., "C-L1", "E-L2")
- `interaction` (e.g., "car_v_car")
- `leader` (which vehicle ID is leading)
- `dist`, `TTC`, `MDRAC`
- `closing_speed`, `speed_diff`, `yaw_diff`
- `link` (replay URL)

## Configuration

Edit `prem/config.yaml`:

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

1. Loads event data from CSV based on pair IDs
2. Finds corresponding trajectory plot
3. Sends plot + metrics to VLM (Gemini API first, local fallback on error)
4. VLM analyzes trajectories and validates near-miss
5. Saves results: `{id1}_{id2}_description.txt` and `{id1}_{id2}_metadata.json`

## Output Format

**description.txt** - Human-readable report with **model name**:
```
============================================================
NEAR-MISS VALIDATION REPORT
============================================================

Event IDs: 10520140 vs 10520195
Zone: C-L1
Interaction: car_v_car

------------------------------------------------------------
METRICS (M-DRAC)
------------------------------------------------------------
TTC: 1.10 s
MDRAC: 7.31 m/s²
Distance: 4.51 m

------------------------------------------------------------
VLM VALIDATION
------------------------------------------------------------
Classification: CONFIRMED_NEAR_MISS
Confidence: 85%
Backend Used: gemini-1.5-flash    ← MODEL NAME

Reasoning:
[VLM's detailed analysis]
```

**metadata.json** - Structured data:
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
