"""
Teleportation Filter

Removes vehicles with unrealistic position jumps between consecutive frames.
Identifies tracking errors, ID switches, and sensor glitches.

Uses vectorized pandas/numpy operations for efficient processing.
"""

import pandas as pd
import numpy as np
from tqdm import tqdm


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Maximum realistic distance a vehicle can travel between frames (meters)
# Default: 3.5m = 126 km/h at 10Hz sampling rate (generous threshold)
MAX_JUMP_DISTANCE = 3.5

# Data sampling frequency (Hz)
SAMPLING_RATE = 10.0

# Enable detailed statistics output
VERBOSE = True


# ============================================================================
# HELPER FUNCTIONS (for threshold calibration)
# ============================================================================

def calibrate_threshold(df: pd.DataFrame, sampling_rate: float = SAMPLING_RATE, verbose: bool = True) -> float:
    """
    Analyze jump distance distribution to recommend optimal threshold.
    
    Args:
        df: DataFrame with columns [id, timestamp, pos_x, pos_y]
        sampling_rate: Data frequency in Hz
        verbose: Print detailed analysis
        
    Returns:
        Recommended threshold (meters)
    """
    if verbose:
        print("\n" + "="*70)
        print("TELEPORTATION THRESHOLD CALIBRATION")
        print("="*70)
    
    # Calculate all jump distances
    df_sorted = df.sort_values(['id', 'timestamp']).copy()
    df_sorted['prev_x'] = df_sorted.groupby('id')['pos_x'].shift(1)
    df_sorted['prev_y'] = df_sorted.groupby('id')['pos_y'].shift(1)
    
    dx = (df_sorted['pos_x'] - df_sorted['prev_x']).values
    dy = (df_sorted['pos_y'] - df_sorted['prev_y']).values
    
    # Calculate distances using vectorized numpy (already optimal)
    jumps = np.sqrt(dx**2 + dy**2)
    
    # Remove NaN (first positions)
    jumps = jumps[~np.isnan(jumps)]
    
    if verbose:
        print(f"\nJump Distance Statistics:")
        print(f"  Total jumps analyzed: {len(jumps):,}")
        print(f"  Mean: {np.mean(jumps):.2f} m")
        print(f"  Median: {np.median(jumps):.2f} m")
        print(f"  Std Dev: {np.std(jumps):.2f} m")
        print(f"\nPercentiles:")
        percentiles = [50, 75, 90, 95, 99, 99.5, 99.9]
        for p in percentiles:
            val = np.percentile(jumps, p)
            kmh = val * sampling_rate * 3.6
            print(f"  {p:5.1f}%: {val:5.2f} m  ({kmh:6.1f} km/h)")
    
    # Recommend threshold at 99.5th percentile (balance between catching errors and keeping good data)
    recommended = np.percentile(jumps, 99.5)
    
    if verbose:
        print(f"\nRecommended threshold: {recommended:.2f} m (99.5th percentile)")
        print(f"  Equivalent speed: {recommended * sampling_rate * 3.6:.1f} km/h at {sampling_rate} Hz")
        print(f"  Expected removal: ~0.5% of vehicle trajectories")
        print("="*70)
    
    return recommended


# ============================================================================
# MAIN FILTER FUNCTION
# ============================================================================

def filter_teleportation_events(
    df: pd.DataFrame, 
    max_jump: float = MAX_JUMP_DISTANCE,
    sampling_rate: float = SAMPLING_RATE,
    verbose: bool = VERBOSE
) -> pd.DataFrame:
    """
    Remove vehicles that exhibit teleportation (unrealistic position jumps).
    
    Uses efficient vectorized operations:
    1. Sort by id and timestamp
    2. Calculate position shifts within each vehicle group
    3. Compute Euclidean distance between consecutive frames
    4. Flag vehicles with any jump > threshold
    
    Args:
        df: DataFrame with columns [id, timestamp, pos_x, pos_y]
        max_jump: Maximum realistic distance between frames (meters)
                  Default 3.5m = 126 km/h at 10Hz (generous threshold)
        sampling_rate: Data frequency in Hz (default 10.0)
        verbose: Print filtering statistics
        
    Returns:
        DataFrame with teleporting vehicles removed
    """
    if verbose:
        print("\n" + "="*70)
        print("TELEPORTATION FILTER")
        print("="*70)
        print(f"Input vehicles: {df['id'].nunique():,}")
        print(f"Input records: {len(df):,}")
        print(f"Max allowed jump: {max_jump:.1f} m")
        print(f"  (Equivalent to {max_jump * sampling_rate * 3.6:.1f} km/h at {sampling_rate} Hz)")
    
    # Sort by vehicle ID and timestamp (critical for shift operation)
    if verbose:
        tqdm.pandas(desc="Sorting data")
    df_sorted = df.sort_values(['id', 'timestamp']).copy()
    
    # Calculate position differences within each vehicle (vectorized!)
    if verbose:
        print("  Calculating frame-to-frame distances...")
    
    # shift() moves values down by 1 row, grouped by vehicle ID
    df_sorted['prev_x'] = df_sorted.groupby('id')['pos_x'].shift(1)
    df_sorted['prev_y'] = df_sorted.groupby('id')['pos_y'].shift(1)
    
    # Calculate Euclidean distance to previous position (vectorized numpy)
    dx = (df_sorted['pos_x'] - df_sorted['prev_x']).values
    dy = (df_sorted['pos_y'] - df_sorted['prev_y']).values
    df_sorted['jump_distance'] = np.sqrt(dx**2 + dy**2)
    
    # First frame of each vehicle has NaN jump_distance (no previous position)
    # Fill NaN with 0 (first frames are always valid)
    df_sorted['jump_distance'] = df_sorted['jump_distance'].fillna(0)
    
    # Find vehicles with ANY jump exceeding threshold (vectorized!)
    teleporting_vehicles = df_sorted[df_sorted['jump_distance'] > max_jump].groupby('id').size()
    teleporting_ids = set(teleporting_vehicles.index)
    
    if verbose and len(teleporting_ids) > 0:
        print(f"\n  Vehicles with teleportation detected: {len(teleporting_ids):,}")
        
        # Statistics on jump distances
        teleport_data = df_sorted[df_sorted['id'].isin(teleporting_ids) & 
                                  (df_sorted['jump_distance'] > max_jump)]
        
        print(f"  - Total teleportation events: {len(teleport_data):,}")
        print(f"  - Max jump distance: {teleport_data['jump_distance'].max():.1f} m")
        print(f"  - Mean jump distance (for violations): {teleport_data['jump_distance'].mean():.1f} m")
        print(f"  - Median jump distance (for violations): {teleport_data['jump_distance'].median():.1f} m")
        
        # Show most severe cases
        worst_cases = teleport_data.nlargest(5, 'jump_distance')[['id', 'timestamp', 'jump_distance']]
        print(f"\n  Worst cases:")
        for _, row in worst_cases.iterrows():
            print(f"    Vehicle {row['id']}: {row['jump_distance']:.1f} m jump at {row['timestamp']}")
    
    # Filter out teleporting vehicles
    df_clean = df_sorted[~df_sorted['id'].isin(teleporting_ids)].copy()
    
    # Drop helper columns
    df_clean = df_clean.drop(columns=['prev_x', 'prev_y', 'jump_distance'])
    
    if verbose:
        print(f"\n  Vehicles after filtering: {df_clean['id'].nunique():,}")
        print(f"  Records removed: {len(df) - len(df_clean):,}")
        print(f"  Percentage removed: {100 * (1 - len(df_clean)/len(df)):.2f}%")
        print("="*70)
    
    return df_clean