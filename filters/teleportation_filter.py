"""
Teleportation Filter

Removes vehicles with unrealistic position jumps between consecutive frames
(tracking errors, ID switches, sensor glitches). Uses vectorized pandas/numpy.
"""

import pandas as pd
import numpy as np
from tqdm import tqdm


def calibrate_threshold(df: pd.DataFrame, sampling_rate: float = 10.0, verbose: bool = True) -> float:
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


def filter_teleportation_events(
    df: pd.DataFrame, 
    max_jump: float = 3.5,
    sampling_rate: float = 10.0,
    verbose: bool = True
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


def analyze_position_jumps(df: pd.DataFrame, max_jump: float = 5.0) -> pd.DataFrame:
    """
    Analyze position jump statistics without filtering.
    Useful for calibrating the max_jump threshold.
    
    Args:
        df: DataFrame with columns [id, timestamp, pos_x, pos_y]
        max_jump: Threshold for flagging jumps
        
    Returns:
        DataFrame with jump statistics per vehicle
    """
    df_sorted = df.sort_values(['id', 'timestamp']).copy()
    
    # Calculate jumps
    df_sorted['prev_x'] = df_sorted.groupby('id')['pos_x'].shift(1)
    df_sorted['prev_y'] = df_sorted.groupby('id')['pos_y'].shift(1)
    dx = df_sorted['pos_x'] - df_sorted['prev_x']
    dy = df_sorted['pos_y'] - df_sorted['prev_y']
    df_sorted['jump_distance'] = np.sqrt(dx**2 + dy**2)
    
    # Statistics per vehicle
    stats = df_sorted.groupby('id')['jump_distance'].agg([
        ('max_jump', 'max'),
        ('mean_jump', 'mean'),
        ('median_jump', 'median'),
        ('violations', lambda x: (x > max_jump).sum())
    ]).reset_index()
    
    stats = stats.sort_values('max_jump', ascending=False)
    
    print(f"\n=== Position Jump Analysis ===")
    print(f"Threshold: {max_jump:.1f} m")
    print(f"\nOverall statistics:")
    print(f"  Total vehicles: {len(stats)}")
    print(f"  Vehicles with violations: {(stats['violations'] > 0).sum()}")
    print(f"  Max jump observed: {stats['max_jump'].max():.1f} m")
    print(f"  95th percentile: {stats['max_jump'].quantile(0.95):.1f} m")
    print(f"  99th percentile: {stats['max_jump'].quantile(0.99):.1f} m")
    
    print(f"\nTop 10 vehicles by max jump:")
    print(stats.head(10).to_string(index=False))
    
    return stats


# Testing
if __name__ == "__main__":
    # Test with dummy data
    print("Testing Teleportation Filter...")
    
    # Create test data with teleporting vehicle
    test_data = {
        'id': [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3],
        'timestamp': [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2],
        'pos_x': [
            0, 1, 2, 3,      # Vehicle 1: smooth (OK)
            0, 1, 10, 11,    # Vehicle 2: teleports at t=2 (BAD)
            0, 1, 2          # Vehicle 3: smooth (OK)
        ],
        'pos_y': [
            0, 0.5, 1, 1.5,
            0, 0.5, 0.7, 1.2,
            10, 10.5, 11
        ]
    }
    
    df_test = pd.DataFrame(test_data)
    print(f"\nTest data: {len(df_test)} records, {df_test['id'].nunique()} vehicles")
    
    # Analyze jumps
    print("\nAnalyzing jumps:")
    stats = analyze_position_jumps(df_test, max_jump=5.0)
    
    # Apply filter
    df_filtered = filter_teleportation_events(df_test, max_jump=3.5, verbose=True)
    
    print(f"\nExpected: Vehicles 1 & 3 kept, Vehicle 2 removed")
    print(f"Actual: {df_filtered['id'].nunique()} vehicle(s) remaining")
    print(f"Vehicle IDs kept: {sorted(df_filtered['id'].unique())}")
