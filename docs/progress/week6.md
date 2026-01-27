# Week 6 Progress: VLM Near-Miss Validation System

**Period**: January 12-19, 2026  
**Focus**: AI-assisted validation system to accelerate near-miss verification process

---

## Summary

Implemented a comprehensive Vision-Language Model (VLM) validation system to automate and accelerate the verification of MDRAC-detected near-miss events. The system uses AI to analyze trajectory plots and event metrics, providing structured classifications with confidence scores.

### Key Achievements
- ✅ VLM validation system with dual backend support (Gemini API + local Qwen fallback)
- ✅ Combined 2×3 plot grid generation (80% token savings vs 5 separate images)
- ✅ Batch validation pipeline with progress tracking
- ✅ Structured JSON output with classification, confidence, and reasoning
- ✅ Integration into config.yaml for easy configuration
- ✅ Modular architecture: prompts, backends, utilities, batch processing

---

## 1. Problem Statement

Manual validation of near-miss detections is time-consuming and subjective:
- MDRAC detects hundreds of potential near-misses per day
- Manual review of each event requires analyzing multiple plots
- Human validation is slow (5-10 minutes per event)
- Need faster way to prioritize which events to investigate deeply
- Desire for consistent, repeatable validation criteria

---

## 2. Solution: VLM-Based Validation

Implemented AI-powered validation using Vision-Language Models:

**Architecture**:
```
MDRAC Detection Results (CSV)
         ↓
Extract Pair Data + Trajectories
         ↓
Generate 5 Trajectory Plots
         ↓
Combine into Single 2×3 Grid
         ↓
VLM Analysis (Gemini API or Local Qwen)
         ↓
Structured Output (JSON)
```

**Key Innovation**: Combined plot approach
- Traditional: 5 separate images per event → expensive, slow
- Our approach: Single 2×3 grid with all 5 plots → 80% cost reduction

---

## 3. Module Structure

### Overview
```
vlm/
├── __init__.py              # Module initialization
├── README.md                # User guide and documentation
├── prompts.py               # VLM prompt templates
├── vlm_backend.py           # Core validation logic
├── utils.py                 # Helper functions
├── batch_validator.py       # Batch processing pipeline
├── validate.py              # User-facing validation script
└── test_updates.py          # Testing utilities
```

### Core Components

#### `prompts.py`
- **Purpose**: Generate prompts for VLM analysis
- **Functions**:
  - `build_prompt()`: Creates comprehensive analysis prompt with event metrics
  - `format_event_metrics()`: Structures data for VLM consumption
- **Features**: 
  - Includes all key metrics (MDRAC, TTC, distance, closing speed, yaw difference)
  - Provides context about interaction type and vehicle types
  - Requests structured classification output

#### `vlm_backend.py`
- **Purpose**: Core validation logic with API-first, local-fallback strategy
- **Functions**:
  - `validate_event()`: Main entry point, handles backend selection and retries
  - `validate_with_gemini()`: Gemini API integration
  - `validate_with_qwen_local()`: Local Qwen model fallback
  - `build_validation_prompt()`: Constructs full validation request
- **Features**:
  - Automatic fallback if API fails or quota exceeded
  - Retry logic with exponential backoff
  - Structured JSON response parsing
  - Error handling and logging

#### `utils.py`
- **Purpose**: Helper utilities for data loading and plot generation
- **Functions**:
  - `load_mdrac_csv()`: Load MDRAC detection results
  - `extract_pair_data()`: Get data for specific vehicle pair
  - `save_combined_plot()`: Generate 2×3 grid with all 5 plots
- **Features**:
  - Trajectory extraction with time windowing
  - Professional plot styling
  - Equal-sized subplots for consistency
  - Efficient image generation

#### `batch_validator.py`
- **Purpose**: Batch processing for multiple pairs
- **Functions**:
  - `validate_pairs_batch()`: Main batch validation entry point
- **Features**:
  - Progress tracking with tqdm
  - Error handling (continues on individual failures)
  - Consolidated CSV output
  - Saves results per pair (JSON + combined plot)

#### `validate.py`
- **Purpose**: User-facing script for running validation
- **Usage**: Edit pairs list and paths, then run
- **Features**: Simple interface for common validation tasks

---

## 4. VLM Backends

### Primary: Gemini API
- **Model**: `gemini-1.5-flash` (fast, cost-effective)
- **Rate Limits**: Free tier allows 1500 requests/day
- **Configuration**: API key via environment variable
- **Benefits**: Fast, high-quality analysis, no local resources needed

### Fallback: Qwen Local Model
- **Model**: `Qwen/Qwen2.5-VL-3B-Instruct` (7.1GB download)
- **Device**: Auto-detection (CPU or CUDA)
- **Benefits**: Offline capability, no API costs, unlimited usage
- **Drawbacks**: Slower on CPU (30-60s per image), requires ~7GB disk space

---

## 5. Validation Output Schema

### JSON Format
```json
{
  "id1": 10520140,
  "id2": 10520195,
  "classification": "confirmed_near_miss",
  "confidence": 85,
  "reasoning": "High MDRAC value (7.31 m/s²) with rapid closure. Distance drops to 4.51m with 4.1 m/s closing speed. Sustained interaction over multiple seconds indicates genuine near-miss event.",
  "backend": "gemini-1.5-flash",
  "MDRAC": 7.31,
  "TTC": 1.10,
  "dist": 4.51
}
```

### Classification Types
- `confirmed_near_miss`: High confidence genuine near-miss
- `likely_near_miss`: Moderate confidence, needs human review
- `uncertain`: Ambiguous case
- `likely_false_positive`: Low confidence, probably not a near-miss
- `false_positive`: High confidence not a near-miss

### Confidence Scores
- 90-100: Very high confidence
- 70-89: High confidence
- 50-69: Moderate confidence (human review recommended)
- 30-49: Low confidence
- 0-29: Very low confidence

---

## 6. Combined Plot Grid

### Layout (2×3)
```
┌─────────────────┬─────────────────┬─────────────────┐
│   Trajectory    │  Distance vs    │ Closing Speed   │
│   (2D spatial)  │     Time        │   vs Time       │
├─────────────────┼─────────────────┼─────────────────┤
│   Velocity      │  Yaw Difference │                 │
│   vs Time       │    vs Time      │     (empty)     │
└─────────────────┴─────────────────┴─────────────────┘
```

### Features
- All 5 plots equal-sized for consistency
- No metrics overlaid on plots (passed separately to VLM)
- Professional styling with consistent color scheme
- Synchronized time axes for temporal analysis
- Clear labeling and legends

### Benefits
- **Token efficiency**: 80% cost reduction vs 5 separate images
- **Context**: VLM sees all plots together for cross-analysis
- **Consistency**: Equal sizing improves VLM interpretation
- **Simplicity**: Single image file per event

---

## 7. Configuration Integration

### config.yaml Updates
```yaml
vlm:
  primary_backend: "gemini"  # "gemini" or "local"
  
  gemini:
    model: "gemini-1.5-flash"
    api_key_env: "GEMINI_API_KEY"
    max_retries: 3
    timeout: 30  # seconds
    rate_limit_delay: 1  # seconds between requests
  
  local:
    model_id: "Qwen/Qwen2.5-VL-3B-Instruct"
    device: "auto"  # auto/cpu/cuda
    torch_dtype: "float32"
  
  confidence_threshold: 70  # Minimum for "confirmed_near_miss"
  top_n_validate: 50        # Number of top events to validate
  save_plots: true
  plot_dpi: 150
```

---

## 8. Usage Examples

### Single Pair Validation
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

### Multiple Pairs Validation
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
    output_dir='results/validation'
)
```

### Output Structure
```
results/validation/
├── validation_results.csv          # All results in one CSV
├── 10520140_10520195/
│   ├── combined_analysis.png       # 2×3 grid
│   └── validation.json             # Detailed result
├── 10520200_10520250/
│   ├── combined_analysis.png
│   └── validation.json
```

---

## 9. Data Reorganization

### Problem
MDRAC results were scattered and inconsistently organized, making batch processing difficult.

### Solution
Implemented structured directory hierarchy for better organization:

**New Structure**:
```
results/
├── brussels/
│   └── mdrac/
│       ├── 01/
│       │   ├── mdrac_01.csv
│       │   └── mdrac_01_postprocessed.csv
│       ├── 02/
│       └── ...
└── oulu/
    └── mdrac/
        └── (similar structure)
```

**Benefits**:
- Region-based separation (Brussels vs Oulu)
- Day-based partitioning for easy access
- Consistent naming convention
- Easy to find and process specific datasets

**Commits**:
- 2026-01-17: Reorganize MDRAC data into structured directories
- 2026-01-18: Remove obsolete files and clean up

---

## 10. Code Quality Improvements

### Utility Functions Added
- **Memory monitoring**: `utils/memory.py` for tracking memory usage
- **I/O helpers**: `utils/io_helpers.py` for file operations
- **Data loader**: Enhanced `utils/data_loader.py` with better error handling

### Refactoring
- Improved code readability with better function naming
- Enhanced docstrings and comments
- Consistent error handling across modules
- Better logging for debugging

---

## 11. Technical Decisions

### Why Combined Plots?
- **Cost**: Single image = 80% cheaper than 5 images
- **Context**: VLM benefits from seeing all plots together
- **Efficiency**: Faster processing, fewer API calls
- **Simplicity**: Easier to manage (1 file vs 5 files per event)

### Why API-First Strategy?
- **Quality**: Gemini provides high-quality analysis
- **Speed**: Fast response times (~2-3 seconds)
- **Scalability**: No local compute requirements
- **Fallback**: Local model ensures offline capability

### Why Structured JSON Output?
- **Parsability**: Easy to process programmatically
- **Consistency**: Standardized schema across all validations
- **Database-ready**: Can be directly inserted into databases
- **Human-readable**: Easy to inspect and review

---

## 12. Performance Metrics

### Processing Times
- **Gemini API**: 2-3 seconds per event (including plot generation)
- **Local Qwen**: 30-60 seconds per event on CPU
- **Plot generation**: ~1 second for combined grid

### Cost Analysis
- **Gemini API**: ~$0.001 per event (free tier: 1500/day)
- **Local Qwen**: $0 (one-time 7GB download)
- **Combined approach**: 80% cost reduction vs separate images

### Validation Throughput
- **With API**: ~20-30 events/minute
- **With local**: ~1-2 events/minute
- **Hybrid**: Automatic fallback ensures continuous operation

---

## 13. Limitations and Future Work

### Current Limitations
1. **API quota**: Free tier limited to 1500 requests/day
2. **Local model speed**: Slow on CPU without GPU
3. **Manual pair specification**: Need to list pairs to validate
4. **No active learning**: Doesn't improve from feedback

### Planned Enhancements (Week 7+)
- [ ] Auto-detect pairs from CSV (no manual specification needed)
- [ ] Simplified prompts for faster processing
- [ ] Configuration-driven validation workflow
- [ ] Integration with IRSM for risk-based prioritization

---

## Files Modified/Created

### New Modules
- `vlm/__init__.py`: Module initialization
- `vlm/README.md`: Comprehensive user guide (328 lines)
- `vlm/prompts.py`: Prompt generation logic
- `vlm/vlm_backend.py`: Core validation engine
- `vlm/utils.py`: Helper utilities
- `vlm/batch_validator.py`: Batch processing pipeline
- `vlm/validate.py`: User-facing script
- `vlm/test_updates.py`: Testing utilities

### Enhanced Utilities
- `utils/memory.py`: **NEW** - Memory monitoring
- `utils/io_helpers.py`: **NEW** - I/O operations
- `utils/data_loader.py`: Enhanced with better error handling

### Configuration
- `config.yaml`: Added VLM configuration section
- `.env`: Environment variable template for API key

### Documentation
- `vlm/README.md`: Complete usage guide
- `docs/progress/week6.md`: This file

---

## Commit History (Week 6)

- **2026-01-19**: feat: Implement VLM Near-Miss Validation System
- **2026-01-18**: Remove obsolete MDRAC CSV and plots, add utility functions
- **2026-01-17**: Refactor: Reorganize MDRAC data into structured directories

---

## Summary Metrics

### Week 6 Achievements
- **1 new module**: Complete VLM validation system
- **8 new files**: Well-structured, modular architecture
- **80% cost reduction**: Combined plot approach
- **~500 lines of code**: Validation logic + utilities
- **Dual backend support**: API + local fallback

### Documentation
- **328-line README**: Comprehensive user guide
- **Code comments**: Detailed docstrings throughout
- **Usage examples**: Multiple workflow examples

### Impact
- **Validation speed**: 10x faster than manual review
- **Consistency**: Standardized criteria across all events
- **Scalability**: Can process hundreds of events per day
- **Flexibility**: Works both online (API) and offline (local)

---

## References

### VLM Technology
- Gemini API: Google's generative AI platform
- Qwen-VL: Open-source vision-language model
- Vision-Language Models: State-of-the-art multimodal AI

### Implementation
- Combined plot generation: Custom matplotlib implementation
- API integration: google-genai and google-generativeai packages
- Local inference: transformers + torch + qwen-vl-utils

---

**Next Steps**: Week 7 will focus on streamlining the VLM workflow with auto-detection and simplified prompts.
