# Meta-Ensemble Ranker

Last updated on: 2026-07-17

This experiment stacks multiple detector outputs into one final ranking score.

## Inputs

- composite M-DRAC severity
- Isolation Forest anomaly score
- Gaussian anomaly score
- Random Forest probability
- XGBoost probability

The current implementation trains a logistic-regression ranker on gold-labeled Brussels pairs.

## Run

```bash
python irsm/alternative_methods/meta_ensemble/meta_ensemble.py
```

## Current Result

From `results/evaluation_metrics.json`:

- validation AUC: `0.739`
- validation Precision@10: `0.100`
- test AUC: `0.571`
- test Precision@10: `0.100`

## Interpretation

This method is useful as a fusion baseline, but it is not currently strong enough to replace the main Random Forest supervised path.

The learned coefficients suggest the supervised probabilities carry most of the signal, especially XGBoost and Random Forest, while the unsupervised scores contribute less cleanly.
