"""
Utility functions for SSM (Surrogate Safety Measures) analysis.

Provides TTC-based pair extraction for vehicle-vehicle conflict detection.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
import yaml


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


def calculate_ttc(
    pos1_x: np.ndarray, pos1_y: np.ndarray,
    pos2_x: np.ndarray, pos2_y: np.ndarray,
    vel1_x: np.ndarray, vel1_y: np.ndarray,
    vel2_x: np.ndarray, vel2_y: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Time-to-Collision (TTC) for vehicle pairs.
    
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
    # Position difference vector
    dx = pos2_x - pos1_x
    dy = pos2_y - pos1_y
    distance = np.sqrt(dx**2 + dy**2)
    
    dvx = vel1_x - vel2_x
    dvy = vel1_y - vel2_y
    
    # Closing speed: projected velocity component along position vector
    # Negative dot product means gap is closing
    dot_product = dvx * dx + dvy * dy
    
    # Avoid division by zero
    closing_speed = np.where(
        distance > 0.1,
        -dot_product / distance,  # Positive if closing, negative if diverging
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
    Extract vehicle-vehicle pairs with potential conflicts using TTC-based filtering.
    
    Filter pipeline:
    1. Extract vehicles (label ∈ {4, 6, 7, 8})
    2. Speed filter (v ≥ min_vehicle_speed)
    3. Generate pairs (cartesian product per timestamp)
    4. Approaching filter (Δv⃗·Δr⃗ < 0)
    5. Identify leader/follower (velocity projection)
    6. Speed difference filter (follower_vel > leader_vel)
    7. TTC filter (TTC ≤ max_ttc)
    8. Closing speed filter (v_closing ≥ min_closing_speed)
    
    Args:
        df: DataFrame with columns: id, label, timestamp, pos_x, pos_y, vel_x, vel_y, vel
        config: Configuration dictionary (optional)
        config_path: Path to config.yaml if config not provided
        
    Returns:
        DataFrame with vehicle pairs including ttc, distance, closing_speed, and
        leader/follower information (is_veh1_follower, follower_vel, leader_vel, speed_diff)
    """
    if config is None:
        config = load_config(config_path)
    
    filter_config = config['filters']
    vehicle_labels = filter_config['vehicle_labels']
    min_vehicle_speed = filter_config['min_vehicle_speed']
    max_ttc = filter_config['max_ttc']
    min_closing_speed = filter_config['min_closing_speed']
    
    # Stage 1: Extract vehicles (car, van, truck, bus only)
    vehicles = df[df['label'].isin(vehicle_labels)].copy()
    
    # Stage 2: Filter moving vehicles (removes stationary/parking vehicles)
    vehicles = vehicles[vehicles['vel'] >= min_vehicle_speed]
    
    if len(vehicles) == 0:
        return pd.DataFrame(columns=[
            'timestamp', 'id1', 'id2', 'label1', 'label2',
            'pos1_x', 'pos1_y', 'pos2_x', 'pos2_y',
            'vel1_x', 'vel1_y', 'vel2_x', 'vel2_y',
            'vel1', 'vel2', 'distance', 'ttc', 'closing_speed',
            'is_veh1_follower', 'follower_vel', 'leader_vel', 'speed_diff'
        ])
    
    # Stage 3: Generate pairs per timestamp (O(T×n²) complexity)
    pairs_list = []
    
    for timestamp, group in vehicles.groupby('timestamp'):
        if len(group) < 2:
            continue
        
        group_reset = group.reset_index(drop=True)
        n = len(group_reset)
        
        # Generate all unique pairs (i < j) to avoid duplicates
        i_indices = np.repeat(np.arange(n), n - np.arange(n) - 1)
        j_indices = np.concatenate([np.arange(i+1, n) for i in range(n)])
        
        if len(i_indices) == 0:
            continue
        
        veh1 = group_reset.iloc[i_indices]
        veh2 = group_reset.iloc[j_indices]
        
        # Extract arrays for vectorized computation
        pos1_x = veh1['pos_x'].values
        pos1_y = veh1['pos_y'].values
        pos2_x = veh2['pos_x'].values
        pos2_y = veh2['pos_y'].values
        vel1_x = veh1['vel_x'].values
        vel1_y = veh1['vel_y'].values
        vel2_x = veh2['vel_x'].values
        vel2_y = veh2['vel_y'].values
        
        # Stage 4: Filter approaching pairs (Δv⃗·Δr⃗ < 0 means gap closing)
        dx = pos2_x - pos1_x
        dy = pos2_y - pos1_y
        dvx = vel1_x - vel2_x
        dvy = vel1_y - vel2_y
        dot_product = dvx * dx + dvy * dy
        
        approaching_mask = dot_product < 0
        
        if not np.any(approaching_mask):
            continue
        
        # Apply approaching filter
        pos1_x = pos1_x[approaching_mask]
        pos1_y = pos1_y[approaching_mask]
        pos2_x = pos2_x[approaching_mask]
        pos2_y = pos2_y[approaching_mask]
        vel1_x = vel1_x[approaching_mask]
        vel1_y = vel1_y[approaching_mask]
        vel2_x = vel2_x[approaching_mask]
        vel2_y = vel2_y[approaching_mask]
        
        veh1_filtered = veh1.reset_index(drop=True)[approaching_mask]
        veh2_filtered = veh2.reset_index(drop=True)[approaching_mask]
        
        # Stage 5: Identify leader and follower
        # The vehicle moving faster TOWARD the other is the follower
        dx_filt = pos2_x - pos1_x
        dy_filt = pos2_y - pos1_y
        distance_filt = np.sqrt(dx_filt**2 + dy_filt**2)
        
        # Velocity of veh1 toward veh2 (positive = moving toward)
        v1_toward_v2 = -(vel1_x * dx_filt + vel1_y * dy_filt) / distance_filt
        
        # Velocity of veh2 toward veh1 (positive = moving toward)
        v2_toward_v1 = (vel2_x * dx_filt + vel2_y * dy_filt) / distance_filt
        
        # Determine who is follower (higher approach velocity)
        veh1_is_follower = v1_toward_v2 > v2_toward_v1
        
        # Get speed magnitudes
        vel1_mag = veh1_filtered['vel'].values
        vel2_mag = veh2_filtered['vel'].values
        
        # Assign follower and leader velocities
        follower_vel = np.where(veh1_is_follower, vel1_mag, vel2_mag)
        leader_vel = np.where(veh1_is_follower, vel2_mag, vel1_mag)
        
        # Stage 6: Speed difference filter
        # Follower must be faster than leader for conflict to exist
        speed_diff = follower_vel - leader_vel
        min_speed_diff = filter_config['min_speed_diff']
        speed_diff_mask = speed_diff > min_speed_diff
        
        if not np.any(speed_diff_mask):
            continue
        
        # Apply speed difference filter
        pos1_x = pos1_x[speed_diff_mask]
        pos1_y = pos1_y[speed_diff_mask]
        pos2_x = pos2_x[speed_diff_mask]
        pos2_y = pos2_y[speed_diff_mask]
        vel1_x = vel1_x[speed_diff_mask]
        vel1_y = vel1_y[speed_diff_mask]
        vel2_x = vel2_x[speed_diff_mask]
        vel2_y = vel2_y[speed_diff_mask]
        
        veh1_filtered = veh1_filtered.reset_index(drop=True)[speed_diff_mask]
        veh2_filtered = veh2_filtered.reset_index(drop=True)[speed_diff_mask]
        veh1_is_follower = veh1_is_follower[speed_diff_mask]
        follower_vel = follower_vel[speed_diff_mask]
        leader_vel = leader_vel[speed_diff_mask]
        speed_diff = speed_diff[speed_diff_mask]
        
        # Stage 7: Calculate TTC and filter by time threshold
        ttc, distance, closing_speed = calculate_ttc(
            pos1_x, pos1_y, pos2_x, pos2_y,
            vel1_x, vel1_y, vel2_x, vel2_y
        )
        
        ttc_mask = ttc <= max_ttc
        if not np.any(ttc_mask):
            continue
        
        # Stage 8: Filter by closing speed
        closing_speed_mask = closing_speed >= min_closing_speed
        final_mask = ttc_mask & closing_speed_mask
        
        if not np.any(final_mask):
            continue
        
        # Apply final filters
        veh1_final = veh1_filtered.reset_index(drop=True)[final_mask]
        veh2_final = veh2_filtered.reset_index(drop=True)[final_mask]
        ttc_final = ttc[final_mask]
        distance_final = distance[final_mask]
        closing_speed_final = closing_speed[final_mask]
        veh1_is_follower_final = veh1_is_follower[final_mask]
        follower_vel_final = follower_vel[final_mask]
        leader_vel_final = leader_vel[final_mask]
        speed_diff_final = speed_diff[final_mask]
        
        pair_df = pd.DataFrame({
            'timestamp': timestamp,
            'id1': veh1_final['id'].values,
            'id2': veh2_final['id'].values,
            'label1': veh1_final['label'].values,
            'label2': veh2_final['label'].values,
            'pos1_x': veh1_final['pos_x'].values,
            'pos1_y': veh1_final['pos_y'].values,
            'pos2_x': veh2_final['pos_x'].values,
            'pos2_y': veh2_final['pos_y'].values,
            'vel1_x': veh1_final['vel_x'].values,
            'vel1_y': veh1_final['vel_y'].values,
            'vel2_x': veh2_final['vel_x'].values,
            'vel2_y': veh2_final['vel_y'].values,
            'vel1': veh1_final['vel'].values,
            'vel2': veh2_final['vel'].values,
            'distance': distance_final,
            'ttc': ttc_final,
            'closing_speed': closing_speed_final,
            'is_veh1_follower': veh1_is_follower_final,
            'follower_vel': follower_vel_final,
            'leader_vel': leader_vel_final,
            'speed_diff': speed_diff_final
        })
        
        pairs_list.append(pair_df)
    
    # Combine all pairs
    if len(pairs_list) == 0:
        return pd.DataFrame(columns=[
            'timestamp', 'id1', 'id2', 'label1', 'label2',
            'pos1_x', 'pos1_y', 'pos2_x', 'pos2_y',
            'vel1_x', 'vel1_y', 'vel2_x', 'vel2_y',
            'vel1', 'vel2', 'distance', 'ttc', 'closing_speed',
            'is_veh1_follower', 'follower_vel', 'leader_vel', 'speed_diff'
        ])
    
    result = pd.concat(pairs_list, ignore_index=True)
    return result


def get_prt_for_labels(labels: np.ndarray, config: dict) -> np.ndarray:
    """Get Perception-Reaction Time (PRT) values for vehicle labels."""
    prt_map = config['mdrac']['prt']
    return np.array([prt_map[label] for label in labels])


def get_threshold_for_labels(labels: np.ndarray, config: dict) -> np.ndarray:
    """Get DRAC threshold values for vehicle labels."""
    threshold_map = config['mdrac']['threshold']
    return np.array([threshold_map[label] for label in labels])
