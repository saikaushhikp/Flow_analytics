# Temporal Sequence Near-Miss Classifier

This alternative method builds a **Temporal Sequence Near-Miss Classifier** to analyze frame-level dynamics within a 3-second interaction window centered around the peak-risk moment.

## Method
Instead of training deep learning architectures (e.g. GRU, TCN, LSTM) straight away, this method implements a **Tabularized Temporal Summaries** approach. This maintains simplicity, low memory foot-print, and highly interpretable feature importances.

## Features Extracted
For each interaction window, we compute standard statistical aggregates (min, max, mean, standard deviation) over:
- **Distance**: The relative distance between the leader and follower.
- **Closing Speed**: The projection of relative speed along the distance vector.
- **Deceleration**: The deceleration profile of the follower.
- **Yaw Delta**: The angle difference between both trajectories.
- **Braking Response**: The number of frames where follower deceleration was significant.

## Structure
- `temporal_classifier.py`: Code to parse raw trajectories, build the interaction windows, train a Random Forest on summaries, and save results.
- `results/`: Directory containing output datasets, metrics, and models.
