# Supervised Near-Miss Detection Tuning Report

Based on probability calibration, validation-selected thresholds, and SMOTE resampling strategy ablation.

## 1. SMOTE Strategy Ablation Results

### Model: RANDOM_FOREST
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.100 | 0.742 | 0.030 |
| smote_gold_only | 0.100 | 0.711 | 0.020 |
| smote_hybrid | 0.100 | 0.798 | 0.020 |

### Model: XGBOOST
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.071 | 0.776 | 0.020 |
| smote_gold_only | 0.100 | 0.758 | 0.070 |
| smote_hybrid | 0.100 | 0.786 | 0.010 |

### Model: NEURAL_NETWORK
| Strategy | Val Precision@10 | Val AUC | Threshold |
| --- | --- | --- | --- |
| no_smote | 0.100 | 0.727 | 0.030 |
| smote_gold_only | 0.043 | 0.742 | 0.020 |
| smote_hybrid | 0.071 | 0.727 | 0.030 |

## 2. Final Selected Model Configurations

### RANDOM_FOREST
- **SMOTE Strategy**: SMOTE_HYBRID
- **Val AUC**: 0.798
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.020
- **Test AUC**: 0.778
- **Test Precision**: 0.375
- **Test Recall**: 0.429

### XGBOOST
- **SMOTE Strategy**: SMOTE_HYBRID
- **Val AUC**: 0.786
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.010
- **Test AUC**: 0.720
- **Test Precision**: 0.375
- **Test Recall**: 0.429

### NEURAL_NETWORK
- **SMOTE Strategy**: NO_SMOTE
- **Val AUC**: 0.727
- **Val Precision@10**: 0.100
- **Operating Threshold**: 0.030
- **Test AUC**: 0.805
- **Test Precision**: 0.000
- **Test Recall**: 0.000
