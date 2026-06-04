"""
IRSM Isolation Forest Model

Pipeline:
1. Load zone-wise risk vector data
2. Train Isolation Forest per zone (contamination=0.5%)
3. Detect anomalies (top 0.5% per zone)
4. Save detections per zone

Input: irsm/data/{region}/{date}/{zone_name}.csv
Output: irsm/results/{region}/{date}/{zone_name}_detections.csv
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import yaml
from tqdm import tqdm


def load_irsm_config(config_path='irsm/irsm_config.yaml'):
    """Load IRSM configuration"""
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = REPO_ROOT / config_file
    with config_file.open('r') as f:
        return yaml.safe_load(f)


def resolve_repo_path(path_value):
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def run_isolation_forest():
    """Train and detect per zone"""
    
    # Load config
    config = load_irsm_config()
    
    region = config['region']
    date = config['date']
    output_base = resolve_repo_path(config['data']['output_base'])
    contamination = config['model']['contamination']
    n_estimators = config['model']['n_estimators']
    random_state = config['model']['random_state']
    
    print("\n" + "="*70)
    print(f"IRSM ISOLATION FOREST - {region.upper()} - {date}")
    print("="*70)
    print(f"Contamination: {contamination} ({contamination*100}%)")
    print("="*70)
    
    # Input and output paths
    data_file = output_base / "data" / region / date / "lanes.csv"
    output_dir = output_base / "results" / region / date
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not data_file.exists():
        print(f"\n✗ Data file not found: {data_file}")
        return
    
    # Load lane pairs data
    print(f"\nLoading data from: {data_file}")
    df = pd.read_csv(data_file)
    print(f"Loaded: {len(df):,} pairs")
    
    # Feature columns for model training
    feature_cols = ['mdrac', 'distance', 'closing_speed', 'closing_accel', 'ttc', 'yaw_diff', 'yaw_rate']
    
    # Extract features
    features = df[feature_cols].copy()
    features = features.fillna(features.median())
    
    # Normalize
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)
    
    # Train Isolation Forest on ALL lane data
    print(f"\nTraining Isolation Forest...")
    print(f"  Samples: {len(df):,}")
    print(f"  Contamination: {contamination} ({contamination*100}%)")
    print(f"  Trees: {n_estimators}")
    
    model = IsolationForest(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=random_state,
        n_jobs=-1
    )
    model.fit(features_scaled)
    
    # Detect anomalies
    print(f"\nDetecting anomalies...")
    predictions = model.predict(features_scaled)
    anomaly_scores = model.decision_function(features_scaled)
    
    # Add predictions to dataframe
    df['prediction'] = predictions
    df['anomaly_score'] = anomaly_scores
    
    # Get anomalies (prediction == -1)
    detections = df[df['prediction'] == -1].copy()
    
    expected = int(len(df) * contamination)
    print(f"  Anomalies detected: {len(detections):,} ({len(detections)/len(df)*100:.2f}%)")
    print(f"  Expected: ~{expected}")
    
    # Save detections
    if len(detections) > 0:
        detection_path = output_dir / "lanes_detections.csv"
        detections.to_csv(detection_path, index=False)
        
        print("\n" + "="*70)
        print("DETECTION COMPLETE")
        print("="*70)
        print(f"Total detections: {len(detections):,}")
        print(f"Output: {detection_path}")
        print("="*70)
    else:
        print("\n✗ No detections found!")


if __name__ == '__main__':
    run_isolation_forest()
