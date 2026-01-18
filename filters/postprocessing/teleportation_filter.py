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
# TIMESTAMP-LEVEL TELEPORTATION DETECTION (for post-processing)
# ============================================================================

def flag_teleportation_timestamps(
    df: pd.DataFrame,
    max_jump: float = MAX_JUMP_DISTANCE,
    sampling_rate: float = SAMPLING_RATE,
    verbose: bool = VERBOSE
) -> pd.DataFrame:
    """
    Flag timestamps where vehicles have teleportation, WITHOUT removing vehicles.
    Adds 'has_teleportation' boolean column to identify problematic moments.
    
    Use this in post-processing to filter conflicts at specific timestamps
    rather than removing entire vehicles from the dataset.
    
    Args:
        df: DataFrame with columns [id, timestamp, pos_x, pos_y]
        max_jump: Maximum realistic distance between frames (meters)
        sampling_rate: Data frequency in Hz
        verbose: Print statistics
        
    Returns:
        DataFrame with added 'has_teleportation' column
    """
    if verbose:
        print(f"Flagging teleportation timestamps (threshold: {max_jump:.1f}m)...")
    
    # Sort by vehicle ID and timestamp
    df_sorted = df.sort_values(['id', 'timestamp']).copy()
    
    # Calculate position jumps
    df_sorted['pos_x_next'] = df_sorted.groupby('id')['pos_x'].shift(-1)
    df_sorted['pos_y_next'] = df_sorted.groupby('id')['pos_y'].shift(-1)
    df_sorted['jump_distance'] = np.sqrt(
        (df_sorted['pos_x_next'] - df_sorted['pos_x'])**2 + 
        (df_sorted['pos_y_next'] - df_sorted['pos_y'])**2
    )
    
    # Flag timestamps with jumps > threshold
    df_sorted['has_teleportation'] = df_sorted['jump_distance'] > max_jump
    
    # Also flag neighboring frames (before and after jump)
    # This ensures we filter conflicts near the glitch
    df_sorted['has_teleportation'] = df_sorted.groupby('id')['has_teleportation'].transform(
        lambda x: x | x.shift(-1).fillna(False) | x.shift(1).fillna(False)
    )
    
    # Drop helper columns
    df_sorted = df_sorted.drop(columns=['pos_x_next', 'pos_y_next', 'jump_distance'])
    
    if verbose:
        flagged_count = df_sorted['has_teleportation'].sum()
        print(f"  Flagged {flagged_count:,} timestamps with teleportation ({100*flagged_count/len(df_sorted):.2f}%)")
    
    return df_sorted


def filter_conflicts_by_teleportation(
    conflicts: pd.DataFrame,
    vehicle_data: pd.DataFrame,
    max_jump: float = MAX_JUMP_DISTANCE,
    sampling_rate: float = SAMPLING_RATE,
    verbose: bool = VERBOSE
) -> pd.DataFrame:
    """
    Filter conflicts that occur at timestamps with teleportation glitches.
    
    Removes conflicts where EITHER vehicle (id1 or id2) has unrealistic
    position jumps at the conflict timestamp. This keeps real vehicles
    in the dataset but filters detections at problematic moments.
    
    Args:
        conflicts: DataFrame with columns [timestamp, id1, id2, ...]
                   (can be mdrac_conflicts.csv or spf_conflicts.csv)
        vehicle_data: Original vehicle DataFrame with [id, timestamp, pos_x, pos_y]
        max_jump: Maximum realistic distance between frames (meters)
        sampling_rate: Data frequency in Hz
        verbose: Print filtering statistics
        
    Returns:
        Filtered conflicts DataFrame (conflicts at clean timestamps only)
    """
    if verbose:
        print("\n" + "="*70)
        print("TELEPORTATION TIMESTAMP FILTER (Post-Processing)")
        print("="*70)
        print(f"Input conflicts: {len(conflicts):,}")
        print(f"Max allowed jump: {max_jump:.1f} m ({max_jump * sampling_rate * 3.6:.1f} km/h @ {sampling_rate}Hz)")
    
    # Flag teleportation timestamps in vehicle data
    vehicle_data_flagged = flag_teleportation_timestamps(
        vehicle_data, max_jump, sampling_rate, verbose=False
    )
    
    if verbose:
        flagged_count = vehicle_data_flagged['has_teleportation'].sum()
        print(f"\nFlagged timestamps in vehicle data: {flagged_count:,}")
    
    # Create lookup: (id, timestamp) -> has_teleportation
    teleport_lookup = vehicle_data_flagged.set_index(['id', 'timestamp'])['has_teleportation'].to_dict()
    
    # Check each conflict
    def has_teleportation_at_conflict(row):
        """Check if either vehicle has teleportation at conflict timestamp"""
        v1_key = (row['id1'], row['timestamp'])
        v2_key = (row['id2'], row['timestamp'])
        
        v1_teleport = teleport_lookup.get(v1_key, False)
        v2_teleport = teleport_lookup.get(v2_key, False)
        
        return v1_teleport or v2_teleport
    
    # Apply filter
    conflicts_with_flag = conflicts.copy()
    conflicts_with_flag['has_teleportation'] = conflicts_with_flag.apply(
        has_teleportation_at_conflict, axis=1
    )
    
    # Statistics
    if verbose:
        teleport_conflicts = conflicts_with_flag['has_teleportation'].sum()
        print(f"\nConflicts at glitchy timestamps: {teleport_conflicts:,} ({100*teleport_conflicts/len(conflicts):.1f}%)")
    
    # Remove conflicts at problematic timestamps
    conflicts_clean = conflicts_with_flag[~conflicts_with_flag['has_teleportation']].copy()
    conflicts_clean = conflicts_clean.drop(columns=['has_teleportation'])
    
    if verbose:
        print(f"Conflicts after filtering: {len(conflicts_clean):,}")
        print(f"Removed: {len(conflicts) - len(conflicts_clean):,} conflicts")
        print("="*70)
    
    return conflicts_clean


# ============================================================================
# MAIN FILTER FUNCTION (legacy - removes entire vehicles)
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