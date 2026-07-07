import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import argparse
import geopandas as gpd
from shapely import wkt
import warnings
warnings.filterwarnings('ignore')

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils import (
    brussels_data_dir,
    default_config_path,
    load_data
)
from filters.preprocessing import (
    filter_by_lifetime,
    attach_zones_to_objects,
    apply_footpath_zone_filter,
    compute_polygon_orientation,
    filter_parallel_vehicles,
    filter_static_objects
)
from regions.brussels.zones import get_lane_zones, get_footpath_zones, get_crosswalk_zones
from ssm.utils import load_config, assign_zones_to_vehicles, find_all_nearby_pairs, identify_leader_follower
from ssm.m_drac import ModifiedDRAC
from irsm.evaluator import load_gold_labels, parse_date

# Define parameters grid as per PLAN.md
LANE_GRID = {
    'min_mdrac': [3.4, 4.0, 4.5, 5.0],
    'max_ttc': [1.0, 1.2, 1.5, 1.8],
    'min_speed_diff': [0.5, 1.0, 1.5],
    'max_lateral_distance': [1.2, 1.5, 1.8],
    'closing_accel_threshold': [-0.3, -0.5, -0.8],
    'min_avg_frames': [3, 4, 5]
}

CROSSWALK_GRID = {
    'min_mdrac': [3.4, 4.0, 4.5],
    'max_ttc': [0.8, 1.0, 1.2],
    'min_speed_diff': [0.5, 1.0],
    'yaw_diff_rate_threshold': [10.0, 15.0, 20.0],
    'avg_window': [0.1, 0.2, 0.3],
    'min_avg_frames': [1, 2]
}

def generate_loose_base_pairs(df_lanes, df_crosswalk, config):
    """Generate loose pairs for both lanes and crosswalks."""
    # Set loose settings
    pair_config = config.copy()
    pair_config['filters'] = config['filters'].copy()
    pair_config['filters']['max_distance'] = 10.0
    pair_config['filters']['max_lateral_distance'] = 2.0
    pair_config['filters']['min_speed_diff'] = 0.0
    pair_config['filters']['max_ttc'] = 13.0
    pair_config['filters']['min_closing_speed'] = 0.0
    pair_config['filters']['vehicle_labels'] = [1, 2, 3, 4, 6, 7, 8]
    
    # Lanes
    lane_pairs = pd.DataFrame()
    if not df_lanes.empty:
        lane_base = find_all_nearby_pairs(df_lanes, pair_config)
        if not lane_base.empty:
            from ssm.utils import get_mdrac_pairs
            lane_pairs = get_mdrac_pairs(
                lane_base,
                pair_config,
                skip_pair_generation=True,
                skip_same_lane_filter=True, # We filter same-lane in tuning loops
                skip_label_filter=False
            )
        
    # Crosswalks
    crosswalk_pairs = pd.DataFrame()
    if not df_crosswalk.empty:
        crosswalk_base = find_all_nearby_pairs(df_crosswalk, pair_config)
        if not crosswalk_base.empty:
            # Pedestrian-vehicle label sets
            from ssm.utils import get_mdrac_pairs
            crosswalk_pairs = get_mdrac_pairs(
                crosswalk_base,
                pair_config,
                skip_pair_generation=True,
                label_sets=([1], [4, 6, 7, 8, 3, 2]),
                skip_same_lane_filter=True,
                skip_label_filter=False
            )
            
    return lane_pairs, crosswalk_pairs

def apply_temporal_averaging(pairs, avg_window, min_avg_frames, min_mdrac):
    """Fast vectorized temporal averaging logic."""
    if len(pairs) == 0:
        return pd.DataFrame()
        
    results = []
    window = pd.Timedelta(seconds=avg_window)
    max_frame_gap = max(0.5, avg_window * 2)
    
    # Sort
    pairs = pairs.sort_values(['id1', 'id2', 'timestamp']).copy()
    pairs['timestamp'] = pd.to_datetime(pairs['timestamp'])
    
    # Group by pair in memory
    for (id1, id2), group in pairs.groupby(['id1', 'id2']):
        if len(group) < min_avg_frames:
            continue
            
        gaps = group['timestamp'].diff().dt.total_seconds().fillna(0)
        group['event_segment'] = (gaps > max_frame_gap).cumsum()
        
        for _, segment in group.groupby('event_segment'):
            if len(segment) < min_avg_frames:
                continue
                
            indexed = segment.set_index('timestamp', drop=False)
            indexed['avg_mdrac'] = indexed['mdrac'].rolling(
                window=window,
                min_periods=min_avg_frames,
                center=True,
            ).mean()
            
            sustained = indexed[indexed['avg_mdrac'] >= min_mdrac]
            if len(sustained) == 0:
                continue
                
            peak_idx = sustained['avg_mdrac'].idxmax()
            peak_row = sustained.loc[peak_idx].copy()
            if isinstance(peak_row, pd.DataFrame):
                peak_row = peak_row.iloc[0]
                
            peak_row['mdrac_avg'] = peak_row['avg_mdrac']
            peak_row['num_frames'] = len(sustained)
            peak_row['duration'] = (
                sustained['timestamp'].max() - sustained['timestamp'].min()
            ).total_seconds()
            
            results.append(peak_row.to_dict())
            
    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results)

def apply_quality_gates(conflicts, min_avg_frames, dedupe_window_sec=10.0, min_duration=0.2):
    """Apply pair deduplication and temporal persistence checks."""
    if conflicts.empty:
        return conflicts
        
    # Temporal persistence
    conflicts = conflicts[(conflicts['num_frames'] >= min_avg_frames) & (conflicts['duration'] >= min_duration)]
    if conflicts.empty:
        return conflicts
        
    # Composite severity score: avg_mdrac * (1 / (ttc + 0.1)) * (closing_speed + 1) * (duration + 1)
    conflicts['composite_score'] = (
        conflicts['mdrac_avg'] * 
        (1.0 / (conflicts['ttc'] + 0.1)) * 
        (conflicts['closing_speed'] + 1.0) * 
        (conflicts['duration'] + 1.0)
    )
    
    # Construct pair_id if missing
    if 'pair_id' not in conflicts.columns and 'id1' in conflicts.columns and 'id2' in conflicts.columns:
        conflicts['pair_id'] = conflicts.apply(
            lambda r: f"{min(int(r['id1']), int(r['id2']))}_{max(int(r['id1']), int(r['id2']))}",
            axis=1
        )
        
    # Sort by timestamp
    conflicts = conflicts.sort_values(by=['pair_id', 'timestamp']).reset_index(drop=True)
    
    # Pair-level dedupe: keep strongest event per pair in temporal clusters
    deduped = []
    for pair_id, group in conflicts.groupby('pair_id'):
        group = group.sort_values(by='timestamp')
        time_diffs = group['timestamp'].diff().dt.total_seconds().fillna(dedupe_window_sec + 1.0)
        group['cluster'] = (time_diffs > dedupe_window_sec).cumsum()
        
        # Keep strongest per cluster
        for _, cluster_grp in group.groupby('cluster'):
            strongest = cluster_grp.loc[cluster_grp['composite_score'].idxmax()]
            deduped.append(strongest.to_dict())
            
    return pd.DataFrame(deduped)

def evaluate_shortlist(conflicts, gold_df, date_list, top_k=10):
    """Compute Precision@K and Recall@K on the gold set."""
    if conflicts.empty:
        return 0.0, 0.0
        
    conflicts = conflicts.copy()
    conflicts['date'] = conflicts['timestamp'].dt.strftime('%Y-%m-%d')
    
    # Standardize pair_id just in case
    def std_pair_id(pid):
        parts = str(pid).split('_')
        if len(parts) == 2:
            return f"{min(parts[0], parts[1])}_{max(parts[0], parts[1])}"
        return str(pid)
    conflicts['pair_id'] = conflicts['pair_id'].apply(std_pair_id)
    
    # Rank daily shortlists by composite score
    daily_shortlists = []
    for d in date_list:
        day_conf = conflicts[conflicts['date'] == d].copy()
        if day_conf.empty:
            continue
        day_conf = day_conf.sort_values(by='composite_score', ascending=False).reset_index(drop=True)
        day_conf['rank'] = np.arange(1, len(day_conf) + 1)
        daily_shortlists.append(day_conf)
        
    if not daily_shortlists:
        return 0.0, 0.0
        
    all_shortlist = pd.concat(daily_shortlists, ignore_index=True)
    
    # Align with gold df
    aligned = pd.merge(all_shortlist, gold_df, on=['date', 'pair_id'], how='left')
    aligned['label_gold'] = aligned['label_gold'].fillna(0).astype(int)
    aligned['is_lidar_artifact'] = aligned['is_lidar_artifact'].fillna('No')
    
    # Exclude lidar artifacts from metric calculation
    aligned = aligned[aligned['is_lidar_artifact'] != 'Yes']
    
    # Compute daily Precision@10 and Recall@10
    daily_precisions = []
    daily_recalls = []
    
    # Filter gold df to our dates (excluding lidar)
    gold_filtered = gold_df[(gold_df['date'].isin(date_list)) & (gold_df['is_lidar_artifact'] != 'Yes')]
    
    for d in date_list:
        day_aligned = aligned[(aligned['date'] == d) & (aligned['rank'] <= top_k)]
        gold_positives_day = gold_filtered[(gold_filtered['date'] == d) & (gold_filtered['label_gold'] == 1)]
        total_pos_day = len(gold_positives_day)
        
        tp_count = (day_aligned['label_gold'] == 1).sum()
        
        precision = tp_count / float(top_k)
        recall = tp_count / float(total_pos_day) if total_pos_day > 0 else 0.0
        
        daily_precisions.append(precision)
        if total_pos_day > 0:
            daily_recalls.append(recall)
            
    avg_precision = np.mean(daily_precisions) if daily_precisions else 0.0
    avg_recall = np.mean(daily_recalls) if daily_recalls else 0.0
    
    return avg_precision, avg_recall

def tune_lanes(lane_pairs, gold_df, dates, config):
    """Tune lane M-DRAC parameters."""
    print("\n--- TUNING LANE PARAMETERS ---")
    best_precision = -1.0
    best_recall = -1.0
    best_params = {}
    
    # Nested loops optimized for pre-loaded frame-by-frame data
    for max_lat in LANE_GRID['max_lateral_distance']:
        for min_sd in LANE_GRID['min_speed_diff']:
            for max_t in LANE_GRID['max_ttc']:
                # Pre-filter frame-by-frame pairs geometrically
                if lane_pairs.empty:
                    continue
                # Speed diff filter
                df_f = lane_pairs[lane_pairs['speed_diff'] > min_sd]
                # TTC filter
                df_f = df_f[df_f['ttc'] <= max_t]
                # Lateral distance same-lane filter
                if not df_f.empty and 'zone1' in df_f.columns and 'zone2' in df_f.columns:
                    dx = df_f['pos_x2'].values - df_f['pos_x1'].values
                    dy = df_f['pos_y2'].values - df_f['pos_y1'].values
                    vel_x = np.where(df_f['is_veh1_follower'], df_f['vel_x1'].values, df_f['vel_x2'].values)
                    vel_y = np.where(df_f['is_veh1_follower'], df_f['vel_y1'].values, df_f['vel_y2'].values)
                    speed = np.where(df_f['is_veh1_follower'], df_f['vel1'].values, df_f['vel2'].values)
                    u_x = np.where(speed > 0.5, vel_x / speed, 0.0)
                    u_y = np.where(speed > 0.5, vel_y / speed, 0.0)
                    lat_dist = np.abs(dx * u_y - dy * u_x)
                    df_f = df_f[(lat_dist <= max_lat) | (speed <= 0.5)]
                
                if df_f.empty:
                    continue
                    
                for closing_acc in LANE_GRID['closing_accel_threshold']:
                    # Calculate effective PRT and MDRAC in-memory
                    df_m = df_f.copy()
                    follower_label = np.where(df_m['is_veh1_follower'], df_m['label1'], df_m['label2'])
                    prt_base = np.array([config['mdrac']['prt'].get(int(lbl), 1.0) for lbl in follower_label])
                    is_responding = (df_m['follower_accel'] < closing_acc) | (df_m['closing_accel'] < closing_acc)
                    prt_eff = np.where(is_responding, 0.0, prt_base)
                    time_avail = df_m['ttc'].values - prt_eff
                    df_m['mdrac'] = np.where(time_avail > 0.2, df_m['closing_speed'].values / (2 * time_avail), df_m['closing_speed'].values / 0.4)
                    
                    for min_avg_f in LANE_GRID['min_avg_frames']:
                        # Calculate averaging
                        avg_window = 1.0 # fixed for lanes
                        avg_df = apply_temporal_averaging(df_m, avg_window, min_avg_f, min_mdrac=3.0)
                        
                        if avg_df.empty:
                            continue
                        
                        for min_mdr in LANE_GRID['min_mdrac']:
                            # Filter by min_mdrac
                            conf_f = avg_df[avg_df['mdrac_avg'] >= min_mdr]
                            
                            # Quality gates (dedupe & persistence)
                            deduped = apply_quality_gates(conf_f, min_avg_f, dedupe_window_sec=10.0, min_duration=0.2)
                            
                            # Evaluate shortlist
                            prec, rec = evaluate_shortlist(deduped, gold_df, dates, top_k=10)
                            
                            if prec > best_precision or (prec == best_precision and rec > best_recall):
                                best_precision = prec
                                best_recall = rec
                                best_params = {
                                    'min_mdrac': min_mdr,
                                    'max_ttc': max_t,
                                    'min_speed_diff': min_sd,
                                    'max_lateral_distance': max_lat,
                                    'closing_accel_threshold': closing_acc,
                                    'min_avg_frames': min_avg_f,
                                    'avg_window': avg_window
                                }
                                print(f"  New Best Lanes Params: Prec@10={prec:.3f}, Rec@10={rec:.3f} | {best_params}")
                                
    return best_params, best_precision, best_recall

def tune_crosswalks(cw_pairs, gold_df, dates, config):
    """Tune crosswalk M-DRAC parameters."""
    print("\n--- TUNING CROSSWALK PARAMETERS ---")
    best_precision = -1.0
    best_recall = -1.0
    best_params = {}
    
    for min_sd in CROSSWALK_GRID['min_speed_diff']:
        for max_t in CROSSWALK_GRID['max_ttc']:
            for yaw_diff_rate in CROSSWALK_GRID['yaw_diff_rate_threshold']:
                if cw_pairs.empty:
                    continue
                # Speed diff filter
                df_f = cw_pairs[cw_pairs['speed_diff'] > min_sd]
                # TTC filter
                df_f = df_f[df_f['ttc'] <= max_t]
                # Yaw diff rate filter
                is_longitudinal = df_f['yaw_diff'] <= 30.0
                non_long_pass = (~is_longitudinal) & (np.abs(df_f['yaw_diff_rate']) >= yaw_diff_rate)
                df_f = df_f[is_longitudinal | non_long_pass]
                
                if df_f.empty:
                    continue
                    
                for avg_win in CROSSWALK_GRID['avg_window']:
                    for min_avg_f in CROSSWALK_GRID['min_avg_frames']:
                        # Compute MDRAC
                        df_m = df_f.copy()
                        follower_label = np.where(df_m['is_veh1_follower'], df_m['label1'], df_m['label2'])
                        prt_base = np.array([config['mdrac']['prt'].get(int(lbl), 1.0) for lbl in follower_label])
                        is_responding = (df_m['follower_accel'] < -0.5) | (df_m['closing_accel'] < -0.5)
                        prt_eff = np.where(is_responding, 0.0, prt_base)
                        time_avail = df_m['ttc'].values - prt_eff
                        df_m['mdrac'] = np.where(time_avail > 0.2, df_m['closing_speed'].values / (2 * time_avail), df_m['closing_speed'].values / 0.4)
                        
                        avg_df = apply_temporal_averaging(df_m, avg_win, min_avg_f, min_mdrac=3.0)
                        
                        if avg_df.empty:
                            continue
                        
                        for min_mdr in CROSSWALK_GRID['min_mdrac']:
                            conf_f = avg_df[avg_df['mdrac_avg'] >= min_mdr]
                            
                            # Quality gates
                            deduped = apply_quality_gates(conf_f, min_avg_f, dedupe_window_sec=10.0, min_duration=0.1)
                            
                            # Evaluate
                            prec, rec = evaluate_shortlist(deduped, gold_df, dates, top_k=10)
                            
                            if prec > best_precision or (prec == best_precision and rec > best_recall):
                                best_precision = prec
                                best_recall = rec
                                best_params = {
                                    'min_mdrac': min_mdr,
                                    'max_ttc': max_t,
                                    'min_speed_diff': min_sd,
                                    'yaw_diff_rate_threshold': yaw_diff_rate,
                                    'avg_window': avg_win,
                                    'min_avg_frames': min_avg_f
                                }
                                print(f"  New Best Crosswalks Params: Prec@10={prec:.3f}, Rec@10={rec:.3f} | {best_params}")
                                
    return best_params, best_precision, best_recall

def main():
    parser = argparse.ArgumentParser(description="Tune M-DRAC with restricted memory constraints")
    parser.add_argument('--max-hours', type=int, default=20, help="Maximum hourly folders to process (strictly limited to <= 20)")
    parser.add_argument('--start-hour-index', type=int, default=0, help="Index of the first hourly folder to load (helps slice 168 hours of data)")
    args = parser.parse_args()
    
    # Strictly limit to 20 hours to prevent out-of-memory errors
    max_hours = min(args.max_hours, 20)
    print(f"Starting M-DRAC parameter tuning. Capped max_hours: {max_hours}, start_hour_index: {args.start_hour_index}")
    
    global config
    config = load_config(str(default_config_path()))
    
    # Load gold labels
    gold_path = str(REPO_ROOT / 'brussels_june_in.csv')
    gold_df = load_gold_labels(gold_path)
    
    # Data directory
    data_dir = str(brussels_data_dir())
    
    # Resolve and slice hourly folders to limit memory usage
    print(f"Resolving trajectory hourly folders...")
    from utils.data_loader import _folder_in_range, _read_parquet_folder
    data_path = Path(data_dir).expanduser()
    folders = [
        child
        for child in sorted(data_path.iterdir())
        if child.is_dir() and _folder_in_range(child.name, "2025-06-01", "2025-06-07", "00")
    ]
    print(f"Found {len(folders)} total hourly folders in range.")
    
    selected_folders = folders[args.start_hour_index : args.start_hour_index + max_hours]
    print(f"Selected {len(selected_folders)} folders starting from index {args.start_hour_index}.")
    
    frames = []
    from tqdm import tqdm
    for folder in tqdm(selected_folders, desc="Loading data"):
        chunk = _read_parquet_folder(folder)
        if config['data']['dtypes']:
            for col, dtype in config['data']['dtypes'].items():
                if col in chunk.columns:
                    chunk[col] = chunk[col].astype(dtype)
        frames.append(chunk)
        
    if not frames:
        print("Error: No trajectory data could be loaded for the selected range!")
        sys.exit(1)
        
    df = pd.concat(frames, ignore_index=True)
        
    df.reset_index(drop=True, inplace=True)
    
    # Extract dates that were actually loaded
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    loaded_dates = df['timestamp'].dt.strftime('%Y-%m-%d').unique().tolist()
    print(f"Successfully loaded {len(df):,} rows across dates: {loaded_dates}")
    
    # Preprocessing
    print("\nPreprocessing loaded trajectories...")
    df = filter_by_lifetime(df, config['preprocessing']['lifetime_filter']['min_lifespan'])
    
    # Footpath filter
    footpath_zones = get_footpath_zones()
    zones_df = pd.DataFrame(footpath_zones)
    zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
    gdf_zones = gpd.GeoDataFrame(zones_df, geometry="geometry")
    df = attach_zones_to_objects(df, gdf_zones, how="left", batch_size=100000)
    df = apply_footpath_zone_filter(df)
    df = df.drop(columns=['zone'], errors='ignore')
    
    # Crosswalk zone parallel filter
    crosswalk_zones = get_crosswalk_zones()
    zones_df = pd.DataFrame(crosswalk_zones)
    zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
    gdf_zones = gpd.GeoDataFrame(zones_df, geometry="geometry")
    gdf_zones["orientation_deg"] = gdf_zones["geometry"].apply(compute_polygon_orientation)
    
    df = attach_zones_to_objects(df, gdf_zones, how="left", batch_size=100000)
    
    # Filter parallel vehicles
    removed_ids_global = []
    df_in_zones = df[df['zone'].notnull()].copy()
    for zone_id in df_in_zones['zone'].unique():
        df_zone = df_in_zones[df_in_zones['zone'] == zone_id]
        orientation = gdf_zones[gdf_zones['id'] == zone_id]['orientation_deg'].iloc[0]
        parallel_ids, _ = filter_parallel_vehicles(df_zone, orientation, threshold=4.0)
        removed_ids_global.extend(parallel_ids)
        
    df = df[~df['id'].isin(removed_ids_global)]
    
    # Static filter
    df = filter_static_objects(df, static_threshold=config['preprocessing']['static_filter']['min_speed'], static_ratio_min=0.8)
    
    # Separate crosswalks and lanes
    df_crosswalk = df[df['zone'].notnull()].copy()
    
    df_lanes = assign_zones_to_vehicles(df.drop(columns=['zone'], errors='ignore'), get_lane_zones())
    df_lanes = df_lanes[df_lanes['zone'] != 'unknown'].copy()
    
    print(f"Lanes vehicles count: {len(df_lanes):,}, Crosswalks vehicles count: {len(df_crosswalk):,}")
    
    # Generate base pairs (loose)
    print("\nGenerating loose base pairs...")
    lane_pairs, cw_pairs = generate_loose_base_pairs(df_lanes, df_crosswalk, config)
    print(f"Loose lane pairs: {len(lane_pairs):,}, Loose crosswalk pairs: {len(cw_pairs):,}")
    
    # Pre-calculate follower variables to speed up nested loops
    if not lane_pairs.empty:
        lane_pairs = identify_leader_follower(lane_pairs)
        follower_vel = np.where(lane_pairs['is_veh1_follower'], lane_pairs['vel1'], lane_pairs['vel2'])
        lane_pairs['follower_vel'] = follower_vel
        lane_pairs = lane_pairs.sort_values(['id1', 'id2', 'timestamp'])
        
        pair_groups = lane_pairs.groupby(['id1', 'id2'], sort=False)
        dt = pair_groups['timestamp'].diff().dt.total_seconds().fillna(0.1)
        d_vel = pair_groups['follower_vel'].diff().fillna(0.0)
        lane_pairs['accel_raw'] = d_vel / np.maximum(dt, 0.01)
        lane_pairs['follower_accel'] = pair_groups['accel_raw'].rolling(window=3, center=True, min_periods=1).mean().reset_index(level=[0,1], drop=True).values
        
    if not cw_pairs.empty:
        cw_pairs = identify_leader_follower(cw_pairs)
        follower_vel = np.where(cw_pairs['is_veh1_follower'], cw_pairs['vel1'], cw_pairs['vel2'])
        cw_pairs['follower_vel'] = follower_vel
        cw_pairs = cw_pairs.sort_values(['id1', 'id2', 'timestamp'])
        
        pair_groups = cw_pairs.groupby(['id1', 'id2'], sort=False)
        dt = pair_groups['timestamp'].diff().dt.total_seconds().fillna(0.1)
        d_vel = pair_groups['follower_vel'].diff().fillna(0.0)
        cw_pairs['accel_raw'] = d_vel / np.maximum(dt, 0.01)
        cw_pairs['follower_accel'] = pair_groups['accel_raw'].rolling(window=3, center=True, min_periods=1).mean().reset_index(level=[0,1], drop=True).values
        
        # Calculate yaw and yaw rate
        yaw_diff_rad = np.abs(cw_pairs['yaw2'].values - cw_pairs['yaw1'].values)
        yaw_diff_rad = np.minimum(yaw_diff_rad, 2*np.pi - yaw_diff_rad)
        cw_pairs['yaw_diff'] = np.degrees(yaw_diff_rad)
        
        cw_pairs['d_yaw_diff'] = pair_groups['yaw_diff'].diff().fillna(0.0)
        cw_pairs['yaw_diff_rate_raw'] = cw_pairs['d_yaw_diff'] / np.maximum(dt, 0.01)
        cw_pairs['yaw_diff_rate'] = pair_groups['yaw_diff_rate_raw'].rolling(window=3, center=True, min_periods=1).mean().reset_index(level=[0,1], drop=True).values
        
    # Tune lanes parameters
    best_lane_params, best_lane_prec, best_lane_rec = tune_lanes(lane_pairs, gold_df, loaded_dates, config)
    print(f"\nOPTIMIZED LANE PARAMETERS (Best Prec@10={best_lane_prec:.3f}, Rec@10={best_lane_rec:.3f}):")
    print(best_lane_params)
    
    # Tune crosswalks parameters
    best_cw_params, best_cw_prec, best_cw_rec = tune_crosswalks(cw_pairs, gold_df, loaded_dates, config)
    print(f"\nOPTIMIZED CROSSWALK PARAMETERS (Best Prec@10={best_cw_prec:.3f}, Rec@10={best_cw_rec:.3f}):")
    print(best_cw_params)
    
    # Save optimized parameters to report
    report_path = REPO_ROOT / 'next_steps' / 'mdrac_tuning_report.md'
    with open(report_path, 'w') as f:
        f.write(f"""# M-DRAC Parameter Optimization Tuning Report

Based on parameter grid search on the gold Brussels dataset (`brussels_june_in.csv`) over the first {max_hours} hours.

## 1. Lanes Parameters (Vehicle-Vehicle longitudinal conflicts)
- **Best Precision@10**: {best_lane_prec:.3f}
- **Best Recall@10**: {best_lane_rec:.3f}
- **Optimized Parameters**:
  - `min_mdrac`: {best_lane_params.get('min_mdrac')}
  - `max_ttc`: {best_lane_params.get('max_ttc')}
  - `min_speed_diff`: {best_lane_params.get('min_speed_diff')}
  - `max_lateral_distance`: {best_lane_params.get('max_lateral_distance')}
  - `closing_accel_threshold`: {best_lane_params.get('closing_accel_threshold')}
  - `min_avg_frames`: {best_lane_params.get('min_avg_frames')}
  - `avg_window`: 1.0 (fixed)

## 2. Crosswalks Parameters (Pedestrian-Vehicle crosswalk interactions)
- **Best Precision@10**: {best_cw_prec:.3f}
- **Best Recall@10**: {best_cw_rec:.3f}
- **Optimized Parameters**:
  - `min_mdrac`: {best_cw_params.get('min_mdrac')}
  - `max_ttc`: {best_cw_params.get('max_ttc')}
  - `min_speed_diff`: {best_cw_params.get('min_speed_diff')}
  - `yaw_diff_rate_threshold`: {best_cw_params.get('yaw_diff_rate_threshold')}
  - `avg_window`: {best_cw_params.get('avg_window')}
  - `min_avg_frames`: {best_cw_params.get('min_avg_frames')}
""")
    print(f"\n\N{CHECK MARK} Saved tuning report to: {report_path}")

if __name__ == '__main__':
    main()
