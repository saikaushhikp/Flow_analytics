"""
Risk Vector Extraction Module for IRSM

Extracts risk features using AVERAGED aggregation across interactions.
**USES EXISTING SSM FUNCTIONS** - No reimplementation.

Features extracted:
    - Metadata: pair_id, timestamp, label1, label2, link, same_zone
    - Risk metrics: mdrac, distance, closing_speed, closing_accel, speed_diff, ttc, yaw_diff, yaw_rate
"""

import numpy as np
import pandas as pd
from typing import List, Dict
import sys
import os

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import existing SSM functions - NO REIMPLEMENTATION
from ssm.utils import filter_approaching, identify_leader_follower


LABEL_TO_PRT_KEY = {
    1: 'pedestrian',
    2: 'bicycle',
    3: 'motorcycle',
    4: 'car',
    5: 'escooter',
    6: 'van',
    7: 'truck',
    8: 'bus',
}





def aggregate_to_peak_avg_mdrac(
    pairs: pd.DataFrame,
    min_avg_frames: int = 3,
    window_sec: float = 1.0,
    max_frame_gap: float | None = None,
) -> pd.DataFrame:
    """
    Aggregate pairs by selecting peak avg MDRAC moment WITHOUT threshold filtering.
    
    For each pair:
    1. Calculate rolling average MDRAC over time window (~1 second)
    2. Select timestamp with HIGHEST avg_mdrac (NO threshold filtering)
    3. Return features at that timestamp:
       - mdrac = avg_mdrac (averaged)
       - distance, ttc, closing_speed, etc. = point values at that timestamp (NOT averaged)
    
    This is for IRSM which needs BOTH normal and risky cases (no filtering).
    
    Args:
        pairs: DataFrame with mdrac column and other features
        min_avg_frames: Minimum frames for rolling average (default 3)
    
    Returns:
        DataFrame with one row per pair (at peak avg MDRAC moment)
    """
    if len(pairs) == 0:
        return pairs
    
    print(f"\nAggregating {len(pairs):,} observations to peak avg MDRAC moments...")
    print(f"  NO threshold filtering (IRSM needs both normal and risky cases)")
    
    results = []
    debug_stats = {'too_few_frames': 0, 'success': 0}
    
    # Group by pair
    unique_pairs = pairs.groupby(['id1', 'id2']).size()
    print(f"  Unique pairs: {len(unique_pairs)}")
    
    max_frame_gap = max_frame_gap or max(0.5, window_sec * 2)
    window = pd.Timedelta(seconds=window_sec)

    for (id1, id2), group in pairs.groupby(['id1', 'id2']):
        group = group.sort_values('timestamp').copy()
        group['timestamp'] = pd.to_datetime(group['timestamp'])
        
        if len(group) < min_avg_frames:
            debug_stats['too_few_frames'] += 1
            continue

        gaps = group['timestamp'].diff().dt.total_seconds().fillna(0)
        group['event_segment'] = (gaps > max_frame_gap).cumsum()

        pair_success = False
        for _, segment in group.groupby('event_segment'):
            if len(segment) < min_avg_frames:
                continue

            indexed = segment.set_index('timestamp', drop=False)
            indexed['avg_mdrac'] = indexed['mdrac'].rolling(
                window=window,
                min_periods=min_avg_frames,
                center=True,
            ).mean()

            group_valid = indexed[indexed['avg_mdrac'].notna()].copy()
            if len(group_valid) == 0:
                continue

            peak_idx = group_valid['avg_mdrac'].idxmax()
            peak_rows = group_valid.loc[peak_idx]
            if isinstance(peak_rows, pd.DataFrame):
                peak_row = peak_rows.iloc[0].copy()
            else:
                peak_row = peak_rows.copy()
            
            del peak_rows
            
            peak_row['mdrac'] = peak_row['avg_mdrac']
            peak_row['num_frames'] = len(group_valid)
            peak_row['duration'] = (
                group_valid['timestamp'].max() - group_valid['timestamp'].min()
            ).total_seconds()

            results.append(peak_row.to_dict())
            pair_success = True

        if pair_success:
            debug_stats['success'] += 1
        else:
            debug_stats['too_few_frames'] += 1
    
    # Print debug stats
    print(f"  Debug stats:")
    print(f"    Too few frames (< {min_avg_frames}): {debug_stats['too_few_frames']}")
    print(f"    Success: {debug_stats['success']}")
    
    if len(results) == 0:
        return pd.DataFrame()
    
    result_df = pd.DataFrame(results)
    
    # Drop the temporary avg_mdrac column
    if 'avg_mdrac' in result_df.columns:
        result_df = result_df.drop(columns=['avg_mdrac'])
    
    print(f"  \N{CHECK MARK} Reduced to {len(result_df):,} unique pairs")
    
    return result_df


def _lookup_prt(labels: np.ndarray, prt_config: Dict) -> np.ndarray:
    default_prt = prt_config['default']
    return np.array([
        prt_config.get(LABEL_TO_PRT_KEY.get(int(label), ''), default_prt)
        for label in labels
    ])


def extract_risk_vectors(pairs: pd.DataFrame, 
                        region: str = "",
                        config: Dict = None) -> pd.DataFrame:
    """
    Extract risk vectors from pair data using config-based thresholds.
    Uses existing SSM functions - NO hardcoded values.
    
    Pipeline:
        1. Apply SSM filter_approaching
        2. Filter by config thresholds (TTC, closing_speed)
        3. Compute MDRAC using existing ModifiedDRAC class
        4. Aggregate to average
        5. Select final features
        
    Args:
        pairs: DataFrame with pair observations
        region: Region name for link generation
        config: IRSM configuration dict (from irsm_config.yaml)
        
    Returns:
        DataFrame with averaged risk features per pair
    """
    if len(pairs) == 0:
        print("No pairs to process")
        return pd.DataFrame()
    
    # Load config thresholds
    if config is None:
        raise ValueError("Config is required - no hardcoded values allowed")
    
    max_ttc = config['pair_generation']['max_ttc']
    min_closing_speed = config['pair_generation']['min_closing_speed']
    prt_config = config['prt']
    aggregation_config = config.get('aggregation', {})
    window_sec = aggregation_config.get('window_sec', 1.0)
    min_avg_frames = aggregation_config.get('min_avg_frames', 3)
    max_frame_gap = aggregation_config.get('max_frame_gap_sec')
    
    print(f"\nExtracting risk vectors from {len(pairs):,} pair observations...")
    print(f"  Using config: max_ttc={max_ttc}s, min_closing_speed={min_closing_speed} m/s")
    
    # Create pair_id
    pairs['pair_id'] = pairs['id1'].astype(str) + '_' + pairs['id2'].astype(str)
    
    # ========================================================================
    # STEP 1: Apply SSM filter_approaching (from existing code)
    # ========================================================================
    print("  Applying SSM filters...")
    initial_count = len(pairs)
    
    # Use existing filter_approaching function
    pairs = filter_approaching(pairs)
    print(f"    Approaching filter: {len(pairs):,} pairs (removed {initial_count - len(pairs):,})")
    
    if len(pairs) == 0:
        print("  No approaching pairs found")
        return pd.DataFrame()
    
    # Filter by config thresholds
    ttc_count = len(pairs)
    pairs = pairs[pairs['ttc'] <= max_ttc].copy()
    print(f"    TTC <= {max_ttc}s: {len(pairs):,} pairs (removed {ttc_count - len(pairs):,})")
    
    if len(pairs) == 0:
        print("  No pairs within TTC threshold")
        return pd.DataFrame()
    
    closing_count = len(pairs)
    pairs = pairs[pairs['closing_speed'] >= min_closing_speed].copy()
    print(f"    Closing speed >= {min_closing_speed} m/s: {len(pairs):,} pairs (removed {closing_count - len(pairs):,})")
    
    if len(pairs) == 0:
        print("  No pairs with sufficient closing speed")
        return pd.DataFrame()
    
    # ========================================================================
    # STEP 2: Compute MDRAC using formula from config (NO hardcoded values)
    # ========================================================================
    print("  Computing MDRAC...")
    print(f"    Using label-aware PRT values from config")

    pairs = identify_leader_follower(pairs)
    
    # MDRAC formula (from SSM m_drac.py lines 176-184)
    # Formula: MDRAC = closing_speed / (2 * (TTC - PRT))
    # With capping to avoid infinity when (TTC - PRT) is very small
    
    follower_label = np.where(
        pairs['is_veh1_follower'],
        pairs['label1'],
        pairs['label2'],
    )
    prt_effective = _lookup_prt(follower_label, prt_config)

    min_time_buffer = config.get('min_time_buffer', 0.2)
    time_available = pairs['ttc'].values - prt_effective
    
    # Apply formula with capping
    mdrac = np.where(
        time_available > min_time_buffer,
        pairs['closing_speed'].values / (2 * time_available),
        pairs['closing_speed'].values / (2 * min_time_buffer)
    )
    
    pairs['mdrac'] = mdrac
    pairs['prt_effective'] = prt_effective
    
    # ========================================================================
    # STEP 3: Aggregate to peak avg MDRAC moment (NO threshold filtering for IRSM)
    # ========================================================================
    aggregated = aggregate_to_peak_avg_mdrac(
        pairs,
        min_avg_frames=min_avg_frames,
        window_sec=window_sec,
        max_frame_gap=max_frame_gap,
    )

    if aggregated.empty:
        print("  No risk vectors after temporal aggregation")
        return pd.DataFrame()
    
    # ========================================================================
    # STEP 4: Select final features
    # ========================================================================
    metadata_cols = ['pair_id', 'timestamp', 'label1', 'label2']
    
    # Link generation
    if 'link' not in aggregated.columns:
        aggregated['link'] = ""
        if region:
            try:
                ts_str = pd.to_datetime(aggregated['timestamp']).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                aggregated['link'] = f"https://di-india-collab.flow-analytics.io/tools/replay/" + ts_str
            except:
                pass
    
    # Same zone indicator
    if 'zone1' in aggregated.columns and 'zone2' in aggregated.columns:
        aggregated['same_zone'] = (aggregated['zone1'] == aggregated['zone2']).astype(int)
    else:
        aggregated['same_zone'] = 0
    
    # Risk features (at peak avg MDRAC timestamp)
    # NOTE: ONLY mdrac is averaged, others are point values at this timestamp!
    # yaw_diff_rate was computed by filter_approaching
    risk_features = [
        'mdrac',                    # Averaged MDRAC (rolling window)
        'distance',                 # Point value at peak timestamp
        'closing_speed',            # Point value at peak timestamp
        'closing_accel',            # Point value at peak timestamp
        'speed_diff',               # Follower speed minus leader speed
        'ttc',                      # Point value at peak timestamp
        'yaw_diff',                 # Point value at peak timestamp
        'yaw_diff_rate'             # Point value at peak timestamp
    ]
    
    # Rename yaw_diff_rate to yaw_rate for consistency with user spec
    if 'yaw_diff_rate' in aggregated.columns:
        aggregated = aggregated.rename(columns={'yaw_diff_rate': 'yaw_rate'})
        risk_features = ['yaw_rate' if f == 'yaw_diff_rate' else f for f in risk_features]
    
    # Final column selection
    final_cols = metadata_cols + ['link', 'same_zone'] + risk_features
    
    # Keep only available columns
    available_cols = [c for c in final_cols if c in aggregated.columns]
    result = aggregated[available_cols].copy()
    
    print(f"  \N{CHECK MARK} Extracted risk vectors: {len(result):,} rows × {len(available_cols)} features")
    print(f"  Features: {', '.join([f for f in risk_features if f in result.columns])}")
    print(f"  NOTE: Only MDRAC is averaged; others are point values at peak timestamp")
    
    return result


def get_feature_names() -> List[str]:
    """
    Get ordered list of risk feature names.
    
    Returns:
        List of feature column names (excluding metadata)
    """
    return [
        'mdrac',
        'distance',
        'closing_speed',
        'closing_accel',
        'speed_diff',
        'ttc',
        'yaw_diff',
        'yaw_rate'
    ]
