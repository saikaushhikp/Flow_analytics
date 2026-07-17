# IRSM: Interaction Risk Space Modeling

Last updated on: 2026-07-17

IRSM is the learning-based track in this repository. It converts pairwise traffic interactions into feature vectors, then ranks or classifies those interactions as potential near-misses.

The active implementation is Brussels lane focused.

## What IRSM Does

IRSM keeps both normal and risky interactions instead of thresholding everything up front. The workflow is:

1. load Brussels parquet data
2. apply the shared preprocessing stack
3. assign lane zones
4. generate nearby same-lane pairs
5. extract one feature vector per pair at the peak averaged M-DRAC moment
6. score the pairs with unsupervised or supervised models

The current feature space is 28 columns and includes:

- core surrogate signals: `mdrac`, `ttc`, `closing_speed`, `closing_accel`, `yaw_diff`
- safe-distance and trajectory projections
- learned environmental surrogates
- follower braking-response features over a short future window

## Primary Entry Points

Generate lane risk vectors:

```bash
python irsm/data_generation.py --date 2025-06-01 --start-time 00 --max-hours 22
```

Run unsupervised detection:

```bash
python irsm/models/isolation_forest.py
python irsm/models/gaussian_anomaly.py
```

Train supervised models:

```bash
python irsm/models/supervised.py --train
```

Run supervised inference on the configured day:

```bash
python irsm/supervised_detect.py
```

Compare M-DRAC and IRSM for one date:

```bash
python irsm/compare_mdrac_irsm.py --date 2025-06-01
```

Plot risk space or pair trajectories:

```bash
python irsm/visualize_risk.py
python irsm/irsm_plotter.py
```

## Inputs and Outputs

Input parquet data is loaded from `FLOW_ANALYTICS_DATA_BRUSSELS` or the repository-local `data/` folder.

Generated lane vectors:

```text
irsm/data/brussels/{date}/lanes.csv
```

Unsupervised outputs:

```text
irsm/results/brussels/{date}/lanes_detections.csv
irsm/results/brussels/{date}/gaussian_results.csv
irsm/results/brussels/{date}/gaussian_detections.csv
irsm/results/brussels/{date}/gaussian_distributions.png
irsm/results/brussels/{date}/visualizations/risk_space_2d_projections.png
```

Supervised outputs:

```text
irsm/results/brussels/{date}/random_forest.csv
irsm/results/brussels/{date}/xgboost.csv
irsm/results/brussels/{date}/neural_network.csv
irsm/models/saved/metrics.json
```

## Current Model Notes

### Isolation Forest

- active unsupervised baseline
- reads the configured feature set from `irsm/irsm_config.yaml`
- deduplicates repeated anomaly rows by `pair_id`
- writes `lanes_detections.csv`

### Gaussian Anomaly

- multivariate Gaussian scoring with covariance stabilization
- useful as a second unsupervised view and for supporting plots

### Random Forest and XGBoost

- current primary supervised models
- trained from Brussels labels aligned from `brussels_june_in.csv`
- intended for calibrated ranking of likely near-miss pairs

### Neural Network

- still available
- remains experimental relative to the tree-based path

## Current Saved Metrics

From `irsm/models/saved/metrics.json`:

| Model | Test AUC | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Random Forest | 0.863 | 0.500 | 0.429 | 0.462 |
| XGBoost | 0.708 | 0.200 | 0.143 | 0.167 |
| Neural Network | 0.869 | 1.000 | 0.286 | 0.444 |

Operationally, the repository should currently be read as favoring the Random Forest path because it is easier to reason about and less brittle than the neural model.

## Alternative Methods

Experimental alternatives are documented separately:

- [meta_ensemble](alternative_methods/meta_ensemble/README.md)
- [temporal_sequence](alternative_methods/temporal_sequence/README.md)
- [surrogate_fusion](alternative_methods/surrogate_fusion/README.md)

These are useful for benchmarking and idea staging, but they are not the default production path in this checkout.

## Known Caveats

- `irsm/supervised_detect.py` still uses module-level configuration instead of CLI arguments.
- `irsm/canonical_utils.py` currently returns canonical output paths without writing files because the save call is commented out.
- Bounded Brussels windows are the reproducible operating mode; full-day scaling is still an open performance problem.
- The repo contains historical metrics and reports from multiple iterations. Prefer current code, current saved metrics, and `next_steps/current_state.md` over older notes.
