# Meta-Ensemble Ranker

This alternative method implements a **Meta-Ensemble Ranker** that aggregates inputs from multiple underlying models to produce one final consolidated near-miss confidence score.

## Inputs
- **M-DRAC Composite Score**: Calculated dynamically as `mdrac * (1.0 / (ttc + 0.1))`
- **Isolation Forest Score**: Z-normalized anomaly score (unsupervised)
- **Gaussian Anomaly Score**: Z-normalized log-probability (unsupervised, Ledoit-Wolf)
- **Random Forest Probability**: Calibrated prediction probability (supervised)
- **XGBoost Probability**: Calibrated prediction probability (supervised)

## Model
The meta-ensemble uses a **Logistic Regression** model trained on the gold-standard labeled data points (excluding the weak self-trained labels to prevent prediction bias).

## Structure
- `meta_ensemble.py`: Script to generate features, fit the logistic regression model, evaluate predictions, and save metrics.
- `results/`: Contains the saved models, scaler, and evaluated performance metrics.
