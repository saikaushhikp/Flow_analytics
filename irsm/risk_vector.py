"""
Risk Vector Extraction Module for IRSM

Extracts risk features at the critical moment (highest 1-sec averaged MDRAC) per pair.
**USES EXISTING SSM FILTERS AND CALCULATIONS** - No reimplementation.

Features extracted:
    - Metadata: pair_id, timestamp, label1, label2, link, same_zone
    - Risk metrics: mdrac, distance, closing_speed, closing_accel, ttc, yaw_diff, yaw_rate
    
SSM Filters Applied:
    - filter_approaching: Keeps only pairs where gap is closing
    - Adds: closing_speed, ttc, closing_accel, yaw_diff_rate (exact SSM formulas)
    - TTC threshold: <= 10.0s (reasonable collision time)
    - Closing speed threshold: >= 0.5 m/s (meaningful approach)
"""

import numpy as np
import pandas as pd
from typing import List
import sys
import os

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import SSM utilities - REUSE existing functions
from ssm.utils import filter_approaching


def compute_mdrac_with_prt(pairs: pd.DataFrame, prt: float = 1.5, min_time_buffer: float = 0.2) -> pd.DataFrame:
    """
    Compute MDRAC using SSM formula with proper handling of edge cases.
    
    Formula (from m_drac.py calculate_mdrac):
        MDRAC = closing_speed / (2 * (TTC - PRT))
        
    With capping to AVOID INFINITY (exact SSM logic):
        If (TTC - PRT) < min_time_buffer:
            MDRAC = closing_speed / (2 * min_time_buffer)
    
    This is THE SAME logic used in ModifiedDRAC.calculate_mdrac() - no infinities.
    
    Args:
        pairs: DataFrame with columns [ttc, closing_speed] already computed by filter_approaching
        prt: Perception-Reaction Time (default 1.5s)
        min_time_buffer: Minimum time denominator to avoid infinity (default 0.2s from config)
        
    Returns:
        DataFrame with added 'mdrac' column (NO infinite values)
    """
    if len(pairs) == 0:
        return pairs
    
    # Time available for reaction
    time_available = pairs['ttc'].values - prt
    
    # MDRAC formula with capping (EXACT SSM LOGIC from m_drac.py line 179-183)
    mdrac = np.where(
        time_available > min_time_buffer,
        pairs['closing_speed'].values / (2 * time_available),
        pairs['closing_speed'].values / (2 * min_time_buffer)
    )
    
    pairs = pairs.copy()
    pairs['mdrac'] = mdrac
    
    return pairs


def aggregate_to_critical_moment(pairs: pd.DataFrame, window_sec: float = 1.0) -> pd.DataFrame:
    """
    Aggregate each pair to a single row representing the critical moment.
    
    Critical moment = timestamp with highest 1-second averaged MDRAC.
    
    Process:
        1. Compute 1-second averaged MDRAC for each pair
        2. Find timestamp bin with highest average
        3. Extract all features at that timestamp (or closest observation)
        
    Args:
        pairs: DataFrame with all pair observations (multiple rows per pair)
               Must have columns: pair_id, timestamp, mdrac, and all risk features
        window_sec: Time window for MDRAC averaging (default 1.0s)
        
    Returns:
        DataFrame with 1 row per pair_id, containing features at critical moment
    """
    if len(pairs) == 0:
        return pairs
    
    print(f"\nAggregating {len(pairs):,} observations to critical moments...")
    print(f"  Window: {window_sec}s for MDRAC averaging")
    
    # Create time bins (1-second windows)
    pairs = pairs.copy()
    pairs['timestamp_dt'] = pd.to_datetime(pairs['timestamp'])
    pairs['time_bin'] = pairs['timestamp_dt'].dt.floor(f'{window_sec}s')
    
    # Calculate 1-second averaged MDRAC for each pair-bin
    # NO infinite values because we're using capped MDRAC formula
    bin_avg = pairs.groupby(['pair_id', 'time_bin'])['mdrac'].mean().reset_index()
    bin_avg = bin_avg.rename(columns={'mdrac': 'mdrac_avg'})
    
    # Find bin with highest average MDRAC for each pair
    idx_max = bin_avg.groupby('pair_id')['mdrac_avg'].idxmax()
    critical_bins = bin_avg.loc[idx_max, ['pair_id', 'time_bin', 'mdrac_avg']]
    
    # Merge back to get all observations in critical bins
    pairs_with_critical = pairs.merge(
        critical_bins[['pair_id', 'time_bin']],
        on=['pair_id', 'time_bin'],
        how='inner'
    )
    
    # For each pair, select ONE observation from the critical bin
    # Strategy: Pick observation closest to middle of bin
    pairs_with_critical['time_offset'] = (
        pairs_with_critical['timestamp_dt'] - pairs_with_critical['time_bin']
    ).dt.total_seconds()
    
    # Find observation closest to 0.5s (middle of 1-sec bin)
    pairs_with_critical['offset_from_middle'] = np.abs(pairs_with_critical['time_offset'] - 0.5)
    idx_critical = pairs_with_critical.groupby('pair_id')['offset_from_middle'].idxmin()
    
    # Extract critical moment observations
    critical_moments = pairs_with_critical.loc[idx_critical].copy()
    
    # Clean up temporary columns
    critical_moments = critical_moments.drop(columns=[
        'timestamp_dt', 'time_bin', 'time_offset', 'offset_from_middle'
    ])
    
    print(f"  ✓ Reduced to {len(critical_moments):,} unique pairs")
    
    return critical_moments


def extract_risk_vectors(pairs: pd.DataFrame, region: str = "", 
                        apply_filters: bool = True,
                        max_ttc: float = 10.0,
                        min_closing_speed: float = 0.5) -> pd.DataFrame:
    """
    Extract risk vectors from pair data at critical moments.
    
    Pipeline:
        1. Apply SSM filters (approaching, TTC, closing_speed thresholds)
        2. Compute MDRAC with proper capping (no infinities)
        3. Aggregate to critical moment (highest 1-sec avg MDRAC)
        4. Select final features
        
    Args:
        pairs: DataFrame with pair observations
               Required columns: id1, id2, timestamp, pos_x1, pos_y1, pos_x2, pos_y2,
                                vel_x1, vel_y1, vel_x2, vel_y2, yaw1, yaw2,
                                label1, label2, zone1, zone2 (optional)
        region: Region name for link generation (optional)
        apply_filters: If True, applies approaching + TTC + closing_speed filters (default True)
        max_ttc: Maximum TTC threshold (seconds, default 10.0)
        min_closing_speed: Minimum closing speed (m/s, default 0.5)
        
    Returns:
        DataFrame with columns:
            - pair_id, timestamp, label1, label2, link, same_zone (metadata)
            - mdrac, distance, closing_speed, closing_accel, ttc, yaw_diff, yaw_rate (risk features)
    """
    if len(pairs) == 0:
        print("No pairs to process")
        return pd.DataFrame()
    
    print(f"\nExtracting risk vectors from {len(pairs):,} pair observations...")
    
    # Create pair_id
    pairs['pair_id'] = pairs['id1'].astype(str) + '_' + pairs['id2'].astype(str)
    
    # ========================================================================
    # STEP 1: Apply SSM filters (uses existing SSM functions)
    # ========================================================================
    if apply_filters:
        print("  Applying SSM filters...")
        initial_count = len(pairs)
        
        # Filter 1: Keep only approaching pairs (gap closing)
        # This adds: closing_speed, ttc, closing_accel, yaw_diff_rate
        pairs = filter_approaching(pairs)
        print(f"    Approaching filter: {len(pairs):,} pairs (removed {initial_count - len(pairs):,})")
        
        if len(pairs) == 0:
            print("  No approaching pairs found")
            return pd.DataFrame()
        
        # Filter 2: TTC threshold (reasonable time to collision)
        ttc_count = len(pairs)
        pairs = pairs[pairs['ttc'] <= max_ttc].copy()
        print(f"    TTC <= {max_ttc}s: {len(pairs):,} pairs (removed {ttc_count - len(pairs):,})")
        
        if len(pairs) == 0:
            print("  No pairs within TTC threshold")
            return pd.DataFrame()
        
        # Filter 3: Closing speed threshold (meaningful approach)
        closing_count = len(pairs)
        pairs = pairs[pairs['closing_speed'] >= min_closing_speed].copy()
        print(f"    Closing speed >= {min_closing_speed} m/s: {len(pairs):,} pairs (removed {closing_count - len(pairs):,})")
        
        if len(pairs) == 0:
            print("  No pairs with sufficient closing speed")
            return pd.DataFrame()
    
    # ========================================================================
    # STEP 2: Compute MDRAC with proper capping (no infinities)
    # ========================================================================
    print("  Computing MDRAC...")
    pairs = compute_mdrac_with_prt(pairs, prt=1.5, min_time_buffer=0.2)
    
    # ========================================================================
    # STEP 3: Aggregate to critical moments
    # ========================================================================
    critical = aggregate_to_critical_moment(pairs, window_sec=1.0)
    
    # ========================================================================
    # STEP 4: Select final features
    # ========================================================================
    # Metadata (select any - they don't change)
    metadata_cols = ['pair_id', 'timestamp', 'label1', 'label2']
    
    # Link generation
    if 'link' not in critical.columns:
        critical['link'] = ""
        if region:
            try:
                ts_str = pd.to_datetime(critical['timestamp']).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                critical['link'] = f"https://{region}.flow-analytics.io/tools/replay/" + ts_str
            except:
                pass
    
    # Same zone indicator
    if 'zone1' in critical.columns and 'zone2' in critical.columns:
        critical['same_zone'] = (critical['zone1'] == critical['zone2']).astype(int)
    else:
        critical['same_zone'] = 0
    
    # Risk features (at critical moment)
    # yaw_diff_rate was computed by filter_approaching
    risk_features = [
        'mdrac',                    # Highest 1-sec averaged MDRAC (capped, no infinities)
        'distance',                 # Distance at critical moment (from pairs)
        'closing_speed',            # Closing speed at critical moment (from filter_approaching)
        'closing_accel',            # Rate of change of closing speed (from filter_approaching)
        'ttc',                      # Time to collision at critical moment (from filter_approaching)
        'yaw_diff',                 # Heading difference (from filter_approaching -> calculate_yaw_diff_rate)
        'yaw_diff_rate'             # Rate of change of yaw_diff (from filter_approaching)
    ]
    
    # Rename yaw_diff_rate to yaw_rate for consistency with user spec
    if 'yaw_diff_rate' in critical.columns:
        critical = critical.rename(columns={'yaw_diff_rate': 'yaw_rate'})
        risk_features = ['yaw_rate' if f == 'yaw_diff_rate' else f for f in risk_features]
    
    # Final column selection
    final_cols = metadata_cols + ['link', 'same_zone'] + risk_features
    
    # Keep only available columns
    available_cols = [c for c in final_cols if c in critical.columns]
    result = critical[available_cols].copy()
    
    print(f"  ✓ Extracted risk vectors: {len(result):,} rows × {len(available_cols)} features")
    print(f"  Features: {', '.join([f for f in risk_features if f in result.columns])}")
    
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
