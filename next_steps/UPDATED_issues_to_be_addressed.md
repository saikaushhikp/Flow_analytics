# Known Issues and Blockers

This file lists issues found by going through the entire current codebase and running lightweight checks  

Documented on 2026-05-21

## Resolution Status as of 2026-05-27

Active Brussels + M-DRAC + IRSM stabilization blockers have been addressed:

- Hardcoded active Brussels and IRSM paths were replaced with repository-relative defaults, environment-variable defaults, and CLI overrides.
- `utils.load_data()` was restored in `utils/data_loader.py` and verified against local Brussels parquet data.
- `utils/io_helpers.load_detection_results()` now reads CSV files with `pd.read_csv()`.
- Brussels lane and crosswalk scripts now run with local `data/`, bounded smoke windows, configurable output roots, and schema-valid CSV output.
- SPF production use, Oulu, VLM validation, and supervised IRSM remain deferred by project decision.
- Full-day Brussels lane processing remains a scaling/performance issue because large windows can exhaust memory; the stabilized runnable workflow is the bounded hourly smoke window documented in `UPDATED_milestone_execution_status.md` and `UPDATED_brussels_validation_summary.md`.

## Environment Blockers

1. Many scripts hardcode `/home/ubuntu/prem`.
   - Examples: region scripts, IRSM scripts, VLM scripts.
   - Need to be fixed

## Immediate Import/Runtime Breakages

1. `utils/__init__.py` imports a missing `utils/data_loader.py`.
   - Region scripts call `from utils import ... load_data`.
   - `utils/data_loader.py` is not present.
   - `plotter.py` contains a `load_data()` function, but it is not exposed through `utils`.

2. `utils/io_helpers.py` loads CSV files with `pd.read_parquet()`.
   - `load_detection_results()` checks `filepath.suffix == '.csv'` and then calls `pd.read_parquet(filepath)`.
   - It should have used the call `pd.read_csv(filepath)`.


3. `irsm/__init__.py` exports missing or renamed functions/files.
   - References `irsm.data_generation.generate_risk_vectors`; `irsm/data_generation.py` is absent.
   - References `extract_risk_vector_instantaneous` and `get_feature_names_instantaneous`; these are absent from `irsm/risk_vector.py`.

4. [x]   
   - **The _SPF_ has been intended to be keep aside or deprecate till further notice**  
   `ssm/spf.py` expects a config shape that does not match `config.yaml`.
   - Code expects `config['spf']['objective']`, `subjective`, `thresholds`, `min_risk`, `composite_method`.
   - Current `config.yaml` has flat SPF keys like `beta_p`, `beta_t`, `t_star`, `min_spf`, `severity`.
   - Result: `SafetyPotentialField(config)` will fail with `KeyError`.



5. [x]   
   - **The _VLM_ has been intended to be kept aside or deprecate right now till further notice**  
   `vlm/batch_validator.py` references `save_interval` that is no longer in the function signature.
   - `validate_pairs_batch()` signature has no `save_interval`.
   - Later code executes `if idx % save_interval == 0:`.
   - Result: first successful pair reaches `NameError`.

6. [x]   
   - **The _VLM_ has been intended to be kept aside or deprecate right now till further notice**   
   `vlm/vlm_backend.py` uses `from prompts import build_prompt`.
   - In package context this should be `from vlm.prompts import build_prompt` or a relative import.
   - Current import may fail depending on working directory.

7. [x] `utils/irsm_preprocessing.py` imports `get_crosswalk_zones` from `regions.oulu.zones`.
   - **The scope for `Oulu` region has been intended to be kept aside or deprecate right now till further notice**   
   - Oulu zones only define `get_crosswalk_zone()` singular.
   - Oulu IRSM preprocessing will fail.

## Pipeline and Code Drift

1.  `filters/postprocessing/__init__.py` documents a duration filter, but no duration filter exists.
   - Historical docs also reference `filters/postprocessing/duration_filter.py`.

2. `docs/progress/week4.md` references `ssm/conflict_detection.py`; that file is absent.

3. `irsm/README.md` and progress docs reference missing files:
   - `irsm/data_generation.py`
   - `irsm/create_supervised_dataset.py`

4. `config.yaml` and docs are not synchronized for SPF(**since we intend to keep it aside or deprecate it, leaving it UNTOUCHED**) and some label descriptions.
   - The code comments and README label tables disagree in places.

5. `get_threshold_for_labels()` in `ssm/utils.py` references `config['mdrac']['threshold']`, which is absent.
   - This appears unused.

6. [x]  
   - **The scope for `Oulu` region has been intended to be kept aside or deprecate right now till further notice**
   - `regions/oulu/crosswalk_main.py` is duplicated inside the same file.
   - After the final summary, the script starts another copy of the same workflow.
   - It also still uses the old label-spoofing workaround.
   - Brussels crosswalk already uses the cleaner `skip_label_filter=True` pattern.

7. [x]
   - **The scope for `Oulu` region has been intended to be kept aside or deprecate right now till further notice**
   - Oulu crosswalk outputs include `label1,label2`, while Brussels crosswalk outputs do not.
   - This indicates outputs came from different code generations.
   - Oulu `interaction` values can remain `car_v_car` even after label restoration because the formatted `interaction` string is computed before restoration.

8. [x]
   - **The scope for `Oulu` region has been intended to be keep aside or deprecate right now till further notice**
   - Oulu lane default arguments cover a date range but save under `START_DATE`.
   - `regions/oulu/lane_main.py` defaults to `2025-08-22` through `2025-09-11`.
   - Output path uses only `START_DATE`.
   - The current `results/oulu/lanes/2025-08-22/mdrac_2025-08-22.csv` contains timestamps from 2025-09-09, confirming this mislabeling risk.
