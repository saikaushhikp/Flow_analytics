"""
Multi-criteria conflict detection for rear-end and head-on/crossing conflicts.

Rear-end conflicts: Use M-DRAC (Modified Deceleration Rate to Avoid Crash)
Head-on/crossing: Use evasive action detection (yaw rate OR deceleration)
"""

import numpy as np
import pandas as pd
import yaml
from typing import Tuple


def load_detection_config(config_path: str = 'config.yaml') -> dict:
    """Load conflict detection configuration."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config.get('conflict_detection', {})


def classify_conflict_type(
    pairs: pd.DataFrame,
    yaw_threshold: float = None,
    config_path: str = 'config.yaml'
) -> pd.DataFrame:
    """
    Classify conflicts as rear-end or head-on/crossing based on relative yaw.
    
    Args:
        pairs: DataFrame with pair data including 'yaw_diff' column
        yaw_threshold: Threshold in degrees (default from config: 90)
        config_path: Path to config.yaml
    
    Returns:
        DataFrame with added 'conflict_type' column
    """
    if yaw_threshold is None:
        config = load_detection_config(config_path)
        yaw_threshold = config.get('rear_end', {}).get('yaw_threshold', 90.0)
    
    # Convert to radians
    yaw_threshold_rad = np.deg2rad(yaw_threshold)
    
    # Classify based on yaw difference
    pairs = pairs.copy()
    pairs['conflict_type'] = np.where(
        pairs['yaw_diff'] < yaw_threshold_rad,
        'rear_end',
        'head_on'
    )
    
    return pairs


def detect_near_misses(
    pairs: pd.DataFrame,
    mdrac: np.ndarray = None,
    config_path: str = 'config.yaml'
) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Detect near-misses using multi-criteria approach.
    
    Rear-end: M-DRAC > threshold
    Head-on/Crossing: (rel_yaw_rate > threshold) OR (rel_deceleration > threshold)
    
    Args:
        pairs: DataFrame with conflict pairs
        mdrac: Pre-calculated M-DRAC values (optional)
        config_path: Path to config.yaml
    
    Returns:
        Tuple of (filtered DataFrame, detection metrics array)
    """
    config = load_detection_config(config_path)
    
    # Get thresholds
    rear_end_cfg = config.get('rear_end', {})
    head_on_cfg = config.get('head_on', {})
    
    min_mdrac = rear_end_cfg.get('min_mdrac', 3.4)
    min_yaw_rate = head_on_cfg.get('min_yaw_rate', 0.4)
    min_deceleration = head_on_cfg.get('min_deceleration', 4.5)
    
    # Classify conflict types
    pairs = classify_conflict_type(pairs, config_path=config_path)
    
    # Detection masks for each type
    is_rear_end = pairs['conflict_type'] == 'rear_end'
    is_head_on = pairs['conflict_type'] == 'head_on'
    
    # Rear-end detection: M-DRAC threshold
    if mdrac is not None:
        rear_end_detected = mdrac >= min_mdrac
    else:
        rear_end_detected = np.zeros(len(pairs), dtype=bool)
    
    # Head-on detection: yaw rate OR deceleration
    yaw_detected = pairs['rel_yaw_rate'].values >= min_yaw_rate
    decel_detected = pairs['rel_deceleration'].values >= min_deceleration
    head_on_detected = yaw_detected | decel_detected
    
    # Combine detections by conflict type
    detected = (is_rear_end & rear_end_detected) | (is_head_on & head_on_detected)
    
    # Store detection metrics
    detection_metric = np.where(
        is_rear_end,
        mdrac if mdrac is not None else 0.0,
        np.maximum(
            pairs['rel_yaw_rate'].values / min_yaw_rate,  # Normalized yaw rate
            pairs['rel_deceleration'].values / min_deceleration  # Normalized decel
        )
    )
    
    # Add detection info to dataframe
    pairs = pairs[detected].copy()
    pairs['detection_metric'] = detection_metric[detected]
    
    return pairs, detection_metric[detected]


def aggregate_mdrac_per_pair(
    conflicts: pd.DataFrame,
    mdrac_col: str = 'mdrac',
    aggregation: str = None,
    config_path: str = 'config.yaml'
) -> pd.DataFrame:
    """
    Aggregate M-DRAC values per unique pair.
    
    Args:
        conflicts: DataFrame with M-DRAC conflicts
        mdrac_col: Name of M-DRAC column
        aggregation: 'max', 'mean', or 'rolling' (default from config: 'max')
        config_path: Path to config.yaml
    
    Returns:
        DataFrame with aggregated M-DRAC per pair
    """
    if aggregation is None:
        config = yaml.safe_load(open(config_path, 'r'))
        aggregation = config.get('postprocessing', {}).get('mdrac_aggregation', 'max')
    
    if aggregation == 'max':
        # Simple: take maximum M-DRAC per pair
        agg_func = {mdrac_col: 'max', 'timestamp': ['min', 'max', 'count']}
        result = conflicts.groupby(['id1', 'id2']).agg(agg_func).reset_index()
        result.columns = ['id1', 'id2', 'mdrac_max', 'first_ts', 'last_ts', 'frame_count']
        
    elif aggregation == 'mean':
        # Average M-DRAC per pair
        agg_func = {mdrac_col: 'mean', 'timestamp': ['min', 'max', 'count']}
        result = conflicts.groupby(['id1', 'id2']).agg(agg_func).reset_index()
        result.columns = ['id1', 'id2', 'mdrac_mean', 'first_ts', 'last_ts', 'frame_count']
        
    else:
        # Return all frames (no aggregation for rolling window analysis)
        result = conflicts
    
    return result
