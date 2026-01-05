"""
Duration filter for removing short-lived conflicts.

Filters out conflicts that last less than a minimum duration or frame count,
as these are likely detection noise rather than genuine near-miss events.
"""

import pandas as pd
import yaml


def load_postprocessing_config(config_path: str = 'config.yaml') -> dict:
    """Load post-processing configuration."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config.get('postprocessing', {})


def filter_by_duration(
    conflicts: pd.DataFrame,
    min_duration: float = None,
    min_frames: int = None,
    timestamp_col: str = 'timestamp',
    pair_id_cols: list = None,
    sampling_rate: float = 10.0,
    config_path: str = 'config.yaml'
) -> pd.DataFrame:
    """
    Filter conflicts by minimum duration or frame count.
    
    Args:
        conflicts: DataFrame with conflict pairs
        min_duration: Minimum duration in seconds (overrides config if provided)
        min_frames: Minimum number of frames (overrides config if provided)
        timestamp_col: Name of timestamp column
        pair_id_cols: Columns defining unique pairs (default: ['id1', 'id2'])
        sampling_rate: Data sampling rate in Hz (default: 10.0)
        config_path: Path to config.yaml
    
    Returns:
        Filtered DataFrame with conflicts meeting duration threshold
    """
    if pair_id_cols is None:
        pair_id_cols = ['id1', 'id2']
    
    # Load config if thresholds not provided
    if min_duration is None and min_frames is None:
        config = load_postprocessing_config(config_path)
        min_duration = config.get('min_duration', 0.5)
        min_frames = config.get('min_frames', 5)
    
    # Calculate duration per pair
    pair_stats = conflicts.groupby(pair_id_cols).agg({
        timestamp_col: ['min', 'max', 'count']
    }).reset_index()
    
    pair_stats.columns = pair_id_cols + ['first_ts', 'last_ts', 'frame_count']
    pair_stats['duration'] = pair_stats['last_ts'] - pair_stats['first_ts']
    
    # Apply filters
    mask = pd.Series(True, index=pair_stats.index)
    
    if min_duration is not None:
        mask &= (pair_stats['duration'] >= min_duration)
    
    if min_frames is not None:
        mask &= (pair_stats['frame_count'] >= min_frames)
    
    valid_pairs = pair_stats[mask][pair_id_cols]
    
    # Filter original dataframe
    filtered = conflicts.merge(valid_pairs, on=pair_id_cols, how='inner')
    
    return filtered
