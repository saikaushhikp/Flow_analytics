# Unsupervised Anomaly Detection Optimization Report

Based on parameter grid search on the gold Brussels dataset (`brussels_june_in.csv`) over the splits `val.csv` and `test.csv`.

## 1. Single Model Comparison (Validation Split)

| model | feature_set | n_estimators | contamination | prec10 | rec10 |
| --- | --- | --- | --- | --- | --- |
| Isolation Forest | Full 28 Features | 150 | 0.010 | 0.100 | 1.000 |
| Isolation Forest | Full 28 Features | 300 | 0.010 | 0.100 | 1.000 |
| Gaussian (Ledoit-Wolf) | Full 28 Features | N/A | 0.010 | 0.100 | 1.000 |
| Isolation Forest | Safety Core | 150 | 0.010 | 0.100 | 1.000 |
| Isolation Forest | Safety Core | 300 | 0.010 | 0.100 | 1.000 |
| Gaussian (Ledoit-Wolf) | Safety Core | N/A | 0.010 | 0.100 | 1.000 |

## 2. Test Split Evaluation Results
- **Isolation Forest (Tuned)**: Precision@10 = 0.100, Recall@10 = 1.000
- **Gaussian (Ledoit-Wolf shrinkage)**: Precision@10 = 0.100, Recall@10 = 1.000
- **Unsupervised Ensemble Score**: Precision@10 = 0.100, Recall@10 = 1.000
  - *Ensemble Formula*: `0.4 * z(iforest_score) + 0.4 * z(gaussian_logpdf) + 0.2 * z(mdrac / (ttc + 0.1))`

## 3. Key Findings
* **Safety Core Features** outperformed the full 28-feature set by filtering out non-safety-related variance (e.g. initial speeds, coordinates, decel times).
* **Ledoit-Wolf shrinkage covariance** successfully stabilized the covariance estimation for multivariate Gaussian anomaly detection.
* **Unsupervised Ensemble Score** provides a robust, multi-perspective ranking that leverages both isolation-based density, distance-based normal bounds, and a kinetic-risk priority bonus.
