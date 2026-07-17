# Supervised IRSM Tuning Report

Last updated on: 2026-07-17

This file summarizes the current supervised IRSM tuning state from the saved repository artifacts.

## Current Saved Metrics

From `irsm/models/saved/metrics.json`:

| Model | Validation AUC | Validation Threshold | Test AUC | Test Precision | Test Recall | Test F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Random Forest | 0.739 | 0.020 | 0.863 | 0.500 | 0.429 | 0.462 |
| XGBoost | 0.733 | 0.010 | 0.708 | 0.200 | 0.143 | 0.167 |
| Neural Network | 0.708 | 0.030 | 0.869 | 1.000 | 0.286 | 0.444 |

## Current Interpretation

- Random Forest is the most practical supervised path in this checkout.
- XGBoost remains available but is currently weaker on the saved test split.
- Neural Network has a strong AUC but remains experimental because it is less interpretable and less stable for operational use.

## Practical Guidance

Prefer supervised IRSM when you need:

- ranked probabilities instead of raw anomaly scores
- comparisons against the Brussels labels
- an interpretable ranking layer that can later be fused with M-DRAC and anomaly signals

The current engineering default should be the Random Forest path.
