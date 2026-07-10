import os
import argparse
import pandas as pd
import numpy as np
import yaml
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]

def load_config():
    with open(repo_root / 'config.yaml', 'r') as f:
        return yaml.safe_load(f)

def apply_filters(df, model_name, config):
    global_cfg = config.get('global_filters', {})
    
    use_escape = global_cfg.get('use_escape_maneuver_filter', False)
    min_req_decel = global_cfg.get('min_required_deceleration', 2.5)
    
    use_ttr = global_cfg.get('use_ttr_filter', False)
    max_ttr = global_cfg.get('max_ttr', 2.0)
    prt = global_cfg.get('prt', 1.0)
    
    use_plausibility = global_cfg.get('use_entity_plausibility_filter', False)
    max_speeds = global_cfg.get('fp_velocity_max_speed', {})

    use_ttc = global_cfg.get('use_ttc_filter', False)
    max_ttc_thresh = global_cfg.get('max_ttc', 1.5)

    use_angle = global_cfg.get('use_angle_filter', False)
    parallel_tol = global_cfg.get('parallel_angle_tolerance', 20.0)

    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)

    # Calculate required kinematic variables
    if model_name == 'M-DRAC':
        closing_speed = df['closing_speed']
        distance = df['dist']
        ttc = df['TTC']
        yaw_diff = df.get('yaw_diff', pd.Series(90, index=df.index))
    elif model_name == 'IRSM':
        closing_speed = df['closing_speed']
        distance = df['distance']
        ttc = df['ttc']
        yaw_diff = df.get('yaw_diff', pd.Series(90, index=df.index))
    elif model_name == 'Bhattacharyya':
        dx = df['pos_x_obj2'] - df['pos_x_obj1']
        dy = df['pos_y_obj2'] - df['pos_y_obj1']
        dvx = df['vel_x_obj1'] - df['vel_x_obj2']
        dvy = df['vel_y_obj1'] - df['vel_y_obj2']
        distance = df['rel_dist']
        closing_speed = (dvx * dx + dvy * dy) / np.maximum(distance, 1.0)
        ttc = distance / np.maximum(closing_speed, 0.01)
        yaw_diff = pd.Series(90, index=df.index) # Default to 90 if unavailable in basic Bhattacharyya output

    # 1. Escape Maneuver Filter (Required Deceleration)
    if use_escape:
        req_decel = (closing_speed ** 2) / (2 * np.maximum(distance, 0.1))
        escape_mask = (closing_speed <= 0) | (req_decel > min_req_decel)
        mask = mask & escape_mask

    # 2. Time-To-React Filter
    if use_ttr:
        ttr = ttc - prt
        ttr_mask = (ttr <= max_ttr)
        mask = mask & ttr_mask

    # 3. Entity Plausibility Filter
    if use_plausibility and model_name == 'Bhattacharyya':
        def _speed_ok(label, vel):
            max_v = max_speeds.get(int(label), 999.0)
            return vel <= max_v
        
        plaus_mask = df.apply(lambda r: _speed_ok(r['label_obj1'], r['vel_obj1']) and 
                                        _speed_ok(r['label_obj2'], r['vel_obj2']), axis=1)
        mask = mask & plaus_mask

    # 4. TTC Filter
    if use_ttc:
        ttc_mask = (ttc <= max_ttc_thresh)
        mask = mask & ttc_mask
        
    # 5. Angle Filter (Drop pure parallel driving that's safe)
    if use_angle:
        is_parallel = (yaw_diff <= parallel_tol) | (yaw_diff >= (180 - parallel_tol))
        # Add angle logic here if necessary in the future
        pass

    return df[mask].copy()

def process_day(day: str):
    config = load_config()

    models = {
        'M-DRAC': repo_root / f'results/mdrac/brussels/lanes/{day}/mdrac_{day}.csv',
        'IRSM': repo_root / f'irsm/results/brussels/{day}/lanes_detections.csv',
        # Bhattacharyya is now under global results/
        'Bhattacharyya': repo_root / f'results/bhattacharyya/brussels/lanes/{day}/detections.csv'
    }

    print(f"\nApplying Global Filters for {day}...")
    for model_name, file_path in models.items():
        if file_path.exists():
            df = pd.read_csv(file_path)
            before_len = len(df)
            
            df_filtered = apply_filters(df, model_name, config)
            after_len = len(df_filtered)
            
            out_path = str(file_path).replace('.csv', '_filtered.csv')
            df_filtered.to_csv(out_path, index=False)
            print(f"[{model_name}] {before_len} -> {after_len} detections")
        else:
            print(f"[{model_name}] No data found at {file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    process_day(args.date)
