# Supervised Near-Miss Detection Tuning Report

Based on probability calibration, validation-selected thresholds, and SMOTE resampling strategy ablation.

## 1. SMOTE Strategy Ablation Results

### Model: RANDOM_FOREST
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.100 | 0.879 | 0.010 |
| smote_gold_only | 0.086 | 0.814 | 0.010 |
| smote_hybrid | 0.086 | 0.848 | 0.020 |

### Model: XGBOOST
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.100 | 0.857 | 0.010 |
| smote_gold_only | 0.100 | 0.835 | 0.010 |
| smote_hybrid | 0.086 | 0.863 | 0.040 |

### Model: NEURAL_NETWORK
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.086 | 0.419 | 0.180 |
| smote_gold_only | 0.100 | 0.876 | 0.020 |
| smote_hybrid | 0.086 | 0.860 | 0.090 |

## 2. Final Selected Model Configurations

### RANDOM_FOREST
- **SMOTE Strategy**: NO_SMOTE
- **Val AUC**: 0.879
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.010
- **Test AUC**: 0.632
- **Test Precision**: 0.500
- **Test Recall**: 0.143

### XGBOOST
- **SMOTE Strategy**: NO_SMOTE
- **Val AUC**: 0.857
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.010
- **Test AUC**: 0.596
- **Test Precision**: 0.000
- **Test Recall**: 0.000

### NEURAL_NETWORK
- **SMOTE Strategy**: SMOTE_GOLD_ONLY
- **Val AUC**: 0.876
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.020
- **Test AUC**: 0.769
- **Test Precision**: 0.267
- **Test Recall**: 0.571
