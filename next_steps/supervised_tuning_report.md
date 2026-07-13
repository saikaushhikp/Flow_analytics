# Supervised Near-Miss Detection Tuning Report

Based on probability calibration, validation-selected thresholds, and SMOTE resampling strategy ablation.

## 1. SMOTE Strategy Ablation Results

### Model: RANDOM_FOREST
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.100 | 0.730 | 0.010 |
| smote_gold_only | 0.100 | 0.739 | 0.020 |
| smote_hybrid | 0.086 | 0.739 | 0.010 |

### Model: XGBOOST
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.100 | 0.733 | 0.010 |
| smote_gold_only | 0.100 | 0.730 | 0.030 |
| smote_hybrid | 0.071 | 0.702 | 0.020 |

### Model: NEURAL_NETWORK
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.100 | 0.708 | 0.030 |
| smote_gold_only | 0.086 | 0.705 | 0.010 |
| smote_hybrid | 0.071 | 0.677 | 0.020 |

## 2. Final Selected Model Configurations

### RANDOM_FOREST
- **SMOTE Strategy**: SMOTE_GOLD_ONLY
- **Val AUC**: 0.739
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.020
- **Test AUC**: 0.863
- **Test Precision**: 0.500
- **Test Recall**: 0.429

### XGBOOST
- **SMOTE Strategy**: NO_SMOTE
- **Val AUC**: 0.733
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.010
- **Test AUC**: 0.708
- **Test Precision**: 0.200
- **Test Recall**: 0.143

### NEURAL_NETWORK
- **SMOTE Strategy**: NO_SMOTE
- **Val AUC**: 0.708
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.030
- **Test AUC**: 0.869
- **Test Precision**: 1.000
- **Test Recall**: 0.286
