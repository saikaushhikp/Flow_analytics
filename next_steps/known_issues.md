# Known Issues and Blockers

This file lists issues found by reading the current checkout and running lightweight syntax/import checks on 2026-05-21.

## Environment Blockers

1. The intended conda env `flow_env` is not installed locally.
   - `conda env list` shows only `base` and `ml-env`.
   - `conda run -n flow_env ...` fails.
   - Active `base` lacks packages such as `numpy` and `psutil`.

2. Many scripts hardcode `/home/ubuntu/prem`.
   - Current checkout is `/home/kaushik/Kezual/Flow_analytics`.
   - Examples: region scripts, IRSM scripts, VLM scripts.
   - This blocks local execution unless paths are patched or symlinked.

## Immediate Import/Runtime Breakages

1. `utils/__init__.py` imports a missing `utils/data_loader.py`.
   - Region scripts call `from utils import ... load_data`.
   - `utils/data_loader.py` is not present.
   - `plotter.py` contains a `load_data()` function, but it is not exposed through `utils`.

2. `utils/io_helpers.py` loads CSV files with `pd.read_parquet()`.
   - `load_detection_results()` checks `filepath.suffix == '.csv'` and then calls `pd.read_parquet(filepath)`.
   - It should call `pd.read_csv(filepath)`.

3. `ssm/spf.py` expects a config shape that does not match `config.yaml`.
   - Code expects `config['spf']['objective']`, `subjective`, `thresholds`, `min_risk`, `composite_method`.
   - Current `config.yaml` has flat SPF keys like `beta_p`, `beta_t`, `t_star`, `min_spf`, `severity`.
   - Result: `SafetyPotentialField(config)` will fail with `KeyError`.

4. `vlm/batch_validator.py` references `save_interval` that is no longer in the function signature.
   - `validate_pairs_batch()` signature has no `save_interval`.
   - Later code executes `if idx % save_interval == 0:`.
   - Result: first successful pair reaches `NameError`.

5. `vlm/vlm_backend.py` uses `from prompts import build_prompt`.
   - In package context this should be `from vlm.prompts import build_prompt` or a relative import.
   - Current import may fail depending on working directory.

6. `utils/irsm_preprocessing.py` imports `get_crosswalk_zones` from `regions.oulu.zones`.
   - Oulu zones only define `get_crosswalk_zone()` singular.
   - Oulu IRSM preprocessing will fail.

7. `irsm/__init__.py` lazily exports missing or renamed functions/files.
   - References `irsm.data_generation.generate_risk_vectors`; `irsm/data_generation.py` is absent.
   - References `extract_risk_vector_instantaneous` and `get_feature_names_instantaneous`; these are absent from `irsm/risk_vector.py`.

## Pipeline and Code Drift

1. `regions/oulu/crosswalk_main.py` is duplicated inside the same file.
   - After the final summary, the script starts another copy of the same workflow.
   - It also still uses the old label-spoofing workaround.
   - Brussels crosswalk already uses the cleaner `skip_label_filter=True` pattern.

2. Oulu crosswalk outputs include `label1,label2`, while Brussels crosswalk outputs do not.
   - This indicates outputs came from different code generations.
   - Oulu `interaction` values can remain `car_v_car` even after label restoration because the formatted `interaction` string is computed before restoration.

3. Oulu lane default arguments cover a date range but save under `START_DATE`.
   - `regions/oulu/lane_main.py` defaults to `2025-08-22` through `2025-09-11`.
   - Output path uses only `START_DATE`.
   - The current `results/oulu/lanes/2025-08-22/mdrac_2025-08-22.csv` contains timestamps from 2025-09-09, confirming this mislabeling risk.

4. `filters/postprocessing/__init__.py` documents a duration filter, but no duration filter exists.
   - Historical docs also reference `filters/postprocessing/duration_filter.py`.

5. `docs/progress/week4.md` references `ssm/conflict_detection.py`; that file is absent.

6. `irsm/README.md` and progress docs reference missing files:
   - `irsm/data_generation.py`
   - `irsm/create_supervised_dataset.py`
   - trained model files under `irsm/models/saved/`

7. `config.yaml` and docs are not synchronized for SPF and some label descriptions.
   - The code comments and README label tables disagree in places.

8. `get_threshold_for_labels()` in `ssm/utils.py` references `config['mdrac']['threshold']`, which is absent.
   - This appears unused, but it is a latent bug.

## Data and Result Concerns

1. Results are generated artifacts, not a reproducibility guarantee.
   - Because code has drifted, rerunning may not reproduce existing CSVs.

2. Oulu result coverage is uneven.
   - Many crosswalk days exist, fewer lane days exist.
   - Some results may have been produced by duplicated or older scripts.

3. Brussels result coverage is partial.
   - Lane CSVs exist for 2025-06-01 through 2025-06-14.
   - Crosswalk CSVs exist for several June dates but not every day in that range.

4. No automated test suite is present.
   - There are embedded examples and notebook validations, but no pytest/unit test structure.

## Documentation Drift

The historical docs repeatedly say "production ready", but the current checkout has enough broken references that it should be treated as "prototype with usable pieces" until the stabilization plan is completed.

Source-of-truth priority should be:

1. Current code that imports and runs.
2. Current `config.yaml`.
3. Current result CSVs, with caveats.
4. Historical docs for intent and rationale only.

