# Supervised Near-Miss Detection Tuning Report

Based on probability calibration, validation-selected thresholds, and SMOTE resampling strategy ablation.

## 1. SMOTE Strategy Ablation Results

### Model: RANDOM_FOREST
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.100 | 0.888 | 0.020 |
| smote_gold_only | 0.100 | 0.814 | 0.040 |
| smote_hybrid | 0.100 | 0.898 | 0.020 |

### Model: XGBOOST
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.100 | 0.835 | 0.010 |
| smote_gold_only | 0.100 | 0.851 | 0.050 |
| smote_hybrid | 0.086 | 0.842 | 0.030 |

### Model: NEURAL_NETWORK
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.086 | 0.823 | 0.190 |
| smote_gold_only | 0.086 | 0.829 | 0.080 |
| smote_hybrid | 0.086 | 0.842 | 0.060 |

## 2. Final Selected Model Configurations

### RANDOM_FOREST
- **SMOTE Strategy**: SMOTE_HYBRID
- **Val AUC**: 0.898
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.020
- **Test AUC**: 0.666
- **Test Precision**: 0.300
- **Test Recall**: 0.429

### XGBOOST
- **SMOTE Strategy**: SMOTE_GOLD_ONLY
- **Val AUC**: 0.851
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.050
- **Test AUC**: 0.596
- **Test Precision**: 0.200
- **Test Recall**: 0.286

### NEURAL_NETWORK
- **SMOTE Strategy**: SMOTE_HYBRID
- **Val AUC**: 0.842
- **Val Precision@10**: 0.086
- **Operating Threshold**: 0.060
- **Test AUC**: 0.705
- **Test Precision**: 0.125
- **Test Recall**: 0.143
