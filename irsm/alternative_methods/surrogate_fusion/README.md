# Surrogate Fusion Pipeline

This alternative method implements a **Surrogate Fusion Pipeline** to post-filter high M-DRAC conflict candidates using auxiliary safety surrogates and behavioral indicators.

## Motivation
M-DRAC is a kinetic safety surrogate. However, transient speed changes or measurement noise can result in a high M-DRAC score even when no actual near-miss event occurred. By requiring auxiliary behavioral evidence (such as actual vehicle braking response) or immediate collision risk (low TTC), we can cut down false positives significantly.

## Post-Filtering Rule
- **Baseline Rule**: Candidate is a near-miss if `mdrac >= 3.0`.
- **Post-Filtered Rule**: Candidate is a near-miss if:
  - `mdrac >= 3.0`
  - **AND** at least one of:
    - **Follower Deceleration**: The follower performed a braking action (`decel_max_deceleration < -0.8` m/s²).
    - **Low TTC**: The time-to-collision is critical (`ttc < 1.5` seconds).

## Structure
- `surrogate_fusion.py`: Evaluates the baseline vs post-filtered rules on the splits and prints metrics.
- `results/`: Contains output evaluation metrics comparing the rules.
