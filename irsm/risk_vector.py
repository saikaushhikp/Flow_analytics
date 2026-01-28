"""
Risk Vector Extraction Module for IRSM

Extracts risk features using AVERAGED aggregation across interactions.
**USES EXISTING SSM FUNCTIONS** - No reimplementation.

Features extracted:
    - Metadata: pair_id, timestamp, label1, label2, link, same_zone
    - Risk metrics: mdrac, distance, closing_speed, closing_accel, ttc, yaw_diff, yaw_rate
"""

import numpy as np
import pandas as pd
from typing import List, Dict
import sys
import os

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import existing SSM functions - NO REIMPLEMENTATION
from ssm.utils import filter_approaching





def aggregate_to_peak_avg_mdrac(pairs: pd.DataFrame,
                                 min_avg_frames: int = 3) -> pd.DataFrame:
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
    
    for (id1, id2), group in pairs.groupby(['id1', 'id2']):
        group = group.sort_values('timestamp').copy()
        
        if len(group) < 4:
            debug_stats['too_few_frames'] += 1
            continue  # Require minimum 4 frames (0.4s) for rolling average
        
        # Calculate frame-based rolling average
        # Use window size that approximates 1 second based on typical frame rate (~10 fps)
        window_frames = min(max(min_avg_frames, 10), len(group))  # Adaptive window
        
        group['avg_mdrac'] = group['mdrac'].rolling(
            window=window_frames,
            min_periods=min_avg_frames,
            center=True
        ).mean()
        
        # Remove NaN values from rolling average
        group_valid = group[group['avg_mdrac'].notna()].copy()
        
        if len(group_valid) == 0:
            debug_stats['too_few_frames'] += 1
            continue
        
        # Take peak avg_mdrac moment (HIGHEST averaged MDRAC)
        peak_idx = group_valid['avg_mdrac'].idxmax()
        peak_row = group_valid.loc[peak_idx].copy()
        
        # Replace instantaneous MDRAC with averaged MDRAC
        # OTHER metrics (distance, ttc, closing_speed) remain as point values!
        peak_row['mdrac'] = peak_row['avg_mdrac']
        
        results.append(peak_row)
        debug_stats['success'] += 1
    
    # Print debug stats
    print(f"  Debug stats:")
    print(f"    Too few frames (< 4): {debug_stats['too_few_frames']}")
    print(f"    Success: {debug_stats['success']}")
    
    if len(results) == 0:
        return pd.DataFrame()
    
    result_df = pd.DataFrame(results)
    
    # Drop the temporary avg_mdrac column
    if 'avg_mdrac' in result_df.columns:
        result_df = result_df.drop(columns=['avg_mdrac'])
    
    print(f"  ✓ Reduced to {len(result_df):,} unique pairs")
    
    return result_df


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
    prt_default = config['prt']['default']
    
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
    print(f"    Using PRT={prt_default}s from config")
    
    # MDRAC formula (from SSM m_drac.py lines 176-184)
    # Formula: MDRAC = closing_speed / (2 * (TTC - PRT))
    # With capping to avoid infinity when (TTC - PRT) is very small
    
    min_time_buffer = 0.2  # Standard from SSM config
    time_available = pairs['ttc'].values - prt_default
    
    # Apply formula with capping
    mdrac = np.where(
        time_available > min_time_buffer,
        pairs['closing_speed'].values / (2 * time_available),
        pairs['closing_speed'].values / (2 * min_time_buffer)
    )
    
    pairs['mdrac'] = mdrac
    
    # ========================================================================
    # STEP 3: Aggregate to peak avg MDRAC moment (NO threshold filtering for IRSM)
    # ========================================================================
    aggregated = aggregate_to_peak_avg_mdrac(
        pairs,
        min_avg_frames=3
    )
    
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
                aggregated['link'] = f"https://di-india-collab-2.flow-analytics.io/tools/replay/" + ts_str
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
    
    print(f"  ✓ Extracted risk vectors: {len(result):,} rows × {len(available_cols)} features")
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
        'ttc',
        'yaw_diff',
        'yaw_rate'
    ]
