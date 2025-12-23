"""
Pair extraction utilities for SSM conflict detection.
Provides modular filters and method-specific pipelines.
"""

import numpy as np
import pandas as pd
from typing import Tuple
import yaml
import gc


# Global configuration path
CONFIG_PATH = 'config.yaml'


def load_config(path: str = CONFIG_PATH) -> dict:
    """Load configuration from YAML."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)


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


def find_all_nearby_pairs(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Base pair generation with minimal filters.
    Filters: vehicle labels, min speed, max distance.
    Processes timestamps in batches for efficiency.
    """
    filter_config = config['filters']
    vehicle_labels = filter_config['vehicle_labels']
    min_vehicle_speed = filter_config['min_vehicle_speed']
    max_distance = filter_config.get('max_distance', 15.0)
    chunk_size = config.get('chunk_size', 100)
    
    # Stage 1: Pre-filter by vehicle type
    vehicles = df[df['label'].isin(vehicle_labels)].copy()
    if len(vehicles) == 0:
        return pd.DataFrame()
    
    # Stage 2: Remove stationary vehicles
    vehicles = vehicles[vehicles['vel'] >= min_vehicle_speed]
    if len(vehicles) == 0:
        return pd.DataFrame()
    
    print(f"  Filtered vehicles: {len(vehicles):,}")
    print(f"  Generating pairs (max_distance={max_distance}m)...")
    
    # Stage 3: Process timestamps in batches
    # Batching reduces memory pressure by processing chunks of time
    all_pairs = []
    unique_timestamps = vehicles['timestamp'].unique()
    n_timestamps = len(unique_timestamps)
    
    for chunk_start in range(0, n_timestamps, chunk_size):
        chunk_end = min(chunk_start + chunk_size, n_timestamps)
        chunk_ts = unique_timestamps[chunk_start:chunk_end]
        chunk_vehicles = vehicles[vehicles['timestamp'].isin(chunk_ts)]
        
        # Process each timestamp in the chunk
        for ts in chunk_ts:
            ts_vehicles = chunk_vehicles[chunk_vehicles['timestamp'] == ts]
            if len(ts_vehicles) < 2:
                continue
            
            # Cartesian product: all combinations for this timestamp
            ts_slim = ts_vehicles[['timestamp', 'id', 'label', 'pos_x', 'pos_y', 
                                   'vel_x', 'vel_y', 'vel', 'yaw']].copy()
            
            ts_pairs = pd.merge(ts_slim, ts_slim, on='timestamp', suffixes=('1', '2'))
            
            # Remove self-pairs and duplicates (keep only id1 < id2)
            ts_pairs = ts_pairs[ts_pairs['id1'] < ts_pairs['id2']]
            
            if len(ts_pairs) == 0:
                continue
            
            # Early distance filter: reject distant pairs immediately
            # This is critical for performance - avoids creating millions of pairs
            dx = ts_pairs['pos_x2'].values - ts_pairs['pos_x1'].values
            dy = ts_pairs['pos_y2'].values - ts_pairs['pos_y1'].values
            dist_sq = dx**2 + dy**2
            
            ts_pairs = ts_pairs[dist_sq <= (max_distance ** 2)]
            
            if len(ts_pairs) > 0:
                all_pairs.append(ts_pairs)
    
    # Combine all chunks
    if len(all_pairs) == 0:
        return pd.DataFrame()
    
    pairs = pd.concat(all_pairs, ignore_index=True)
    del all_pairs
    gc.collect()
    
    # Add distance column (needed for later filters)
    dx = pairs['pos_x2'].values - pairs['pos_x1'].values
    dy = pairs['pos_y2'].values - pairs['pos_y1'].values
    distance = np.sqrt(dx**2 + dy**2)
    
    pairs['distance'] = distance
    
    print(f"  Nearby pairs: {len(pairs):,}")
    return pairs


def filter_approaching(pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Keep pairs where gap is closing: (v2 - v1) · (p2 - p1) < 0
    Adds: closing_speed, ttc
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
    
    print(f"  Approaching pairs: {len(pairs):,}")
    return pairs


def filter_same_lane(pairs: pd.DataFrame, max_lateral: float) -> pd.DataFrame:
    """
    Lateral distance check: lat_dist = |Δr × û| where û = v_faster/|v_faster|
    Keeps pairs with lateral_dist <= max_lateral
    """
    if len(pairs) == 0:
        return pairs
    
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
    
    pairs = pairs[lateral_mask].copy()
    print(f"  Same-lane pairs (lat <= {max_lateral}m): {len(pairs):,}")
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
    Follower has higher approach velocity: v_approach = (v · Δr) / d
    Adds: is_veh1_follower, follower_vel, leader_vel, speed_diff
    """
    if len(pairs) == 0:
        return pairs
    
    # Position difference (from veh1 to veh2)
    dx = pairs['pos_x2'].values - pairs['pos_x1'].values
    dy = pairs['pos_y2'].values - pairs['pos_y1'].values
    distance = pairs['distance'].values
    
    # Calculate approach velocities
    # v1 pointing toward v2: positive component
    v1_toward_v2 = (pairs['vel_x1'].values * dx + pairs['vel_y1'].values * dy) / distance
    # v2 pointing toward v1: negative dot product, so negate
    v2_toward_v1 = -(pairs['vel_x2'].values * dx + pairs['vel_y2'].values * dy) / distance
    
    # Follower has higher approach velocity
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


def get_mdrac_pairs(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Method-specific pipeline for MDRAC (Modified DRAC) analysis.
    
    MDRAC is designed for longitudinal car-following scenarios where:
    - Vehicles are in the same lane
    - Follower is approaching leader from behind
    - Follower is traveling faster than leader
    
    Filter sequence:
        1. Base pairs (distance filter)
        2. Approaching only (gap must be closing)
        3. Same lane (lateral distance check)
        4. Leader/follower identification
        5. Speed difference filter (follower must be faster)
        6. TTC and closing speed thresholds
    
    Args:
        df: Vehicle data DataFrame
        config: Configuration with MDRAC-specific thresholds
        
    Returns:
        DataFrame ready for MDRAC calculation
    """
    # Stage 1: Generate base pairs
    pairs = find_all_nearby_pairs(df, config)
    if len(pairs) == 0:
        return pairs
    
    # Stage 2: Keep only approaching pairs
    pairs = filter_approaching(pairs)
    if len(pairs) == 0:
        return pairs
    
    # Stage 3: Same-lane filter (critical for car-following)
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
    
    return pairs


def get_spf_pairs(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    SPF pipeline: all conflict types (no lane restriction).
    Filters: approaching only
    """
    pairs = find_all_nearby_pairs(df, config)
    if len(pairs) == 0:
        return pairs
    
    # Stage 2: Keep only approaching pairs
    pairs = filter_approaching(pairs)
    
    # Stage 3: Classify conflict geometry (for analysis)
    pairs = classify_conflict_type(pairs)
    
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
