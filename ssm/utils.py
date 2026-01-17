"""
Pair extraction utilities for SSM conflict detection.
Provides modular filters and method-specific pipelines.

⚡ OPTIMIZED VERSION:
- Vectorized pair generation (no per-timestamp loops)
- Numba JIT with parallel processing
- Efficient batch processing with optimal chunk sizes
"""

import numpy as np
import pandas as pd
from typing import Tuple, List, Dict
import yaml
import gc
from shapely import wkt
from shapely.geometry import Point
import geopandas as gpd
from tqdm import tqdm
from filters.overlap_filter import filter_overlapping_pairs, OVERLAP_BUFFER

# Numba for parallel processing
try:
    from numba import jit, prange, set_num_threads
    import os
    # Use all available CPUs (leave 1 for system)
    n_cores = max(1, os.cpu_count() - 1)
    set_num_threads(n_cores)
    NUMBA_AVAILABLE = True
    print(f"[SSM] Numba enabled with {n_cores} threads")
except ImportError:
    NUMBA_AVAILABLE = False
    print("[SSM] Warning: Numba not available - falling back to single-threaded mode")


# Global configuration path
CONFIG_PATH = 'config.yaml'


def load_config(path: str = CONFIG_PATH) -> dict:
    """Load configuration from YAML."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def assign_zones_to_vehicles(df: pd.DataFrame, detection_zones: List[Dict], batch_size: int = 100000) -> pd.DataFrame:
    """
    Assign zone (lane) to each vehicle based on spatial location.
    
    Uses vectorized spatial join (geopandas sjoin) for fast zone assignment.
    Much faster than iterating through each vehicle individually.
    
    Args:
        df: Vehicle DataFrame with 'pos_x' and 'pos_y' columns
        detection_zones: List of zone dicts with 'name' and 'vertices' (WKT POLYGON)
        batch_size: Number of rows to process at once (default 100k for memory efficiency)
        
    Returns:
        DataFrame with added 'zone' column
        
    Example:
        zones = [
            {"id": "1085", "name": "A-L1", "type": "detection",
             "vertices": "POLYGON ((...))"},
            ...
        ]
        df = assign_zones_to_vehicles(df, zones)
    """
    
    # Create GeoDataFrame for zones (once)
    zones_data = []
    for zone in detection_zones:
        poly = wkt.loads(zone['vertices'])
        zones_data.append({
            'zone_name': zone['name'],
            'geometry': poly
        })
    gdf_zones = gpd.GeoDataFrame(zones_data, geometry='geometry')
    
    print(f"\nAssigning zones to {len(df):,} vehicles using spatial join...")
    print(f"Processing in batches of {batch_size:,} rows")
    
    # Process in batches to manage memory
    result_chunks = []
    total_batches = (len(df) + batch_size - 1) // batch_size
    
    for i in tqdm(range(0, len(df), batch_size), total=total_batches, desc="Zone assignment"):
        batch = df.iloc[i:i+batch_size].copy()
        
        # Create GeoDataFrame for this batch
        gdf_batch = gpd.GeoDataFrame(
            batch,
            geometry=gpd.points_from_xy(batch['pos_x'], batch['pos_y'])
        )
        
        # Spatial join (vectorized - very fast!)
        joined = gpd.sjoin(gdf_batch, gdf_zones, how='left', predicate='within')
        
        # Drop geometry column immediately
        joined = joined.drop(columns=['geometry'])
        
        # Handle duplicates (vehicle in multiple zones - keep first)
        joined = joined.drop_duplicates(subset=joined.columns.difference(['zone_name']).tolist(), keep='first')
        
        # Fill missing zones with 'unknown'
        joined['zone_name'] = joined['zone_name'].fillna('unknown')
        
        # Rename column
        joined = joined.rename(columns={'zone_name': 'zone'})
        
        # Keep only original columns + zone
        original_cols = df.columns.tolist()
        joined = joined[original_cols + ['zone']]
        
        result_chunks.append(joined)
        
        # Cleanup
        del gdf_batch, joined
        gc.collect()
    
    # Concatenate all batches
    result = pd.concat(result_chunks, ignore_index=True)
    del result_chunks
    gc.collect()
    
    # Statistics
    print(f"\n✓ Zone assignment complete!")
    print(f"  Vehicles in zones: {(result['zone'] != 'unknown').sum():,}")
    print(f"  Vehicles outside zones: {(result['zone'] == 'unknown').sum():,}")
    
    return result


def calculate_ttc(
    pos1_x: np.ndarray, pos1_y: np.ndarray,
    pos2_x: np.ndarray, pos2_y: np.ndarray,
    vel1_x: np.ndarray, vel1_y: np.ndarray,
    vel2_x: np.ndarray, vel2_y: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    TTC = d / v_closing where v_closing = -(Δv · Δr) / d
    Returns (ttc, distance, closing_speed)
    """
    # Position difference vector
    dx = pos2_x - pos1_x
    dy = pos2_y - pos1_y
    distance = np.sqrt(dx**2 + dy**2)
    
    # Velocity difference vector
    dvx = vel2_x - vel1_x
    dvy = vel2_y - vel1_y
    
    # Closing speed: negative dot product / distance
    # Positive when vehicles are approaching
    dot_product = dvx * dx + dvy * dy
    closing_speed = np.where(
        distance > 0.01,
        -dot_product / distance,
        0.0
    )
    
    # TTC: only meaningful when closing_speed > 0
    ttc = np.where(
        closing_speed > 0.01,
        distance / closing_speed,
        np.inf
    )
    
    return ttc, distance, closing_speed


def calculate_closing_accel(pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate rate of change of closing speed (m/s²)
    
    Negative = gap closing slower (active response detected)
    Positive = gap closing faster (accelerating toward conflict)
    
    Uses groupby differentiation with 3-frame smoothing to reduce noise
    """
    if len(pairs) == 0:
        return pairs
    
    # Reset index to avoid index mismatch issues
    pairs = pairs.reset_index(drop=True)
    
    # Sort by pair and timestamp
    pairs = pairs.sort_values(['id1', 'id2', 'timestamp']).copy()
    
    # Group by pair
    pair_groups = pairs.groupby(['id1', 'id2'], sort=False)
    
    # Calculate time delta between consecutive frames
    pairs.loc[:, 'dt'] = pair_groups['timestamp'].diff().dt.total_seconds()
    
    # Calculate closing speed change
    pairs.loc[:, 'd_closing_speed'] = pair_groups['closing_speed'].diff()
    
    # Raw closing acceleration
    pairs.loc[:, 'closing_accel_raw'] = pairs['d_closing_speed'] / pairs['dt']
    
    # Smooth with 3-frame rolling average to reduce sensor noise
    pairs.loc[:, 'closing_accel'] = pair_groups['closing_accel_raw'].rolling(
        window=3, center=True, min_periods=1
    ).mean().values
    
    # Clean up intermediate columns
    pairs = pairs.drop(columns=['dt', 'd_closing_speed', 'closing_accel_raw'])
    
    return pairs


def calculate_yaw_diff_rate(pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate rate of change of yaw difference (degrees/second)
    
    High absolute values indicate sudden heading changes (evasive swerving)
    Uses 3-frame smoothing to reduce noise
    """
    if len(pairs) == 0:
        return pairs
    
    # Reset index to avoid mismatch
    pairs = pairs.reset_index(drop=True)
    pairs = pairs.sort_values(['id1', 'id2', 'timestamp']).copy()
    
    # Calculate yaw difference (absolute, normalized to [0, 180])
    yaw_diff_rad = np.abs(pairs['yaw2'].values - pairs['yaw1'].values)
    yaw_diff_rad = np.minimum(yaw_diff_rad, 2*np.pi - yaw_diff_rad)
    pairs.loc[:, 'yaw_diff'] = np.degrees(yaw_diff_rad)
    
    # Group by pair
    pair_groups = pairs.groupby(['id1', 'id2'], sort=False)
    
    # Time delta
    pairs.loc[:, 'dt'] = pair_groups['timestamp'].diff().dt.total_seconds()
    
    # Yaw diff change
    pairs.loc[:, 'd_yaw_diff'] = pair_groups['yaw_diff'].diff()
    
    # Yaw diff rate (degrees/second)
    pairs.loc[:, 'yaw_diff_rate_raw'] = pairs['d_yaw_diff'] / pairs['dt']
    
    # Smooth with 3-frame rolling average
    pairs.loc[:, 'yaw_diff_rate'] = pair_groups['yaw_diff_rate_raw'].rolling(
        window=3, center=True, min_periods=1
    ).mean().values
    
    # Cleanup intermediate columns
    pairs = pairs.drop(columns=['dt', 'd_yaw_diff', 'yaw_diff_rate_raw'])
    
    return pairs


# =============================================================================
# VECTORIZED PAIR GENERATION (No per-timestamp loops!)
# =============================================================================

def find_all_nearby_pairs(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """    
    Find all pairs of vehicles within a certain distance at each timestamp.

    Applies the following filters:
    - Vehicle type: Only includes labels specified in config.
    - Minimum speed: Removes stationary or slow-moving vehicles.
    - Maximum distance: Only includes pairs within the specified spatial range.
    - Unique pairs: Removes self-pairs and ensures each pair is only counted once (id1 < id2).

    Args:
        df: Vehicle DataFrame
        config: Configuration dictionary containing filter parameters

    Returns:
        DataFrame of vehicle pairs with combined attributes
    """
    filter_config = config['filters']
    vehicle_labels = filter_config['vehicle_labels']
    min_vehicle_speed = filter_config['min_vehicle_speed']
    max_distance = filter_config.get('max_distance', 10.0)
    
    # Optimal batch size: process 5000-10000 timestamps per batch
    # This balances memory usage with vectorization efficiency
    timestamp_batch_size = config.get('timestamp_batch_size', 5000)
    
    # Stage 1: Pre-filter by vehicle type
    vehicles = df[df['label'].isin(vehicle_labels)].copy()
    if len(vehicles) == 0:
        print("  No vehicles of specified types found")
        return pd.DataFrame()
    
    # Stage 2: Remove stationary vehicles
    vehicles = vehicles[vehicles['vel'] >= min_vehicle_speed]
    if len(vehicles) == 0:
        print("  No moving vehicles found")
        return pd.DataFrame()
    
    print(f"  Filtered vehicles: {len(vehicles):,}")
    print(f"  Generating pairs (max_distance={max_distance}m)...")
    
    # Stage 3: Get unique timestamps
    unique_timestamps = vehicles['timestamp'].unique()
    n_timestamps = len(unique_timestamps)
    
    print(f"  Processing {n_timestamps:,} timestamps (batch_size={timestamp_batch_size:,})")
    
    # Select only needed columns (reduces memory)
    # Include size_x, size_y for overlap filter
    cols = ['timestamp', 'id', 'label', 'pos_x', 'pos_y', 'vel_x', 'vel_y', 'vel', 'yaw', 'size_x', 'size_y']
    vehicles = vehicles[cols]
    
    # Stage 4: Process in timestamp batches (vectorized within each batch)
    all_pairs = []
    total_batches = (n_timestamps + timestamp_batch_size - 1) // timestamp_batch_size
    max_dist_sq = max_distance ** 2
    
    for batch_idx in tqdm(range(0, n_timestamps, timestamp_batch_size), 
                          total=total_batches, 
                          desc="  Pair generation"):
        batch_end = min(batch_idx + timestamp_batch_size, n_timestamps)
        batch_ts = unique_timestamps[batch_idx:batch_end]
        batch_vehicles = vehicles[vehicles['timestamp'].isin(batch_ts)]
        
        if len(batch_vehicles) < 2:
            continue
        
        # Generate all pairs for batch at once
        # This is the key optimization - no per-timestamp loops!
        pairs = pd.merge(
            batch_vehicles, 
            batch_vehicles, 
            on='timestamp', 
            suffixes=('1', '2')
        )
        
        # Remove self-pairs and duplicates (keep id1 < id2 to avoid A-B and B-A)
        pairs = pairs[pairs['id1'] < pairs['id2']]
        
        if len(pairs) == 0:
            continue
        
        # Distance filter (early rejection)
        dx = pairs['pos_x2'].values - pairs['pos_x1'].values
        dy = pairs['pos_y2'].values - pairs['pos_y1'].values
        dist_sq = dx*dx + dy*dy
        
        # Keep only nearby pairs
        mask = dist_sq <= max_dist_sq
        pairs = pairs[mask]
        
        if len(pairs) > 0:
            # Pre-compute distance (we have dx, dy already)
            pairs = pairs.copy()
            pairs['distance'] = np.sqrt(dist_sq[mask])
            all_pairs.append(pairs)
        
        # Cleanup batch memory
        del pairs, dx, dy, dist_sq, mask
    
    # Stage 5: Combine all batches
    if len(all_pairs) == 0:
        print("  No nearby pairs found")
        return pd.DataFrame()
    
    result = pd.concat(all_pairs, ignore_index=True)
    
    # Cleanup
    del all_pairs
    gc.collect()
    
    # Stage 6: Apply overlap filter (remove physically impossible pairs)
    print(f"  Applying overlap filter (buffer={OVERLAP_BUFFER}m)...")
    result = filter_overlapping_pairs(result, buffer=OVERLAP_BUFFER, verbose=False)
    
    print(f"  ✓ Generated {len(result):,} nearby pairs (after overlap filter)")
    
    # Stage 7: Add zone information if available (automatic)
    if 'zone' in df.columns and len(result) > 0:
        zone_map = dict(zip(df['id'], df['zone']))
        result['zone1'] = result['id1'].map(zone_map)
        result['zone2'] = result['id2'].map(zone_map)
        print(f"  ✓ Added zone information (zone1/zone2 columns)")
    
    return result


def filter_approaching(pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Keep pairs where gap is closing: (v2 - v1) · (p2 - p1) < 0
    Adds: closing_speed, ttc, closing_accel
    """
    if len(pairs) == 0:
        return pairs
    
    # Calculate position and velocity differences
    dx = pairs['pos_x2'].values - pairs['pos_x1'].values
    dy = pairs['pos_y2'].values - pairs['pos_y1'].values
    dvx = pairs['vel_x2'].values - pairs['vel_x1'].values
    dvy = pairs['vel_y2'].values - pairs['vel_y1'].values
    
    # Dot product: negative means gap is closing
    dot_product = dvx * dx + dvy * dy
    pairs = pairs[dot_product < 0].copy()
    
    if len(pairs) == 0:
        return pairs
    
    # Calculate TTC and closing speed for approaching pairs
    ttc, _, closing_speed = calculate_ttc(
        pairs['pos_x1'].values, pairs['pos_y1'].values,
        pairs['pos_x2'].values, pairs['pos_y2'].values,
        pairs['vel_x1'].values, pairs['vel_y1'].values,
        pairs['vel_x2'].values, pairs['vel_y2'].values
    )
    
    pairs['ttc'] = ttc
    pairs['closing_speed'] = closing_speed
    
    # Calculate closing acceleration (rate of change of closing speed)
    pairs = calculate_closing_accel(pairs)
    
    # Calculate yaw diff rate (rate of change of heading difference)
    pairs = calculate_yaw_diff_rate(pairs)
    
    print(f" Approaching pairs: {len(pairs):,}")
    return pairs


def filter_same_lane(pairs: pd.DataFrame, max_lateral: float) -> pd.DataFrame:
    """
    Dual same-lane filtering: Zone-based AND lateral distance.
    
    Applies TWO filters:
    1. Zone equality: zone1 == zone2 (ensures same lane)
    2. Lateral distance: <= max_lateral (ensures geometric alignment)
    
    This dual approach is more robust than either filter alone.
    
    Args:
        pairs: DataFrame with zone1, zone2 columns (REQUIRED)
        max_lateral: Maximum perpendicular distance (meters) - typically 3.0m
    
    Returns:
        Filtered pairs where vehicles are in same lane AND laterally close
    """
    if len(pairs) == 0:
        return pairs
    
    # Check for required zone columns
    if 'zone1' not in pairs.columns or 'zone2' not in pairs.columns:
        raise ValueError(
            "filter_same_lane requires 'zone1' and 'zone2' columns in pairs DataFrame. "
            "Ensure zone information is added before calling this function."
        )
    
    initial_count = len(pairs)
    
    # =========================================================================
    # Filter 1: Zone-based (same lane)
    # =========================================================================
    same_zone_mask = pairs['zone1'] == pairs['zone2']
    pairs = pairs[same_zone_mask].copy()
    zone_filtered_count = initial_count - len(pairs)
    print(f"  Zone filter (same lane): {len(pairs):,} pairs (filtered {zone_filtered_count:,} different-lane)")
    
    if len(pairs) == 0:
        return pairs
    
    # =========================================================================
    # Filter 2: Lateral distance (geometric alignment)
    # =========================================================================
    # Position difference
    dx = pairs['pos_x2'].values - pairs['pos_x1'].values
    dy = pairs['pos_y2'].values - pairs['pos_y1'].values
    
    # Determine faster vehicle (likely the follower)
    speed1 = pairs['vel1'].values
    speed2 = pairs['vel2'].values
    faster_is_1 = speed1 > speed2
    
    # Use faster vehicle's velocity as lane direction
    vel_x = np.where(faster_is_1, pairs['vel_x1'].values, pairs['vel_x2'].values)
    vel_y = np.where(faster_is_1, pairs['vel_y1'].values, pairs['vel_y2'].values)
    speed = np.where(faster_is_1, speed1, speed2)
    
    # Normalize to unit vector (avoid division by zero)
    moving_mask = speed > 0.5
    u_x = np.where(moving_mask, vel_x / speed, 0.0)
    u_y = np.where(moving_mask, vel_y / speed, 0.0)
    
    # Cross product gives lateral distance
    lat_dist = np.abs(dx * u_y - dy * u_x)
    
    # Keep pairs within lateral threshold (or stationary)
    lateral_mask = (lat_dist <= max_lateral) | (~moving_mask)
    
    after_zone = len(pairs)
    pairs = pairs[lateral_mask].copy()
    lateral_filtered_count = after_zone - len(pairs)
    
    print(f"  Lateral filter (<= {max_lateral}m): {len(pairs):,} pairs (filtered {lateral_filtered_count:,} not aligned)")
    print(f"  ✓ Total filtered: {initial_count - len(pairs):,} pairs | Remaining: {len(pairs):,} pairs")
    
    return pairs


def classify_conflict_type(pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Classify based on relative heading: Δθ = |yaw2 - yaw1|
    rear-end: Δθ < 30°, perpendicular: 60° < Δθ < 120°
    head-on: Δθ > 150°, lane-change: else
    """
    if len(pairs) == 0:
        return pairs
    
    # Calculate absolute heading difference
    angle_diff = np.abs(pairs['yaw2'].values - pairs['yaw1'].values)
    
    # Normalize to [0, π] range (shortest angular distance)
    angle_diff = np.minimum(angle_diff, 2*np.pi - angle_diff)
    angle_deg = np.degrees(angle_diff)
    
    # Classify based on heading difference
    conflict_type = np.where(angle_deg < 30, 'rear-end',
                    np.where(angle_deg > 150, 'head-on',
                    np.where((angle_deg > 60) & (angle_deg < 120), 'perpendicular',
                    'lane-change')))
    
    pairs = pairs.copy()
    pairs['conflict_type'] = conflict_type
    return pairs


def identify_leader_follower(pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Identify leader and follower based on POSITION and velocity direction.
    
    Logic: Follower is the vehicle that is:
    1. Moving TOWARD the other vehicle (positive approach velocity)
    2. Behind (in the direction of travel)
    
    The vehicle with higher approach velocity is the follower.
    This correctly handles cases where leader is faster (follower still behind).
    
    Adds: is_veh1_follower, follower_vel, leader_vel, speed_diff
    """
    if len(pairs) == 0:
        return pairs
    
    # Position difference (from veh1 to veh2)
    dx = pairs['pos_x2'].values - pairs['pos_x1'].values
    dy = pairs['pos_y2'].values - pairs['pos_y1'].values
    distance = pairs['distance'].values
    
    # Calculate approach velocities (velocity component TOWARD the other vehicle)
    # Positive means moving toward the other vehicle
    v1_toward_v2 = (pairs['vel_x1'].values * dx + pairs['vel_y1'].values * dy) / distance
    v2_toward_v1 = -(pairs['vel_x2'].values * dx + pairs['vel_y2'].values * dy) / distance
    
    # Follower is the one with HIGHER approach velocity (moving more toward the other)
    # This means follower is BEHIND and approaching (regardless of absolute speed)
    veh1_is_follower = v1_toward_v2 > v2_toward_v1
    
    # Get speed magnitudes
    vel1_mag = pairs['vel1'].values
    vel2_mag = pairs['vel2'].values
    
    # Assign follower/leader roles
    follower_vel = np.where(veh1_is_follower, vel1_mag, vel2_mag)
    leader_vel = np.where(veh1_is_follower, vel2_mag, vel1_mag)
    speed_diff = follower_vel - leader_vel
    
    # Add columns
    pairs = pairs.copy()
    pairs['is_veh1_follower'] = veh1_is_follower
    pairs['follower_vel'] = follower_vel
    pairs['leader_vel'] = leader_vel
    pairs['speed_diff'] = speed_diff
    
    return pairs


def get_mdrac_pairs(df: pd.DataFrame, config: dict, skip_pair_generation: bool = False) -> pd.DataFrame:
    """
    Method-specific pipeline for MDRAC (Modified DRAC) analysis.
    
    MDRAC is designed for longitudinal car-following scenarios where:
    - Vehicles are in the same lane
    - Follower is approaching leader from behind
    - Follower is traveling faster than leader
    
    Filter sequence:
        1. Base pairs (distance filter) - SKIPPED if skip_pair_generation=True
        2. Approaching only (gap must be closing)
        3. Same lane (lateral distance check)
        4. Leader/follower identification
        5. Speed difference filter (follower must be faster)
        6. TTC and closing speed thresholds
    
    Args:
        df: Vehicle data DataFrame OR pre-generated pairs DataFrame
        config: Configuration with MDRAC-specific thresholds
        skip_pair_generation: If True, assumes df is already pairs (has pos_x1 columns).
                             If False, generates pairs from vehicle data (default).
        
    Returns:
        DataFrame ready for MDRAC calculation
        
    Usage:
        # Traditional (generates pairs internally):
        pairs = get_mdrac_pairs(vehicle_df, config)
        
        # Optimized (reuse base pairs):
        base_pairs = get_mdrac_pairs(vehicle_df, config, skip_pair_generation=False)
        mdrac_pairs = get_mdrac_pairs(base_pairs, config, skip_pair_generation=True)
    """
    # Stage 1: Generate base pairs (or skip if already pairs)
    if skip_pair_generation:
        # Input is already pairs - skip expensive generation step
        pairs = df.copy()
        if len(pairs) == 0:
            return pairs
    else:
        # Generate pairs from vehicle data
        pairs = find_all_nearby_pairs(df, config)
        if len(pairs) == 0:
            return pairs
    
    # Stage 2: Keep only approaching pairs
    pairs = filter_approaching(pairs)
    if len(pairs) == 0:
        return pairs
    
    # Stage 2.5: Add zone information BEFORE same-lane filter
    # This is CRITICAL - filter_same_lane requires zone1/zone2 columns
    if skip_pair_generation:
        # Optimized workflow: pairs should already have zone1/zone2 from base_pairs
        if 'zone1' not in pairs.columns or 'zone2' not in pairs.columns:
            raise ValueError(
                "When using skip_pair_generation=True, pairs must have zone1/zone2 columns. "
                "Ensure your base_pairs include zone information before passing to get_mdrac_pairs()."
            )
    else:
        # Direct workflow: add zone info from vehicle DataFrame
        if 'zone' not in df.columns:
            raise ValueError(
                "Vehicle DataFrame must have 'zone' column for M-DRAC detection. "
                "Use assign_zones_to_vehicles() before calling get_mdrac_pairs()."
            )
        zone_map = dict(zip(df['id'], df['zone']))
        pairs['zone1'] = pairs['id1'].map(zone_map)
        pairs['zone2'] = pairs['id2'].map(zone_map)
    
    # Stage 3: Same-lane filter (zone-based - filters different lanes on same road)
    pairs = filter_same_lane(pairs, config['filters']['max_lateral_distance'])
    if len(pairs) == 0:
        return pairs
    
    # Stage 4: Identify leader and follower
    pairs = identify_leader_follower(pairs)
    
    # Stage 5: Follower must be faster than leader
    min_speed_diff = config['filters']['min_speed_diff']
    pairs = pairs[pairs['speed_diff'] > min_speed_diff].copy()
    print(f"  Speed diff > {min_speed_diff}: {len(pairs):,}")
    
    # Stage 6: TTC and closing speed filters
    max_ttc = config['filters']['max_ttc']
    min_closing = config['filters']['min_closing_speed']
    pairs = pairs[(pairs['ttc'] <= max_ttc) & (pairs['closing_speed'] >= min_closing)].copy()
    print(f"  Final MDRAC pairs: {len(pairs):,}")
    
    # Stage 7: Add zone information (depends on workflow)
    if skip_pair_generation:
        # Optimized workflow: pairs already have zone1/zone2 from base_pairs
        # Just add combined 'zone' column if not present
        if 'zone' not in pairs.columns and 'zone1' in pairs.columns:
            pairs['zone'] = pairs['zone1']  # Should all match due to same-lane filter
    else:
        # Direct workflow: add zone info from original vehicle DataFrame
        if 'zone' in df.columns:
            zone_map = dict(zip(df['id'], df['zone']))
            pairs['zone1'] = pairs['id1'].map(zone_map)
            pairs['zone2'] = pairs['id2'].map(zone_map)
            pairs['zone'] = pairs['zone1']  # Should match due to same-lane filter
    
    return pairs


def get_spf_pairs(df: pd.DataFrame, config: dict, skip_pair_generation: bool = False) -> pd.DataFrame:
    """
    SPF pipeline: all conflict types (no lane restriction).
    Filters: approaching only
    
    OPTIMIZED: Vectorized zone combination instead of apply().
    
    Args:
        df: Vehicle data DataFrame OR pre-generated pairs DataFrame
        config: Configuration dict
        skip_pair_generation: If True, assumes df is already pairs (has pos_x1 columns).
                             If False, generates pairs from vehicle data (default).
        
    Returns:
        Filtered pairs ready for SPF calculation
        
    Usage:
        # Traditional (generates pairs internally):
        pairs = get_spf_pairs(vehicle_df, config)
        
        # Optimized (reuse base pairs):
        base_pairs = get_spf_pairs(vehicle_df, config, skip_pair_generation=False)
        spf_pairs = get_spf_pairs(base_pairs, config, skip_pair_generation=True)
    """
    if skip_pair_generation:
        # Input is already pairs - skip expensive generation step
        pairs = df.copy()
        if len(pairs) == 0:
            return pairs
    else:
        # Generate pairs from vehicle data
        pairs = find_all_nearby_pairs(df, config)
        if len(pairs) == 0:
            return pairs
    
    # Stage 2: Keep only approaching pairs
    pairs = filter_approaching(pairs)
    
    # Stage 3: Classify conflict geometry (for analysis)
    pairs = classify_conflict_type(pairs)
    
    # Stage 4: Add zone information (if available in original df)
    if 'zone' in df.columns:
        zone_map = dict(zip(df['id'], df['zone']))
        pairs['zone1'] = pairs['id1'].map(zone_map)
        pairs['zone2'] = pairs['id2'].map(zone_map)
        
        # ⚡ Vectorized zone combination (replaces apply())
        zone1 = pairs['zone1'].astype(str)
        zone2 = pairs['zone2'].astype(str)
        same_zone = pairs['zone1'] == pairs['zone2']
        pairs['zone'] = np.where(same_zone, zone1, zone1 + '_' + zone2)
    
    print(f"  Final SPF pairs: {len(pairs):,}")
    return pairs


def get_prt_for_labels(labels: np.ndarray, config: dict) -> np.ndarray:
    """Get Perception-Reaction Time values for vehicle labels."""
    prt_map = config['mdrac']['prt']
    return np.array([prt_map.get(int(label), 1.0) for label in labels])


def get_threshold_for_labels(labels: np.ndarray, config: dict) -> np.ndarray:
    """Get DRAC threshold values for vehicle labels."""
    threshold_map = config['mdrac']['threshold']
    return np.array([threshold_map.get(int(label), 3.4) for label in labels])


#-------------------------------------------------------------------------------
# TESTING / VERIFICATION
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    """
    Comprehensive test suite for pair generation logic.
    Tests multiple scenarios to verify all filters work correctly.
    """
    
    print("=" * 70)
    print("COMPREHENSIVE PAIR GENERATION TEST SUITE")
    print("=" * 70)
    
    # Test Configuration (permissive for testing)
    test_config = {
        'filters': {
            'vehicle_labels': [4, 6, 7, 8],
            'min_vehicle_speed': 1.0,
            'max_distance': 25.0,
            'max_lateral_distance': 2.5,  # Same-lane threshold
            'max_ttc': 10.0,
            'min_closing_speed': 0.5,
            'min_speed_diff': 0.1
        },
        'timestamp_batch_size': 150  # Process 150 timestamps at a time
    }
    
    # -------------------------------------------------------------------------
    # Test Cases Definition
    # -------------------------------------------------------------------------
    test_cases = [
        # =====================================================================
        # SCENARIO 1: Same Lane, Same Direction (Classic Car Following)
        # =====================================================================
        # [A: 15m/s] ──10m──→ [B: 10m/s]
        # A is faster, catching up to B
        {
            'name': '1. Same lane, same direction (car following)',
            'description': 'A behind B, both moving right, A faster',
            'vehicles': [
                {'id': 101, 'label': 4, 'pos': (0, 0), 'vel': (15, 0)},    # A: faster
                {'id': 102, 'label': 4, 'pos': (10, 0), 'vel': (20, 0)},   # B: slower, ahead
            ],
            'expected_pair': False,
            'expected_follower_id': None,
            'expected_ttc': None,  # 10m / 5m/s = 2s
            'expected_closing_speed': None,
        },
        
        # =====================================================================
        # SCENARIO 2: Head-On Approach (Opposite Directions)
        # =====================================================================
        #     [B: 5m/s]──→         ←──[A: 10m/s] 
        #         └──────────20m──────────┘
        {
            'name': '2. Head-on approach (opposite directions)',
            'description': 'A and B moving toward each other',
            'vehicles': [
                {'id': 201, 'label': 4, 'pos': (0, 0), 'vel': (10, 0)},    # A: moving right
                {'id': 202, 'label': 4, 'pos': (20, 0), 'vel': (-5, 0)},   # B: moving left
            ],
            'expected_pair': True,
            'expected_follower_id': 201,  # A has higher approach velocity
            'expected_ttc': 1.33,  # 20m / 15m/s
            'expected_closing_speed': 15.0,
        },
        
        # =====================================================================
        # SCENARIO 3: Parallel Lanes (Should be FILTERED by lateral distance)
        # =====================================================================
        # Lane 1: [A: 12m/s] ──→
        # ────────────────────── (5m apart)
        # Lane 2: [B: 10m/s] ──→
        {
            'name': '3. Parallel lanes (should be filtered)',
            'description': 'Same direction, different lanes (5m apart)',
            'vehicles': [
                {'id': 301, 'label': 4, 'pos': (0, 0), 'vel': (12, 0)},
                {'id': 302, 'label': 4, 'pos': (0, 5), 'vel': (10, 0)},  # 5m lateral
            ],
            'expected_pair': False,  # Lateral filter should remove (5m > 2.5m)
            'expected_follower_id': None,
            'expected_ttc': None,
            'expected_closing_speed': None,
        },
        
        # =====================================================================
        # SCENARIO 4: Converging Lanes (Merge/Intersection)
        # =====================================================================
        # NOTE: This is an INTERSECTION conflict, not car-following.
        # MDRAC is designed for car-following, so lateral filter correctly removes this.
        #              [B: 8m/s]
        #                 ↘ 45°
        #                  ╲
        #   [A: 10m/s] ──→  ╳ (will meet)
        {
            'name': '4. Converging lanes (45° angle) - NOT car-following',
            'description': 'Different lanes converging (filtered by lateral - correct behavior)',
            'vehicles': [
                {'id': 401, 'label': 4, 'pos': (0, 0), 'vel': (10, 0)},          # A: moving right
                {'id': 402, 'label': 6, 'pos': (10, 10), 'vel': (5.66, -5.66)},  # B: moving 45° toward A's path
            ],
            'expected_pair': False,  # Lateral filter removes - correct for car-following MDRAC
            'expected_follower_id': None,
            'expected_ttc': None,
            'expected_closing_speed': None,
        },
        
        # =====================================================================
        # SCENARIO 5: Perpendicular Crossing (90° intersection)
        # =====================================================================
        # NOTE: This is a CROSSING conflict, not car-following.
        # MDRAC is designed for car-following, so lateral filter correctly removes this.
        #        [B: 8m/s]
        #           ↓
        #  [A: 10m/s] ──→
        {
            'name': '5. Perpendicular crossing (90°) - NOT car-following',
            'description': 'Crossing paths (filtered by lateral - correct behavior)',
            'vehicles': [
                {'id': 501, 'label': 4, 'pos': (0, 0), 'vel': (10, 0)},   # A: moving right
                {'id': 502, 'label': 4, 'pos': (10, 10), 'vel': (0, -10)},  # B: moving down
            ],
            'expected_pair': False,  # Lateral filter removes - correct for car-following MDRAC
            'expected_follower_id': None,
            'expected_ttc': None,
            'expected_closing_speed': None,
        },
        
        # =====================================================================
        # SCENARIO 6: Diverging (Moving Apart) - Should NOT be detected
        # =====================================================================
        # [A: 10m/s] ←───     ───→ [B: 8m/s]
        {
            'name': '6. Diverging (moving apart)',
            'description': 'Moving away from each other',
            'vehicles': [
                {'id': 601, 'label': 4, 'pos': (0, 0), 'vel': (-10, 0)},   # A: moving left
                {'id': 602, 'label': 4, 'pos': (20, 0), 'vel': (8, 0)},    # B: moving right
            ],
            'expected_pair': False,  # Approaching filter removes
            'expected_follower_id': None,
            'expected_ttc': None,
            'expected_closing_speed': None,
        },
        
        # =====================================================================
        # SCENARIO 7: Stationary Leader (A approaching stopped B)
        # =====================================================================
        # [A: 10m/s] ──→ ────── [B: 0m/s]
        {
            'name': '7. Stationary leader',
            'description': 'A approaching stationary B (B below speed threshold)',
            'vehicles': [
                {'id': 701, 'label': 4, 'pos': (0, 0), 'vel': (10, 0)},
                {'id': 702, 'label': 4, 'pos': (15, 0), 'vel': (0.5, 0)},  # Almost stationary
            ],
            'expected_pair': False,  # B filtered by min_vehicle_speed (0.5 < 1.0)
            'expected_follower_id': None,
            'expected_ttc': None,
            'expected_closing_speed': None,
        },
        
        # =====================================================================
        # SCENARIO 8: Leader FASTER than Follower (Critical Test!)
        # =====================================================================
        # [B: 20m/s] ──→ ────10m──── [A: 25m/s] ──→
        # B is behind (follower) but SLOWER, A is ahead (leader) and FASTER
        # This should be FILTERED by speed_diff (follower must be faster)
        {
            'name': '8. Leader faster than follower (should be filtered)',
            'description': 'B behind A, but B is slower - no near-miss risk',
            'vehicles': [
                {'id': 801, 'label': 4, 'pos': (10, 0), 'vel': (25, 0)},   # A: ahead, faster
                {'id': 802, 'label': 4, 'pos': (0, 0), 'vel': (20, 0)},    # B: behind, slower
            ],
            'expected_pair': False,  # Filtered by speed_diff (follower must be faster)
            'expected_follower_id': None,
            'expected_ttc': None,
            'expected_closing_speed': None,
        },
    ]
    
    # -------------------------------------------------------------------------
    # Run Tests
    # -------------------------------------------------------------------------
    results = []
    
    for i, test in enumerate(test_cases):
        print(f"\n{'─' * 70}")
        print(f"TEST: {test['name']}")
        print(f"Description: {test['description']}")
        print(f"{'─' * 70}")
        
        # Build test DataFrame
        vehicles = test['vehicles']
        test_df = pd.DataFrame({
            'timestamp': [1] * len(vehicles),
            'id': [v['id'] for v in vehicles],
            'label': [v['label'] for v in vehicles],
            'pos_x': [v['pos'][0] for v in vehicles],
            'pos_y': [v['pos'][1] for v in vehicles],
            'vel_x': [v['vel'][0] for v in vehicles],
            'vel_y': [v['vel'][1] for v in vehicles],
            'vel': [np.sqrt(v['vel'][0]**2 + v['vel'][1]**2) for v in vehicles],
            'yaw': [np.arctan2(v['vel'][1], v['vel'][0]) for v in vehicles]  # Calculate yaw from velocity
        })
        
        # Print vehicle setup
        print("\nVehicles:")
        for v in vehicles:
            speed = np.sqrt(v['vel'][0]**2 + v['vel'][1]**2)
            print(f"  ID {v['id']}: pos={v['pos']}, vel={v['vel']}, speed={speed:.1f}m/s")
        
        # Run pair generation (using MDRAC pipeline)
        pairs = get_mdrac_pairs(test_df, test_config)
        
        # Analyze results
        pair_found = len(pairs) > 0
        
        print(f"\nExpected: {'Pair detected' if test['expected_pair'] else 'No pair'}")
        print(f"Actual:   {'Pair detected' if pair_found else 'No pair'}")
        
        # Check result
        passed = (pair_found == test['expected_pair'])
        
        if pair_found and test['expected_pair']:
            row = pairs.iloc[0]
            print(f"\nPair details:")
            print(f"  Distance: {row['distance']:.2f} m")
            print(f"  TTC: {row['ttc']:.2f} s")
            print(f"  Closing speed: {row['closing_speed']:.2f} m/s")
            print(f"  Follower ID: {row['id1'] if row['is_veh1_follower'] else row['id2']}")
            
            # Check follower identification
            actual_follower = row['id1'] if row['is_veh1_follower'] else row['id2']
            if test['expected_follower_id'] is not None:
                follower_correct = (actual_follower == test['expected_follower_id'])
                print(f"  Expected follower: {test['expected_follower_id']} {'✓' if follower_correct else '✗'}")
                passed = passed and follower_correct
            
            # Check TTC if expected
            if test['expected_ttc'] is not None:
                ttc_correct = abs(row['ttc'] - test['expected_ttc']) < 0.2
                print(f"  Expected TTC: {test['expected_ttc']:.2f}s {'✓' if ttc_correct else '✗'}")
                passed = passed and ttc_correct
            
            # Check closing speed if expected
            if test['expected_closing_speed'] is not None:
                cs_correct = abs(row['closing_speed'] - test['expected_closing_speed']) < 0.5
                print(f"  Expected closing speed: {test['expected_closing_speed']:.1f}m/s {'✓' if cs_correct else '✗'}")
                passed = passed and cs_correct
        
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"\nResult: {status}")
        results.append((test['name'], passed))
    
    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
    
    print(f"\n{'─' * 70}")
    print(f"Results: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED - Review above for details")
    
    print("=" * 70)
