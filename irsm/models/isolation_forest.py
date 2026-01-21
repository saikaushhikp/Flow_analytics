"""
IRSM Isolation Forest - Near-Miss Detection via Anomaly Detection

Uses unsupervised learning to identify rare, risky vehicle interactions (near-misses)
by treating them as anomalies in the risk feature space.

Usage:
    python models/isolation_forest.py --region brussels --date 2025-06-01
"""

import pandas as pd
import numpy as np
import yaml
import os
import sys
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from datetime import datetime
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# ============================================================================
# GLOBAL VARIABLES - DATA AND MODEL
# ============================================================================
DATA = None           # Global DataFrame with risk vectors
MODEL = None          # Trained Isolation Forest model
SCALER = None         # Feature scaler
CONFIG = None         # Configuration dict
REGION = None         # Current region
DATE = None           # Current date


def load_config():
    """Load IRSM configuration."""
    config_path = Path(__file__).parent.parent / 'configuration.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_risk_vectors(region: str, date: str) -> pd.DataFrame:
    """
    Load risk vector data for a specific region and date.
    
    Args:
        region: Region name ('brussels', 'oulu')
        date: Date string (YYYY-MM-DD)
        
    Returns:
        DataFrame with risk vectors
    """
    config = load_config()
    data_path = Path(config['data']['regions'][region]['output_dir']) / f"{date}.csv"
    
    if not data_path.exists():
        raise FileNotFoundError(
            f"Risk vector data not found: {data_path}\n"
            f"Generate it first with: python irsm/data_generation.py --region {region} --date {date}"
        )
    
    print(f"Loading risk vectors: {data_path}")
    df = pd.read_csv(data_path)
    print(f"  Loaded {len(df):,} pairs")
    
    return df


def get_feature_columns() -> list:
    """
    Get risk feature columns for model training.
    
    Returns:
        List of feature column names
    """
    return [
        'mdrac',
        'distance',
        'closing_speed',
        'closing_accel',
        'ttc',
        'yaw_diff',
        'yaw_rate'
    ]


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare features for model training/prediction.
    
    Handles missing values and filters valid rows.
    
    Args:
        df: Raw risk vector DataFrame
        
    Returns:
        DataFrame with clean features ready for model
    """
    feature_cols = get_feature_columns()
    
    print("\nPreparing features...")
    print(f"  Initial rows: {len(df):,}")
    
    # Check for missing features
    missing_cols = [col for col in feature_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required features: {missing_cols}")
    
    # Create feature DataFrame
    features = df[feature_cols].copy()
    
    # Handle missing values (closing_accel, yaw_rate can be NaN for first observations)
    # Strategy: Fill with 0 (no acceleration/rate change)
    features['closing_accel'] = features['closing_accel'].fillna(0.0)
    features['yaw_rate'] = features['yaw_rate'].fillna(0.0)
    
    # Remove rows with any remaining NaN
    mask_valid = features.notna().all(axis=1)
    n_invalid = (~mask_valid).sum()
    
    if n_invalid > 0:
        print(f"  Removed {n_invalid:,} rows with NaN values")
        df = df[mask_valid].copy()
        features = features[mask_valid].copy()
    
    print(f"  Final rows: {len(df):,}")
    print(f"  Features: {', '.join(feature_cols)}")
    
    return df, features


def train_model(features: pd.DataFrame) -> tuple:
    """
    Train Isolation Forest model on risk features.
    
    Args:
        features: DataFrame with risk feature columns
        
    Returns:
        (model, scaler) - Trained model and feature scaler
    """
    config = load_config()
    if_config = config['models']['isolation_forest']
    
    print("\n" + "="*70)
    print("TRAINING ISOLATION FOREST")
    print("="*70)
    print(f"Training samples: {len(features):,}")
    print(f"Features: {features.shape[1]}")
    print(f"Contamination: {if_config['contamination']} ({if_config['contamination']*100:.1f}%)")
    print(f"Estimators: {if_config['n_estimators']}")
    
    # Normalize features (critical for Isolation Forest)
    print("\nNormalizing features...")
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)
    
    print("  Mean:", scaler.mean_)
    print("  Std:", scaler.scale_)
    
    # Train Isolation Forest
    print("\nTraining model...")
    model = IsolationForest(
        contamination=if_config['contamination'],
        n_estimators=if_config['n_estimators'],
        max_samples=if_config['max_samples'],
        random_state=if_config['random_state'],
        n_jobs=if_config['n_jobs'],
        verbose=1
    )
    
    model.fit(features_scaled)
    
    print("\n✓ Training complete!")
    
    return model, scaler


def predict_anomalies(model, scaler, features: pd.DataFrame) -> tuple:
    """
    Predict anomaly scores and labels for risk vectors.
    
    Args:
        model: Trained Isolation Forest
        scaler: Fitted StandardScaler
        features: Risk features DataFrame
        
    Returns:
        (predictions, scores) - Binary labels and anomaly scores
    """
    print("\nPredicting anomalies...")
    
    # Scale features
    features_scaled = scaler.transform(features)
    
    # Predict: -1 = anomaly (near-miss), +1 = normal
    predictions = model.predict(features_scaled)
    
    # Get anomaly scores (lower = more anomalous)
    scores = model.decision_function(features_scaled)
    
    # Statistics
    n_anomalies = (predictions == -1).sum()
    n_normal = (predictions == 1).sum()
    
    print(f"  Anomalies (near-misses): {n_anomalies:,} ({n_anomalies/len(predictions)*100:.2f}%)")
    print(f"  Normal interactions: {n_normal:,} ({n_normal/len(predictions)*100:.2f}%)")
    print(f"  Score range: [{scores.min():.4f}, {scores.max():.4f}]")
    
    return predictions, scores


def classify_risk_levels(scores: np.ndarray) -> np.ndarray:
    """
    Classify anomaly scores into risk levels.
    
    Args:
        scores: Anomaly scores from Isolation Forest
        
    Returns:
        Array of risk level strings
    """
    config = load_config()
    thresholds = config['thresholds']['risk_score']
    
    risk_levels = np.full(len(scores), 'normal', dtype=object)
    
    # Lower scores = more anomalous = higher risk
    risk_levels = np.where(scores < thresholds['low'], 'low_risk', risk_levels)
    risk_levels = np.where(scores < thresholds['medium'], 'medium_risk', risk_levels)
    risk_levels = np.where(scores < thresholds['high'], 'high_risk', risk_levels)
    
    return risk_levels


def save_results(df: pd.DataFrame, region: str, date: str):
    """
    Save detection results to CSV.
    
    Args:
        df: DataFrame with detections (includes predictions and scores)
        region: Region name
        date: Date string
    """
    # Create results directory
    results_dir = Path(__file__).parent.parent / 'results' / region
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Save near-misses only (skip all_detections.csv to save memory)
    near_misses = df[df['prediction'] == -1].copy()
    if len(near_misses) > 0:
        nm_path = results_dir / f"{date}_near_misses.csv"
        near_misses.to_csv(nm_path, index=False)
        print(f"\n✓ Saved near-misses only: {nm_path}")
        print(f"  Near-miss rows: {len(near_misses):,}")
        print(f"  Total pairs analyzed: {len(df):,}")
        
        # Print top 10 most anomalous
        print("\nTop 10 Most Anomalous Pairs:")
        top10 = near_misses.nsmallest(10, 'anomaly_score')[
            ['pair_id', 'timestamp', 'risk_level', 'anomaly_score', 'mdrac', 'distance', 'ttc']
        ]
        print(top10.to_string(index=False))
    
    # Summary statistics
    print("\n" + "="*70)
    print("DETECTION SUMMARY")
    print("="*70)
    print(f"Region: {region}")
    print(f"Date: {date}")
    print(f"Total pairs analyzed: {len(df):,}")
    print(f"\nRisk Distribution:")
    for level in ['high_risk', 'medium_risk', 'low_risk', 'normal']:
        count = (df['risk_level'] == level).sum()
        pct = count / len(df) * 100
        print(f"  {level:15s}: {count:6,} ({pct:5.2f}%)")
    print("="*70)


def save_model(model, scaler, region: str, date: str):
    """
    Save trained model and scaler for future use.
    
    Args:
        model: Trained Isolation Forest
        scaler: Fitted StandardScaler
        region: Region name
        date: Date string (for versioning)
    """
    models_dir = Path(__file__).parent.parent / 'results' / region / 'models'
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Save with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    model_path = models_dir / f"isolation_forest_{date}_{timestamp}.pkl"
    scaler_path = models_dir / f"scaler_{date}_{timestamp}.pkl"
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    
    print(f"\n✓ Saved model: {model_path}")
    print(f"✓ Saved scaler: {scaler_path}")


def run_detection(region: str, date: str):
    """
    Complete detection pipeline.
    
    Args:
        region: Region name
        date: Date string (YYYY-MM-DD)
    """
    global DATA, MODEL, SCALER, CONFIG, REGION, DATE
    
    # Load configuration
    CONFIG = load_config()
    REGION = region
    DATE = date
    
    print("="*70)
    print("IRSM ISOLATION FOREST - NEAR-MISS DETECTION")
    print("="*70)
    print(f"Region: {region}")
    print(f"Date: {date}")
    print("="*70)
    
    # Step 1: Load risk vectors
    DATA = load_risk_vectors(region, date)
    
    # Step 2: Prepare features
    DATA, features = prepare_features(DATA)
    
    # Step 3: Train model
    MODEL, SCALER = train_model(features)
    
    # Step 4: Predict anomalies
    predictions, scores = predict_anomalies(MODEL, SCALER, features)
    
    # Step 5: Classify risk levels
    risk_levels = classify_risk_levels(scores)
    
    # Step 6: Add results to DataFrame
    DATA['prediction'] = predictions
    DATA['anomaly_score'] = scores
    DATA['risk_level'] = risk_levels
    
    # Step 7: Save results
    save_results(DATA, region, date)
    
    # Models not saved (train fast, save memory)
    print("\n✓ Detection pipeline complete!")
    print("  (Model not saved - regenerate as needed)")
    
    return DATA


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="IRSM Isolation Forest - Near-Miss Detection"
    )
    parser.add_argument(
        '--region',
        type=str,
        required=True,
        help='Region name (brussels, oulu)'
    )
    parser.add_argument(
        '--date',
        type=str,
        required=True,
        help='Date (YYYY-MM-DD)'
    )
    
    args = parser.parse_args()
    
    # Run detection
    run_detection(
        region=args.region,
        date=args.date
    )
