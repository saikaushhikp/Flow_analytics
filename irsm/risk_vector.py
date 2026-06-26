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


def _train_brussels_regressors():
    """
    Loads brussels_june_in.csv and trains Random Forest Regressors to predict:
    traj_severity_score, env_min_dist, env_max_overlap_prob, env_time_horizon, env_severity_score
    """
    from pathlib import Path
    from sklearn.ensemble import RandomForestRegressor
    csv_path = Path(__file__).resolve().parents[1] / 'brussels_june_in.csv'
    if not csv_path.exists():
        print(f"Warning: {csv_path} not found. Cannot train regressors.")
        return None
        
    try:
        df = pd.read_csv(csv_path)
        
        # Compute baseline calculated features
        df['min_safe_dist_calc'] = 0.25 * (df['size_x_obj1'] + df['size_y_obj1'] + df['size_x_obj2'] + df['size_y_obj2'])
        dx = df['pos_x_obj2'] - df['pos_x_obj1']
        dy = df['pos_y_obj2'] - df['pos_y_obj1']
        dvx = df['vel_x_obj2'] - df['vel_x_obj1']
        dvy = df['vel_y_obj2'] - df['vel_y_obj1']
        v_mag_sq = dvx**2 + dvy**2
        cross = dx * dvy - dy * dvx
        df['ttc_min_dist_calc'] = np.where(v_mag_sq > 0.001, np.abs(cross) / np.sqrt(v_mag_sq), np.sqrt(dx**2 + dy**2))
        df['ttc_calc'] = df['ttc'].fillna(10.0)
        df['ttc_severity_score_calc'] = 0.08075 * (df['ttc_min_dist_calc'] ** 1.007) / np.maximum(df['ttc_calc'], 0.1) ** 0.596
        
        t_min = - (dx * dvx + dy * dvy) / np.maximum(v_mag_sq, 0.001)
        df['traj_time_horizon_calc'] = np.maximum(0.0, np.round(t_min / 0.24) * 0.24)
        dx_t = dx + dvx * df['traj_time_horizon_calc']
        dy_t = dy + dvy * df['traj_time_horizon_calc']
        df['traj_min_dist_calc'] = np.sqrt(dx_t**2 + dy_t**2)
        
        features = [
            'rel_dist', 'rel_vel', 'min_safe_dist_calc', 'ttc_min_dist_calc', 'ttc_calc', 'ttc_severity_score_calc',
            'traj_time_horizon_calc', 'traj_min_dist_calc'
        ]
        
        targets = ['traj_severity_score', 'env_min_dist', 'env_max_overlap_prob', 'env_time_horizon', 'env_severity_score']
        
        models = {}
        for target in targets:
            valid = df[df[target].notnull() & df['ttc'].notnull()].copy()
            if valid.empty:
                continue
            X = valid[features]
            y = valid[target]
            
            rf = RandomForestRegressor(n_estimators=50, random_state=42)
            rf.fit(X, y)
            models[target] = rf
            
        return models
    except Exception as e:
        print(f"Error training regressors: {e}")
        return None


def _compute_calculated_features(df):
    """
    Computes baseline calculated features on a pair DataFrame.
    """
    df = df.copy()
    
    # Check if necessary columns exist
    required_cols = ['pos_x1', 'pos_y1', 'pos_x2', 'pos_y2', 'vel_x1', 'vel_y1', 'vel_x2', 'vel_y2']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        for c in missing:
            df[c] = 0.0
            
    # 1. min_safe_dist
    size_x1 = df['size_x1'] if 'size_x1' in df.columns else np.full(len(df), 1.8)
    size_y1 = df['size_y1'] if 'size_y1' in df.columns else np.full(len(df), 1.8)
    size_x2 = df['size_x2'] if 'size_x2' in df.columns else np.full(len(df), 1.8)
    size_y2 = df['size_y2'] if 'size_y2' in df.columns else np.full(len(df), 1.8)
    df['min_safe_dist'] = 0.25 * (size_x1 + size_y1 + size_x2 + size_y2)
    
    # 2. ttc_min_dist
    dx = df['pos_x2'] - df['pos_x1']
    dy = df['pos_y2'] - df['pos_y1']
    dvx = df['vel_x2'] - df['vel_x1']
    dvy = df['vel_y2'] - df['vel_y1']
    v_mag_sq = dvx**2 + dvy**2
    cross = dx * dvy - dy * dvx
    
    df['ttc_min_dist'] = np.where(v_mag_sq > 0.001, np.abs(cross) / np.sqrt(v_mag_sq), np.sqrt(dx**2 + dy**2))
    
    # 3. ttc_severity_score
    ttc_val = df['ttc'].fillna(10.0)
    df['ttc_severity_score'] = 0.08075 * (df['ttc_min_dist'] ** 1.007) / np.maximum(ttc_val, 0.1) ** 0.596
    
    # 4. traj_time_horizon
    t_min = - (dx * dvx + dy * dvy) / np.maximum(v_mag_sq, 0.001)
    df['traj_time_horizon'] = np.maximum(0.0, np.round(t_min / 0.24) * 0.24)
    
    # 5. traj_min_dist
    dx_t = dx + dvx * df['traj_time_horizon']
    dy_t = dy + dvy * df['traj_time_horizon']
    df['traj_min_dist'] = np.sqrt(dx_t**2 + dy_t**2)
    
    return df


def _predict_regressor_features(df, models):
    """
    Predicts traj_severity_score, env_min_dist, env_max_overlap_prob, env_time_horizon, env_severity_score
    """
    df = df.copy()
    
    if models is None:
        for target in ['traj_severity_score', 'env_min_dist', 'env_max_overlap_prob', 'env_time_horizon', 'env_severity_score']:
            df[target] = np.nan
        return df
        
    X = pd.DataFrame()
    X['rel_dist'] = df['distance']
    X['rel_vel'] = df['closing_speed']
    X['min_safe_dist_calc'] = df['min_safe_dist']
    X['ttc_min_dist_calc'] = df['ttc_min_dist']
    X['ttc_calc'] = df['ttc'].fillna(10.0)
    X['ttc_severity_score_calc'] = df['ttc_severity_score']
    X['traj_time_horizon_calc'] = df['traj_time_horizon']
    X['traj_min_dist_calc'] = df['traj_min_dist']
    
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    
    for target, model in models.items():
        df[target] = model.predict(X)
        
    return df


def _compute_decel_metrics(row, traj_df_grouped):
    """
    Computes follower deceleration metrics over a 3.0s future window.
    """
    follower_id = row['id1'] if row['is_veh1_follower'] else row['id2']
    t_start = pd.to_datetime(row['timestamp'])
    t_end = t_start + pd.Timedelta(seconds=3.0)
    
    if follower_id not in traj_df_grouped:
        return {
            'decel_initial_speed': np.nan,
            'decel_final_speed': np.nan,
            'decel_speed_change': np.nan,
            'decel_avg_deceleration': np.nan,
            'decel_max_deceleration': np.nan,
            'decel_observation_time': np.nan,
            'decel_num_frames_observed': np.nan,
            'decel_alignment': np.nan,
            'decel_severity': 'none',
            'decel_model': False
        }
        
    grp = traj_df_grouped[follower_id]
    future = grp[(grp['timestamp'] >= t_start) & (grp['timestamp'] <= t_end)]
    
    if len(future) < 2:
        return {
            'decel_initial_speed': np.nan,
            'decel_final_speed': np.nan,
            'decel_speed_change': np.nan,
            'decel_avg_deceleration': np.nan,
            'decel_max_deceleration': np.nan,
            'decel_observation_time': np.nan,
            'decel_num_frames_observed': np.nan,
            'decel_alignment': np.nan,
            'decel_severity': 'none',
            'decel_model': False
        }
        
    initial_speed = future.iloc[0]['vel']
    final_speed = future.iloc[-1]['vel']
    speed_change = initial_speed - final_speed
    time_elapsed = (future.iloc[-1]['timestamp'] - future.iloc[0]['timestamp']).total_seconds()
    num_frames = len(future)
    avg_decel = speed_change / time_elapsed if time_elapsed > 0 else 0.0
    
    vels = future['vel'].values
    times = future['timestamp'].values
    dt = np.diff(times) / np.timedelta64(1, 's')
    dt = np.maximum(dt, 0.01)
    dv = -np.diff(vels)
    inst_decels = dv / dt
    inst_decels_pos = inst_decels[inst_decels > 0]
    
    if len(inst_decels_pos) > 0:
        max_decel = np.max(inst_decels_pos)
    else:
        max_decel = 0.0
        
    dx = row['pos_x2'] - row['pos_x1']
    dy = row['pos_y2'] - row['pos_y1']
    distance = row['distance']
    
    if distance > 0.001:
        if row['is_veh1_follower']:
            to_leader_x = dx / distance
            to_leader_y = dy / distance
            yaw_follower = row['yaw1']
        else:
            to_leader_x = -dx / distance
            to_leader_y = -dy / distance
            yaw_follower = row['yaw2']
            
        alignment = np.cos(yaw_follower) * to_leader_x + np.sin(yaw_follower) * to_leader_y
    else:
        alignment = np.nan
        
    if max_decel <= 0.05:
        severity = 'none'
    elif max_decel >= 6.5:
        severity = 'critical'
    elif max_decel >= 4.0:
        severity = 'serious'
    elif max_decel >= 2.0:
        severity = 'moderate'
    else:
        severity = 'low'
        
    return {
        'decel_initial_speed': initial_speed,
        'decel_final_speed': final_speed,
        'decel_speed_change': speed_change,
        'decel_avg_deceleration': avg_decel,
        'decel_max_deceleration': max_decel,
        'decel_observation_time': time_elapsed,
        'decel_num_frames_observed': num_frames,
        'decel_alignment': alignment,
        'decel_severity': severity,
        'decel_model': True
    }


def extract_risk_vectors(pairs: pd.DataFrame, 
                        region: str = "",
                        config: Dict = None,
                        traj_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Extract risk vectors from pair data using config-based thresholds.
    Uses existing SSM functions - NO hardcoded values.
    
    Pipeline:
        1. Apply SSM filter_approaching
        2. Filter by config thresholds (TTC, closing_speed)
        3. Compute MDRAC using existing ModifiedDRAC class
        4. Aggregate to average
        5. Extract rich features using analytical formulas and regressors
        6. Compute follower deceleration metrics from original trajectory data
        7. Select final features
        
    Args:
        pairs: DataFrame with pair observations
        region: Region name for link generation
        config: IRSM configuration dict (from irsm_config.yaml)
        traj_df: Optional original trajectory DataFrame to compute deceleration metrics
        
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
    # STEP 4: Calculate advanced features (analytical and regressor-based)
    # ========================================================================
    print("  Calculating advanced features...")
    aggregated = _compute_calculated_features(aggregated)
    models = _train_brussels_regressors()
    aggregated = _predict_regressor_features(aggregated, models)
    
    # ========================================================================
    # STEP 5: Compute follower deceleration metrics from original trajectory data
    # ========================================================================
    if traj_df is not None and len(aggregated) > 0:
        print("  Computing follower deceleration metrics...")
        follower_ids = set(np.where(aggregated['is_veh1_follower'], aggregated['id1'], aggregated['id2']))
        follower_df = traj_df[traj_df['id'].isin(follower_ids)].sort_values(['id', 'timestamp'])
        traj_df_grouped = {fid: grp for fid, grp in follower_df.groupby('id')}
        
        decel_list = []
        for _, row in aggregated.iterrows():
            decel_list.append(_compute_decel_metrics(row, traj_df_grouped))
            
        decel_df = pd.DataFrame(decel_list)
        for col in decel_df.columns:
            aggregated[col] = decel_df[col].values
    else:
        print("  No trajectory data provided; filling deceleration metrics with NaN.")
        aggregated['decel_initial_speed'] = np.nan
        aggregated['decel_final_speed'] = np.nan
        aggregated['decel_speed_change'] = np.nan
        aggregated['decel_avg_deceleration'] = np.nan
        aggregated['decel_max_deceleration'] = np.nan
        aggregated['decel_observation_time'] = np.nan
        aggregated['decel_num_frames_observed'] = np.nan
        aggregated['decel_alignment'] = np.nan
        aggregated['decel_severity'] = 'none'
        aggregated['decel_model'] = False
        
    # ========================================================================
    # STEP 6: Select final features
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
    
    # Rename yaw_diff_rate to yaw_rate for consistency with user spec
    if 'yaw_diff_rate' in aggregated.columns:
        aggregated = aggregated.rename(columns={'yaw_diff_rate': 'yaw_rate'})
        
    risk_features = get_feature_names()
    
    # Final column selection
    final_cols = metadata_cols + ['same_zone'] + risk_features + ['link']
    
    # Keep only available columns
    available_cols = [c for c in final_cols if c in aggregated.columns]
    result = aggregated[available_cols].copy()
    
    print(f"  \N{CHECK MARK} Extracted risk vectors: {len(result):,} rows × {len(available_cols)} features")
    print(f"  Features: {', '.join([f for f in risk_features if f in result.columns])}")
    print(f"  NOTE: Only MDRAC is averaged; others are point/window values at peak timestamp")
    
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
        'yaw_rate',
        'min_safe_dist',
        'ttc_min_dist',
        'ttc_severity_score',
        'traj_min_dist',
        'traj_time_horizon',
        'traj_severity_score',
        'env_min_dist',
        'env_max_overlap_prob',
        'env_time_horizon',
        'env_severity_score',
        'decel_initial_speed',
        'decel_final_speed',
        'decel_speed_change',
        'decel_avg_deceleration',
        'decel_max_deceleration',
        'decel_observation_time',
        'decel_num_frames_observed',
        'decel_alignment',
        'decel_severity',
        'decel_model'
    ]

