# Implementation Plan

This is the recommended order for taking the work forward. The first milestone should be "make the current repository runnable and reproducible", not new model work.

Documented on 2026-05-25

## Milestone 1: Stabilize Runtime and Imports

Goal: one-command imports and one-day smoke runs should work locally.

Tasks:

1. [**DONE**]  
   ~~Create the project environment.~~
   ~~- Use `environment.yaml` as the baseline.~~
   ~~- Install any missing packages discovered during import.~~
   ~~- Confirm `python -c "import numpy, pandas, geopandas, shapely, yaml, psutil"` works.~~

2. Remove hardcoded `/home/ubuntu/prem` assumptions.
   - Use repository-relative paths or environment variables.
   - Good defaults:
     - `FLOW_ANALYTICS_ROOT`
     - `FLOW_ANALYTICS_DATA_BRUSSELS`
     - `FLOW_ANALYTICS_OUTPUT_ROOT`
   - Keep CLI overrides for data/output paths.

3. Restore/fix `utils.load_data`.
   - Create `utils/data_loader.py` or move `plotter.load_data()` into `utils`.
   - Must support:
     - Brussels hourly/folder parquet layout.
     - Start/end date range.
     - Optional dtype casting from config.
   - Update `utils/__init__.py` only after implementation.

4. Fix `utils/io_helpers.load_detection_results()`.
   - `.csv` must use `pd.read_csv`.
   - Add a tiny smoke test using an in-memory temporary CSV.

5. Run import checks:

```bash
python -c "import utils; import ssm.utils; from ssm.m_drac import ModifiedDRAC"
python -c "from regions.brussels import zones; print(len(zones.get_lane_zones()))"
python -c "from vlm.batch_validator import validate_pairs_batch"
```

## Milestone 2: Repair Operational M-DRAC Scripts

Goal: run one Brussels lane day, one Brussels crosswalk day, ~~one Oulu lane day, and one Oulu crosswalk day.~~

Tasks:

1. Make Brussels scripts path-configurable.
   - `regions/brussels/lane_main.py`
   - `regions/brussels/crosswalk_main.py`


2. [**DECIDED TO BE DEPRECATED/LEFT ASIDE UNTOUCHED**]  
~~Port Brussels crosswalk cleanup to Oulu.~~
   ~~- Remove duplicated code from `regions/oulu/crosswalk_main.py`.~~
   ~~- Remove label spoofing.~~
   ~~- Use:~~
~~detector = ModifiedDRAC(config, zone_type='crosswalks')~~
~~crosswalk_conflicts = detector.detect(~~
~~crosswalk_pairs,~~
 ~~is_pairs_data=True,~~
  ~~skip_label_filter=True,~~
~~)~~

3. [**DECIDED TO BE DEPRECATED/LEFT ASIDE UNTOUCHED**]  
~~Fix Oulu lane default behavior.~~
   ~~- Default should be a single day, or output filename should reflect the full date range.~~
   ~~- Batch scripts already pass one day at a time; keep that flow.~~

4. Add a smoke-run mode.
   - Example: `--max-hours 1` or `--sample-limit`.
   - Useful for testing without loading a full day.

5. Add minimal output-schema assertions.
   - Required columns: `timestamp,id1,id2,zone,interaction,leader,dist,TTC,MDRAC,closing_speed,speed_diff,yaw_diff,link`.

## Milestone 3: Make SPF ~~Either Runnable or~~ **Clearly Experimental**

Goal: remove ambiguity

Choose one:

~~1. Fix SPF config to match `ssm/spf.py`.~~
   ~~- Add nested `spf.objective`, `spf.subjective`, `spf.thresholds`, `spf.min_risk`, `spf.composite_method`.~~
   ~~- Validate `SafetyPotentialField(config)` initializes.~~

2. explicitly mark SPF as experimental-disabled.
   - Update README/config docs.
   - Keep code but do not present it as runnable.

Recommendation: mark SPF as experimental-disabled for now. M-DRAC and IRSM need attention first.

## Milestone 4: ~~Repair~~ VLM Validation[**VLM VALIDATION HAS BEEN DECIDED TO BE DEPRECATED/LEFT ASIDE UNTOUCHED**]

~~Goal: validate a small existing MDRAC CSV without crashing.~~

~~Tasks:~~

~~1. Fix imports in `vlm/vlm_backend.py`.~~
   ~~- Replace `from prompts import build_prompt` with package-safe import.~~

~~2. Fix `validate_pairs_batch()`.~~
   ~~- Either restore `save_interval` parameter with a default or remove checkpoint code fully.~~
  ~~ - Make auto-detected pairs unique, not one pair per row if duplicates exist.~~

~~3. Make VLM data loading date-aware.~~
   ~~- Current `vlm/validate.py` assumes Brussels June day format via `2025-06-{day}`.~~
   ~~- Generalize to actual dates in CSV timestamps.~~

~~4. Add no-API dry run.~~
   ~~- Generate plots and parse a fake response without calling Gemini/Qwen.~~

## Milestone 5: Restore IRSM Pipeline

Goal: generate `irsm/data/{region}/{date}/lanes.csv` from trajectory data and run unsupervised detectors.

Tasks:

1. ~~Decide whether to restore~~ or rewrite `irsm/data_generation.py`.
   - Current docs depend on it, but it is absent.
   - It should load data, apply preprocessing, assign lane zones, generate pairs, extract risk vectors, and save `lanes.csv`.

2. Fix IRSM package exports.
   - Remove missing lazy exports or implement the missing functions.

3. [**OULU REGION HAS BEEN DECIDED TO BE DEPRECATED/LEFT ASIDE UNTOUCHED**]  
   ~~Fix Oulu preprocessing import.~~
   ~~- Use `get_crosswalk_zone()` for Oulu or wrap it as a list.~~

4. Keep supervised models out of production until retrained.
   - Existing docs already note supervised models over-predict due to train/test distribution mismatch.
   - Use Isolation Forest/Gaussian first.

5. Add comparison report.
   - Compare MDRAC detections and IRSM anomalies for the same day.
   - Manually inspect top cases.

## Milestone 6: Testing and Reproducibility

Add a small automated test suite before scaling.

Suggested tests:

- Config loads and has required keys for active subsystems.
- `utils.load_data()` handles a mocked folder structure.
- `save_detection_results()` and `load_detection_results()` round-trip CSV.
- `get_mdrac_pairs()` works on a tiny synthetic same-lane fixture.
- `ModifiedDRAC.detect()` works with pre-filtered pairs and `skip_label_filter=True`.  
- [**DECIDED TO BE DEPRECATED/LEFT ASIDE UNTOUCHED**]~~VLM response parser handles expected structured responses.~~
- Region zone functions return valid WKT polygons.

## Milestone 7: Reprocess and Validate Results

Only after the above:

1. [**DONE FOR BOUNDED LOCAL WINDOW**] Re-run Brussels lanes and crosswalks for a small verified window.
   - Completed for `2025-06-01` through `2025-06-07` with `--max-hours 1`.
   - Outputs: `results/mdrac/brussels/`.
   - Logs: `results/mdrac/brussels/smoke_logs/`.
   - Summary: `next_steps/UPDATED_brussels_validation_summary.md`.
2. [**OULU REGION HAS BEEN DECIDED TO BE DEPRECATED/LEFT ASIDE UNTOUCHED**]  
   ~~Re-run Oulu lanes and crosswalks after fixing Oulu scripts.~~
3. [**DONE FOR IRSM SELECTED DETECTIONS**] Regenerate plots only for selected detections.
4. [**VLM VALIDATION HAS BEEN DECIDED TO BE DEPRECATED/LEFT ASIDE UNTOUCHED**]  ~~Run VLM validation on top-risk events if API key/model is available.~~
5. [**DONE FOR ACTIVE REGION ONLY**] Produce a cross-region summary:
   - detections per day
   - detections per zone
   - severity/MDRAC distribution
   - false-positive notes from manual review
   - Since Oulu is deferred, the active summary is Brussels-only.

## Definition of Done for Stabilization

- Environment setup command works on a clean machine.
- All imports pass.
- One-day Brussels lane and crosswalk scripts run.
- Outputs have consistent schema.
- Existing known issues are either fixed or explicitly documented as deferred.
- README reflects the current runnable workflows, not historical ambitions.
