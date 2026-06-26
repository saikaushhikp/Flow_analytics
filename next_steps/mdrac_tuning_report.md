# M-DRAC Parameter Optimization Tuning Report

Based on parameter grid search on the gold Brussels dataset (`brussels_june_in.csv`) over the first 24 hours.

## 1. Lanes Parameters (Vehicle-Vehicle longitudinal conflicts)
- **Best Precision@10**: 0.000
- **Best Recall@10**: 0.000
- **Optimized Parameters**:
  - `min_mdrac`: 3.4
  - `max_ttc`: 1.0
  - `min_speed_diff`: 0.5
  - `max_lateral_distance`: 1.2
  - `closing_accel_threshold`: -0.3
  - `min_avg_frames`: 3
  - `avg_window`: 1.0 (fixed)

## 2. Crosswalks Parameters (Pedestrian-Vehicle crosswalk interactions)
- **Best Precision@10**: 0.100
- **Best Recall@10**: 0.500
- **Optimized Parameters**:
  - `min_mdrac`: 3.4
  - `max_ttc`: 0.8
  - `min_speed_diff`: 0.5
  - `yaw_diff_rate_threshold`: 10.0
  - `avg_window`: 0.3
  - `min_avg_frames`: 1
