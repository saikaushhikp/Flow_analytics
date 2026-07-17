# Temporal Summary Classifier

Last updated on: 2026-07-17

This experiment converts short interaction windows into summary statistics instead of training a full sequence network.

## Method

For each candidate pair, the pipeline extracts a short time window around peak risk and summarizes:

- minimum / mean / standard deviation of distance
- maximum / mean / standard deviation of closing speed
- minimum / mean braking features
- yaw-difference aggregates
- braking-response counts

The current implementation trains a Random Forest on those temporal summaries.

## Run

```bash
python irsm/alternative_methods/temporal_sequence/temporal_classifier.py
```

## Current Result

From `results/evaluation_metrics.json`:

- validation AUC: `0.766`
- validation F1: `0.250`
- test AUC: `0.742`
- test F1: `0.000`

Top current feature importance:

- `closing_speed_max`
- `decel_min`
- `dist_min`

## Interpretation

The method preserves some ranking signal, but the current thresholded classification behavior is weak on test. It remains a good bridge experiment between tabular IRSM and future sequence or graph models, not the current deployment path.
