import os
import sys
import pandas as pd
import numpy as np
import json
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from irsm.evaluator import load_gold_labels
from ssm.utils import load_config, identify_leader_follower
from utils import brussels_data_dir, load_data

def extract_sequence_summaries(split_df, raw_trajectory_dir, pair_config):
    """
    Load raw trajectories for the target IDs, find frame sequence around peak timestamp,
    and extract tabularized temporal summaries.
    """
    print(f"Extracting temporal sequence summaries for {len(split_df)} conflicts...")
    
    # Standardize dates
    split_df = split_df.copy()
    split_df['timestamp'] = pd.to_datetime(split_df['timestamp'])
    split_df['date'] = split_df['timestamp'].dt.strftime('%Y-%m-%d')
    
    summary_features = []
    
    # Process by date to load raw files once per date
    for date_str, group in split_df.groupby('date'):
        print(f"  Processing date {date_str}...")
        
        # Identify all target vehicle IDs for this date
        target_ids = set()
        for _, row in group.iterrows():
            parts = str(row['pair_id']).split('_')
            if len(parts) == 2:
                target_ids.add(int(parts[0]))
                target_ids.add(int(parts[1]))
                
        if not target_ids:
            continue
            
        # Load raw data for this date
        try:
            raw_df = load_data(
                raw_trajectory_dir,
                date_str,
                date_str,
                dtypes=pair_config["data"]["dtypes"]
            )
        except Exception as e:
            print(f"    Failed to load data for {date_str}: {e}")
            continue
            
        if raw_df.empty:
            continue
            
        # Filter raw trajectories to target vehicles
        filtered_raw = raw_df[raw_df['id'].isin(target_ids)].copy()
        if filtered_raw.empty:
            continue
            
        # Group raw trajectory by vehicle ID
        raw_groups = {vid: grp.sort_values('timestamp') for vid, grp in filtered_raw.groupby('id')}
        
        for idx, row in group.iterrows():
            parts = str(row['pair_id']).split('_')
            id1, id2 = int(parts[0]), int(parts[1])
            
            if id1 not in raw_groups or id2 not in raw_groups:
                continue
                
            p1 = raw_groups[id1]
            p2 = raw_groups[id2]
            
            # Align timestamps
            # Find the window +/- 1.5 seconds around peak timestamp
            peak_time = row['timestamp']
            w_start = peak_time - pd.Timedelta(seconds=1.5)
            w_end = peak_time + pd.Timedelta(seconds=1.5)
            
            p1_win = p1[(p1['timestamp'] >= w_start) & (p1['timestamp'] <= w_end)]
            p2_win = p2[(p2['timestamp'] >= w_start) & (p2['timestamp'] <= w_end)]
            
            if len(p1_win) < 5 or len(p2_win) < 5:
                continue
                
            # Merge on exact or nearest timestamp (within 0.1s)
            merged = pd.merge_asof(
                p1_win.sort_values('timestamp'),
                p2_win.sort_values('timestamp'),
                on='timestamp',
                direction='nearest',
                tolerance=pd.Timedelta(seconds=0.1),
                suffixes=('1', '2')
            )
            
            if len(merged) < 5:
                continue
                
            # Calculate frame-by-frame metrics
            dx = merged['pos_x2'].values - merged['pos_x1'].values
            dy = merged['pos_y2'].values - merged['pos_y1'].values
            dist = np.sqrt(dx**2 + dy**2)
            merged['distance'] = dist
            
            # Closing speed
            vx1, vy1 = merged['vel_x1'].values, merged['vel_y1'].values
            vx2, vy2 = merged['vel_x2'].values, merged['vel_y2'].values
            rel_vx = vx1 - vx2
            rel_vy = vy1 - vy2
            
            # Vector projection of relative velocity onto distance vector
            # (rel_vx * dx + rel_vy * dy) / dist
            closing_speed = -(rel_vx * dx + rel_vy * dy) / (dist + 1e-5)
            
            # Follower deceleration
            merged_with_lf = identify_leader_follower(merged.copy())
            if 'is_veh1_follower' in merged_with_lf.columns and len(merged_with_lf) > 0:
                is_fol1 = merged_with_lf['is_veh1_follower'].values
                follower_vel = np.where(is_fol1, merged_with_lf['vel1'].values, merged_with_lf['vel2'].values)
                dt = merged['timestamp'].diff().dt.total_seconds().fillna(0.1).values
                d_vel = np.diff(follower_vel, prepend=follower_vel[0])
                follower_accel = d_vel / np.maximum(dt, 0.01)
                follower_accel = np.nan_to_num(follower_accel, nan=0.0)
            else:
                follower_accel = np.zeros(len(merged))
                
            # Yaw difference
            yaw1, yaw2 = merged['yaw1'].values, merged['yaw2'].values
            yaw_diff = np.abs(yaw2 - yaw1)
            yaw_diff = np.minimum(yaw_diff, 2*np.pi - yaw_diff)
            yaw_diff_deg = np.degrees(yaw_diff)
            
            # Compile summaries
            summaries = {
                'pair_id': row['pair_id'],
                'label': row['label'],
                'date': date_str,
                'dist_min': float(np.min(dist)),
                'dist_mean': float(np.mean(dist)),
                'dist_std': float(np.std(dist)),
                'closing_speed_max': float(np.max(closing_speed)),
                'closing_speed_mean': float(np.mean(closing_speed)),
                'closing_speed_std': float(np.std(closing_speed)),
                'decel_min': float(np.min(follower_accel)),
                'decel_mean': float(np.mean(follower_accel)),
                'decel_num_frames_braking': int(np.sum(follower_accel < -0.5)),
                'yaw_diff_mean': float(np.mean(yaw_diff_deg)),
                'yaw_diff_max': float(np.max(yaw_diff_deg))
            }
            summary_features.append(summaries)
            
    return pd.DataFrame(summary_features)

def main():
    print("\n" + "="*50)
    print("TEMPORAL SEQUENCE CLASSIFIER STAGING")
    print("="*50)
    
    # 1. Load splits
    train_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'train.csv'
    val_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'val.csv'
    test_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'test.csv'
    
    if not (train_path.exists() and val_path.exists() and test_path.exists()):
        print("Error: Labeled splits not found!")
        sys.exit(1)
        
    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)
    
    # Only keep gold (is_weak == 0) for temporal training to avoid pseudo-label sequence noise
    train_df_gold = train_df[train_df['is_weak'] == 0].copy()
    
    # Load configuration
    pair_config = load_config(str(REPO_ROOT / "config.yaml"))
    raw_trajectory_dir = brussels_data_dir()
    
    # Extract temporal summaries
    train_sum = extract_sequence_summaries(train_df_gold, raw_trajectory_dir, pair_config)
    val_sum = extract_sequence_summaries(val_df, raw_trajectory_dir, pair_config)
    test_sum = extract_sequence_summaries(test_df, raw_trajectory_dir, pair_config)
    
    if train_sum.empty or val_sum.empty or test_sum.empty:
        print("Error: Extracted sequence summaries are empty. Check raw trajectory data alignment.")
        sys.exit(1)
        
    print(f"\nExtracted Features:")
    print(f"  Train: {len(train_sum)} samples")
    print(f"  Val:   {len(val_sum)} samples")
    print(f"  Test:  {len(test_sum)} samples")
    
    # Columns to use for training
    feat_cols = [
        'dist_min', 'dist_mean', 'dist_std', 
        'closing_speed_max', 'closing_speed_mean', 'closing_speed_std', 
        'decel_min', 'decel_mean', 'decel_num_frames_braking', 
        'yaw_diff_mean', 'yaw_diff_max'
    ]
    
    X_train = train_sum[feat_cols].fillna(0.0).values
    y_train = train_sum['label'].values
    
    X_val = val_sum[feat_cols].fillna(0.0).values
    y_val = val_sum['label'].values
    
    X_test = test_sum[feat_cols].fillna(0.0).values
    y_test = test_sum['label'].values
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # Train Random Forest on Sequence Summaries
    print("\nTraining Sequence Random Forest...")
    rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
    rf.fit(X_train_scaled, y_train)
    
    # Predict
    val_probs = rf.predict_proba(X_val_scaled)[:, 1]
    test_probs = rf.predict_proba(X_test_scaled)[:, 1]
    
    val_auc = roc_auc_score(y_val, val_probs)
    test_auc = roc_auc_score(y_test, test_probs)
    
    val_preds = (val_probs >= 0.5).astype(int)
    test_preds = (test_probs >= 0.5).astype(int)
    
    val_f1 = f1_score(y_val, val_preds)
    test_f1 = f1_score(y_test, test_preds)
    
    print("\n" + "="*40)
    print("TEMPORAL SEQUENCE MODEL PERFORMANCE")
    print("="*40)
    print(f"Validation AUC: {val_auc:.3f}")
    print(f"Validation F1:  {val_f1:.3f}")
    print(f"Test AUC:       {test_auc:.3f}")
    print(f"Test F1:        {test_f1:.3f}")
    
    # Save outputs
    output_dir = Path(__file__).resolve().parent / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save model and scaler
    import joblib
    joblib.dump(rf, output_dir / 'temporal_rf_model.pkl')
    joblib.dump(scaler, output_dir / 'temporal_rf_scaler.pkl')
    
    # Save feature summaries
    train_sum.to_csv(output_dir / 'train_temporal_summaries.csv', index=False)
    val_sum.to_csv(output_dir / 'val_temporal_summaries.csv', index=False)
    test_sum.to_csv(output_dir / 'test_temporal_summaries.csv', index=False)
    
    metrics = {
        'val_auc': val_auc,
        'val_f1': val_f1,
        'test_auc': test_auc,
        'test_f1': test_f1,
        'feature_importances': {feat: float(imp) for feat, imp in zip(feat_cols, rf.feature_importances_)}
    }
    
    with open(output_dir / 'evaluation_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)
        
    print(f"\n\N{CHECK MARK} Saved temporal sequence classifier outputs to: {output_dir}")

if __name__ == '__main__':
    main()
