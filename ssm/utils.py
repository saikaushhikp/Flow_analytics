"""
Utility functions for SSM (Surrogate Safety Measures) analysis.

Provides TTC-based pair extraction for vehicle-vehicle conflict detection.
Optimized with vectorized operations for performance.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
import yaml
import gc


def load_config(config_path: str = 'config.yaml') -> dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config.yaml file
        
    Returns:
        Configuration dictionary
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def calculate_ttc_vectorized(
    pos1_x: np.ndarray, pos1_y: np.ndarray,
    pos2_x: np.ndarray, pos2_y: np.ndarray,
    vel1_x: np.ndarray, vel1_y: np.ndarray,
    vel2_x: np.ndarray, vel2_y: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Time-to-Collision (TTC) for vehicle pairs (vectorized).
    
    Uses projected closing speed: v_closing = -(Δv⃗ · Δr⃗) / d
    TTC = d / v_closing (only if v_closing > 0)
    
    Args:
        pos1_x, pos1_y: Position of vehicle 1 (meters)
        pos2_x, pos2_y: Position of vehicle 2 (meters)
        vel1_x, vel1_y: Velocity of vehicle 1 (m/s)
        vel2_x, vel2_y: Velocity of vehicle 2 (m/s)
        
    Returns:
        (ttc, distance, closing_speed) where ttc is in seconds, distance in meters,
        and closing_speed in m/s (positive if closing, negative if diverging)
    """
    # Position difference vector (from veh1 to veh2)
    dx = pos2_x - pos1_x
    dy = pos2_y - pos1_y
    distance = np.sqrt(dx**2 + dy**2)
    
    # Rate of change of gap vector: d/dt(p2 - p1) = v2 - v1
    dvx = vel2_x - vel1_x  # v2 - v1 (NOT v1 - v2!)
    dvy = vel2_y - vel1_y
    
    # Closing speed = rate of change of distance (negative = closing)
    # d/dt(|d|) = d · d'/|d| = d · (v2-v1) / |d|
    # If this is negative, distance is decreasing (closing)
    # We define closing_speed as POSITIVE when closing
    dot_product = dvx * dx + dvy * dy
    
    # Avoid division by zero
    closing_speed = np.where(
        distance > 0.1,
        -dot_product / distance,  # Negative of rate = positive when closing
        0.0
    )
    
    # TTC calculation: only meaningful when closing (closing_speed > 0)
    ttc = np.where(
        closing_speed > 0.01,
        distance / closing_speed,
        np.inf
    )
    
    return ttc, distance, closing_speed


def find_vehicle_vehicle_pairs(
    df: pd.DataFrame,
    config: Optional[dict] = None,
    config_path: str = 'config.yaml'
) -> pd.DataFrame:
    """
    Extract vehicle-vehicle pairs with potential conflicts using vectorized operations.
    
    OPTIMIZED VERSION with early distance filtering (timestamp-by-timestamp).
    
    Filter Pipeline:
    1. Pre-filter: Keep only vehicle labels (removes pedestrians, bicycles, etc.)
    2. Speed filter: v ≥ min_vehicle_speed
    3. Distance-filtered pair generation: Process each timestamp separately
       - Create pairs for timestamp
       - Remove self-pairs (id1 < id2)
       - Apply distance filter IMMEDIATELY (max_distance)
       - Accumulate only nearby pairs
    4. Approaching filter: Δv⃗·Δr⃗ < 0 (gap is closing)
    5. Lateral distance filter: Same-lane check (max_lateral_distance)
    6. Leader/Follower identification: Based on approach velocity
    7. Speed difference filter: follower_vel > leader_vel + min_speed_diff
    8. TTC calculation and filter: TTC ≤ max_ttc
    9. Closing speed filter: v_closing ≥ min_closing_speed
    
    Performance Note:
    Previous version created ALL pairs first (O(N²)), then filtered.
    New version filters by distance DURING pair creation, avoiding
    creation of millions of pairs that would be discarded.
    Expected speedup: 10-50x depending on density.
    
    Args:
        df: DataFrame with columns: id, label, timestamp, pos_x, pos_y, vel_x, vel_y, vel
        config: Configuration dictionary (optional)
        config_path: Path to config.yaml if config not provided
        
    Returns:
        DataFrame with vehicle pairs including ttc, distance, closing_speed, and
        leader/follower information
    """
    if config is None:
        config = load_config(config_path)
    
    filter_config = config['filters']
    vehicle_labels = filter_config['vehicle_labels']
    min_vehicle_speed = filter_config['min_vehicle_speed']
    max_ttc = filter_config['max_ttc']
    min_closing_speed = filter_config['min_closing_speed']
    min_speed_diff = filter_config['min_speed_diff']
    
    # Empty result schema
    empty_columns = [
        'timestamp', 'id1', 'id2', 'label1', 'label2',
        'pos1_x', 'pos1_y', 'pos2_x', 'pos2_y',
        'vel1_x', 'vel1_y', 'vel2_x', 'vel2_y',
        'vel1', 'vel2', 'distance', 'ttc', 'closing_speed',
        'is_veh1_follower', 'follower_vel', 'leader_vel', 'speed_diff'
    ]
    
    # =========================================================================
    # Stage 1: Pre-filter to keep only specified vehicle labels
    # =========================================================================
    vehicles = df[df['label'].isin(vehicle_labels)].copy()
    
    if len(vehicles) == 0:
        return pd.DataFrame(columns=empty_columns)
    
    # =========================================================================
    # Stage 2: Filter moving vehicles (removes stationary/parked vehicles)
    # =========================================================================
    vehicles = vehicles[vehicles['vel'] >= min_vehicle_speed]
    
    if len(vehicles) == 0:
        return pd.DataFrame(columns=empty_columns)
    
    print(f"  Vehicles after filtering: {len(vehicles):,} rows")
    
    # =========================================================================
    # Stage 3: Distance-filtered pair generation (timestamp-by-timestamp)
    # =========================================================================
    # Process each timestamp separately to apply distance filter early
    # This avoids creating millions of pairs that will be filtered anyway
    
    max_distance = filter_config.get('max_distance', 15.0)
    max_lateral_distance = filter_config.get('max_lateral_distance', 2.5)
    
    print(f"  Generating pairs with distance filter (max_distance={max_distance}m)...")
    
    all_pairs = []
    unique_timestamps = vehicles['timestamp'].unique()
    
    for ts in unique_timestamps:
        ts_vehicles = vehicles[vehicles['timestamp'] == ts].copy()
        
        if len(ts_vehicles) < 2:
            continue
        
        # Create pairs only for this timestamp
        ts_slim = ts_vehicles[['timestamp', 'id', 'label', 'pos_x', 'pos_y', 
                               'vel_x', 'vel_y', 'vel']].copy()
        
        ts_pairs = pd.merge(
            ts_slim, 
            ts_slim, 
            on='timestamp', 
            suffixes=('1', '2')
        )
        
        # Remove self-pairs and duplicates (id1 < id2)
        ts_pairs = ts_pairs[ts_pairs['id1'] < ts_pairs['id2']]
        
        if len(ts_pairs) == 0:
            continue
        
        # Apply distance filter IMMEDIATELY (before accumulating)
        dx = ts_pairs['pos_x2'].values - ts_pairs['pos_x1'].values
        dy = ts_pairs['pos_y2'].values - ts_pairs['pos_y1'].values
        dist_sq = dx**2 + dy**2
        
        distance_mask = dist_sq <= (max_distance ** 2)
        ts_pairs = ts_pairs[distance_mask]
        
        if len(ts_pairs) > 0:
            all_pairs.append(ts_pairs)
        
        # Cleanup this timestamp's data
        del ts_vehicles, ts_slim, ts_pairs
    
    # Combine all timestamp pairs
    if len(all_pairs) == 0:
        return pd.DataFrame(columns=empty_columns)
    
    pairs = pd.concat(all_pairs, ignore_index=True)
    del all_pairs
    gc.collect()
    
    print(f"  Total pairs within {max_distance}m: {len(pairs):,}")
    
    # =========================================================================
    # Stage 5: Approaching filter
    # =========================================================================
    # Rate of change of gap = d/dt(p2 - p1) = v2 - v1
    # If (v2 - v1) · (p2 - p1) < 0, the gap is shrinking (approaching)
    dx = pairs['pos_x2'].values - pairs['pos_x1'].values
    dy = pairs['pos_y2'].values - pairs['pos_y1'].values
    dvx = pairs['vel_x2'].values - pairs['vel_x1'].values  # v2 - v1 (NOT v1 - v2!)
    dvy = pairs['vel_y2'].values - pairs['vel_y1'].values
    
    # Negative dot product means gap is shrinking (vehicles approaching)
    dot_product = dvx * dx + dvy * dy
    approaching_mask = dot_product < 0
    
    pairs = pairs[approaching_mask]
    
    if len(pairs) == 0:
        return pd.DataFrame(columns=empty_columns)
    
    print(f"  Approaching pairs: {len(pairs):,}")
    
    # Recompute for filtered data
    dx = pairs['pos_x2'].values - pairs['pos_x1'].values
    dy = pairs['pos_y2'].values - pairs['pos_y1'].values
    distance = np.sqrt(dx**2 + dy**2)
    
    # =========================================================================
    # Stage 5.5: Lateral distance filter (same-lane check)
    # =========================================================================
    # Uses the follower's velocity direction as "lane direction"
    # Lateral distance = perpendicular distance between vehicles
    # Formula: lat_dist = |dx × u_y - dy × u_x| where u is lane unit vector
    #
    # We need to identify follower first to get their velocity direction
    # For now, use the faster vehicle's velocity as lane direction
    speed1 = pairs['vel1'].values
    speed2 = pairs['vel2'].values
    faster_is_1 = speed1 > speed2
    
    # Get velocity of faster vehicle (likely follower)
    vel_x = np.where(faster_is_1, pairs['vel_x1'].values, pairs['vel_x2'].values)
    vel_y = np.where(faster_is_1, pairs['vel_y1'].values, pairs['vel_y2'].values)
    speed = np.where(faster_is_1, speed1, speed2)
    
    # Filter: need minimum speed to define lane direction (avoid div by zero)
    moving_mask = speed > 0.5
    
    # Unit vector in lane direction
    u_x = np.where(moving_mask, vel_x / speed, 0.0)
    u_y = np.where(moving_mask, vel_y / speed, 0.0)
    
    # Lateral distance using cross product: |d × u|
    lat_dist = np.abs(dx * u_y - dy * u_x)
    
    # Apply lateral filter (skip for stationary pairs)
    lateral_mask = (lat_dist <= max_lateral_distance) | (~moving_mask)
    
    pairs = pairs[lateral_mask]
    distance = distance[lateral_mask]
    
    if len(pairs) == 0:
        return pd.DataFrame(columns=empty_columns)
    
    print(f"  Pairs in same lane (lat_dist <= {max_lateral_distance}m): {len(pairs):,}")
    
    # Recompute dx/dy for filtered data
    dx = pairs['pos_x2'].values - pairs['pos_x1'].values
    dy = pairs['pos_y2'].values - pairs['pos_y1'].values
    
    # =========================================================================
    # Stage 6: Identify leader and follower
    # =========================================================================
    # The vehicle moving faster TOWARD the other is the follower
    # d = p2 - p1 points from veh1 to veh2
    # v1 · d > 0 means v1 has component in direction of d (toward veh2)
    # v2 · d < 0 (i.e., -v2 · d > 0) means v2 has component toward veh1
    v1_toward_v2 = (pairs['vel_x1'].values * dx + pairs['vel_y1'].values * dy) / distance
    v2_toward_v1 = -(pairs['vel_x2'].values * dx + pairs['vel_y2'].values * dy) / distance
    
    # Follower has higher approach velocity
    veh1_is_follower = v1_toward_v2 > v2_toward_v1
    
    # Get speed magnitudes
    vel1_mag = pairs['vel1'].values
    vel2_mag = pairs['vel2'].values
    
    # Assign follower and leader velocities
    follower_vel = np.where(veh1_is_follower, vel1_mag, vel2_mag)
    leader_vel = np.where(veh1_is_follower, vel2_mag, vel1_mag)
    
    # =========================================================================
    # Stage 7: Speed difference filter (follower must be faster than leader)
    # =========================================================================
    speed_diff = follower_vel - leader_vel
    speed_diff_mask = speed_diff > min_speed_diff
    
    pairs = pairs[speed_diff_mask]
    distance = distance[speed_diff_mask]
    veh1_is_follower = veh1_is_follower[speed_diff_mask]
    follower_vel = follower_vel[speed_diff_mask]
    leader_vel = leader_vel[speed_diff_mask]
    speed_diff = speed_diff[speed_diff_mask]
    
    if len(pairs) == 0:
        return pd.DataFrame(columns=empty_columns)
    
    print(f"  Pairs with speed_diff > {min_speed_diff}: {len(pairs):,}")
    
    # =========================================================================
    # Stage 8: Calculate TTC
    # =========================================================================
    ttc, _, closing_speed = calculate_ttc_vectorized(
        pairs['pos_x1'].values, pairs['pos_y1'].values,
        pairs['pos_x2'].values, pairs['pos_y2'].values,
        pairs['vel_x1'].values, pairs['vel_y1'].values,
        pairs['vel_x2'].values, pairs['vel_y2'].values
    )
    
    # =========================================================================
    # Stage 9: Filter by TTC and closing speed
    # =========================================================================
    ttc_mask = ttc <= max_ttc
    closing_speed_mask = closing_speed >= min_closing_speed
    final_mask = ttc_mask & closing_speed_mask
    
    pairs = pairs[final_mask]
    ttc = ttc[final_mask]
    distance = distance[final_mask]
    closing_speed = closing_speed[final_mask]
    veh1_is_follower = veh1_is_follower[final_mask]
    follower_vel = follower_vel[final_mask]
    leader_vel = leader_vel[final_mask]
    speed_diff = speed_diff[final_mask]
    
    if len(pairs) == 0:
        return pd.DataFrame(columns=empty_columns)
    
    print(f"  Final pairs (TTC ≤ {max_ttc}s, closing ≥ {min_closing_speed}m/s): {len(pairs):,}")
    
    # =========================================================================
    # Build result DataFrame
    # =========================================================================
    result = pd.DataFrame({
        'timestamp': pairs['timestamp'].values,
        'id1': pairs['id1'].values,
        'id2': pairs['id2'].values,
        'label1': pairs['label1'].values,
        'label2': pairs['label2'].values,
        'pos1_x': pairs['pos_x1'].values,
        'pos1_y': pairs['pos_y1'].values,
        'pos2_x': pairs['pos_x2'].values,
        'pos2_y': pairs['pos_y2'].values,
        'vel1_x': pairs['vel_x1'].values,
        'vel1_y': pairs['vel_y1'].values,
        'vel2_x': pairs['vel_x2'].values,
        'vel2_y': pairs['vel_y2'].values,
        'vel1': pairs['vel1'].values,
        'vel2': pairs['vel2'].values,
        'distance': distance,
        'ttc': ttc,
        'closing_speed': closing_speed,
        'is_veh1_follower': veh1_is_follower,
        'follower_vel': follower_vel,
        'leader_vel': leader_vel,
        'speed_diff': speed_diff
    })
    
    # Cleanup
    del pairs
    gc.collect()
    
    return result


def get_prt_for_labels(labels: np.ndarray, config: dict) -> np.ndarray:
    """Get Perception-Reaction Time (PRT) values for vehicle labels."""
    prt_map = config['mdrac']['prt']
    return np.array([prt_map.get(int(label), 1.0) for label in labels])


def get_threshold_for_labels(labels: np.ndarray, config: dict) -> np.ndarray:
    """Get DRAC threshold values for vehicle labels."""
    threshold_map = config['mdrac']['threshold']
    return np.array([threshold_map.get(int(label), 3.4) for label in labels])


# =============================================================================
# TESTING / VERIFICATION
# =============================================================================

if __name__ == "__main__":
    """
    Comprehensive test suite for pair generation logic.
    Tests multiple scenarios to verify all filters work correctly.
    """
    
    print("=" * 70)
    print("COMPREHENSIVE PAIR GENERATION TEST SUITE")
    print("=" * 70)
    
    # -------------------------------------------------------------------------
    # Test Configuration (permissive for testing)
    # -------------------------------------------------------------------------
    test_config = {
        'filters': {
            'vehicle_labels': [4, 6, 7, 8],
            'min_vehicle_speed': 1.0,
            'max_distance': 25.0,
            'max_lateral_distance': 2.5,  # Same-lane threshold
            'max_ttc': 10.0,
            'min_closing_speed': 0.5,
            'min_speed_diff': 0.1
        }
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
                {'id': 102, 'label': 4, 'pos': (10, 0), 'vel': (10, 0)},   # B: slower, ahead
            ],
            'expected_pair': True,
            'expected_follower_id': 101,
            'expected_ttc': 2.0,  # 10m / 5m/s = 2s
            'expected_closing_speed': 5.0,
        },
        
        # =====================================================================
        # SCENARIO 2: Head-On Approach (Opposite Directions)
        # =====================================================================
        # ←── [B: 5m/s]     [A: 10m/s] ──→
        #         └────20m────┘
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
            'vel': [np.sqrt(v['vel'][0]**2 + v['vel'][1]**2) for v in vehicles]
        })
        
        # Print vehicle setup
        print("\nVehicles:")
        for v in vehicles:
            speed = np.sqrt(v['vel'][0]**2 + v['vel'][1]**2)
            print(f"  ID {v['id']}: pos={v['pos']}, vel={v['vel']}, speed={speed:.1f}m/s")
        
        # Run pair generation
        pairs = find_vehicle_vehicle_pairs(test_df, test_config)
        
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

