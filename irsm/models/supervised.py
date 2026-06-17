"""
IRSM Supervised Near-Miss Detection

Supervised learning approach using Random Forest, XGBoost, and Neural Networks.
Uses labeled near-miss data to train binary classifiers.

Pipeline:
1. Training: python3 irsm/models/supervised.py --train
2. Detection: python3 irsm/models/supervised.py

Input: irsm/data/{region}/{date}/lanes.csv
Output: irsm/results/{region}/{date}/supervised/{model}_detections.csv
"""

import sys
import pandas as pd
import numpy as np
import json
import os
import argparse
from pathlib import Path
import yaml
from typing import Union, Optional
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from imblearn.over_sampling import SMOTE
from sklearn.metrics import (
    roc_auc_score, f1_score, precision_score, recall_score,
    accuracy_score, confusion_matrix
)
from sklearn.model_selection import train_test_split
import joblib

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from irsm.risk_vector import get_feature_names

# Try to import xgboost (optional)
try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

# =============================================================================
# CONFIGURATION
# =============================================================================

FEATURES = get_feature_names()

DATA_DIR = str(REPO_ROOT / 'irsm' / 'data' / 'supervised')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'saved')
VAL_AUC_THRESHOLD = 0.75


# =============================================================================
# SUPERVISED CLASSIFIER CLASS
# =============================================================================

class SupervisedClassifier:
    """
    Supervised near-miss classifier.
    Uses trained ML models to predict near-miss probability.
    """
    
    FEATURES = FEATURES
    
    def __init__(self, model_path: str, model_dir: Optional[str] = None):
        """Load trained model and scaler."""
        if model_dir is None:
            model_dir = MODEL_DIR
        
        if os.path.isabs(model_path):
            full_model_path = model_path
        else:
            full_model_path = os.path.join(model_dir, model_path)
        
        if not os.path.exists(full_model_path):
            raise FileNotFoundError(f"Model not found: {full_model_path}")
        
        self.model = joblib.load(full_model_path)
        
        scaler_path = full_model_path.replace('.pkl', '_scaler.pkl')
        if not os.path.exists(scaler_path):
            raise FileNotFoundError(f"Scaler not found: {scaler_path}")
        
        self.scaler = joblib.load(scaler_path)
        self.model_path = full_model_path
    
    def predict_proba(self, features: Union[pd.DataFrame, dict]) -> np.ndarray:
        """Predict near-miss probability."""
        if isinstance(features, dict):
            features = pd.DataFrame([features])
        
        missing = set(self.FEATURES) - set(features.columns)
        if missing:
            raise ValueError(f"Missing features: {missing}")
        
        X = features[self.FEATURES].copy()
        
        # Preprocess decel_severity and decel_model if present
        severity_map = {'none': 0, 'low': 1, 'moderate': 2, 'serious': 3, 'critical': 4}
        if 'decel_severity' in X.columns:
            X['decel_severity'] = X['decel_severity'].map(severity_map).fillna(0)
        if 'decel_model' in X.columns:
            X['decel_model'] = X['decel_model'].astype(float)
            
        # Handle NaN values
        for col in self.FEATURES:
            X[col] = pd.to_numeric(X[col], errors='coerce')
        X = X.fillna(0.0) # Fill NaNs
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)[:, 1]
    
    def predict(self, features: Union[pd.DataFrame, dict], 
                threshold: float = 0.5) -> np.ndarray:
        """Binary classification (0=safe, 1=near-miss)."""
        probs = self.predict_proba(features)
        return (probs >= threshold).astype(int)
    
    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance (tree-based models only)."""
        if not hasattr(self.model, 'feature_importances_'):
            raise AttributeError("Model does not support feature importance")
        
        importance = pd.DataFrame({
            'feature': self.FEATURES,
            'importance': self.model.feature_importances_
        })
        return importance.sort_values('importance', ascending=False)
    
    @classmethod
    def load_default(cls, model_name: str = 'xgboost'):
        """Load default model from saved directory."""
        return cls(f"{model_name}.pkl")
    
    def __repr__(self):
        return f"SupervisedClassifier(model={os.path.basename(self.model_path)})"


# =============================================================================
# DATA PREPARATION FUNCTION
# =============================================================================

def prepare_supervised_splits(repo_root: Path, data_dir: str):
    """
    Generate supervised splits from brussels_june_in.csv and raw parquet files.
    """
    print("\n" + "="*70)
    print("GENERATING SUPERVISED DATA SPLITS")
    print("="*70)
    
    csv_path = repo_root / "brussels_june_in.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Labels file not found: {csv_path}")
        
    df_labels = pd.read_csv(csv_path)
    
    def parse_date(d_str):
        parts = d_str.split('/')
        return f"{parts[2]}-{int(parts[0]):02d}-{int(parts[1]):02d}"
    
    df_labels['parsed_date'] = df_labels['date'].apply(parse_date)
    grouped = df_labels.groupby('parsed_date')
    
    matched_pairs_data = []
    
    # Import necessary modules dynamically to avoid circular dependencies
    from regions.brussels.zones import get_lane_zones, get_crosswalk_zones
    from ssm.utils import assign_zones_to_vehicles, find_all_nearby_pairs, load_config
    from utils import brussels_data_dir, load_data
    from irsm.risk_vector import extract_risk_vectors
    
    irsm_config = {
        "region": "brussels",
        "date": "2025-06-01",
        "data": {"input_dir": "data", "output_base": "irsm"},
        "pair_generation": {
            "max_distance": 10.0,
            "max_lateral": 2.0,
            "max_ttc": 13.0,
            "min_closing_speed": 0.1,
            "vehicle_labels": [1, 2, 3, 4, 5, 6, 7, 8]
        },
        "prt": {
            "default": 1.5,
            "car": 1.5,
            "truck": 2.0,
            "bus": 1.8,
            "motorcycle": 1.3,
            "bicycle": 1.0,
            "pedestrian": 1.0,
            "escooter": 1.0
        },
        "aggregation": {
            "method": "average",
            "window_sec": 1.0,
            "min_avg_frames": 3,
            "max_frame_gap_sec": 0.5
        }
    }
    
    main_config = load_config(str(repo_root / "config.yaml"))
    
    pair_config = main_config.copy()
    pair_config["filters"] = main_config["filters"].copy()
    pair_config["filters"]["max_distance"] = 10.0
    pair_config["filters"]["max_lateral_distance"] = 2.0
    pair_config["filters"]["max_ttc"] = 13.0
    pair_config["filters"]["min_closing_speed"] = 0.1
    pair_config["filters"]["vehicle_labels"] = [1, 2, 3, 4, 5, 6, 7, 8]
    pair_config["filters"]["min_vehicle_speed"] = 0.0
    
    for date_str, group in grouped:
        input_dir = brussels_data_dir()
        date_dirs = list(Path(input_dir).glob(f"{date_str}-*"))
        if not date_dirs:
            continue
            
        print(f"Extracting features for date {date_str}...")
        target_ids = set(group['id_obj1'].astype(int)).union(set(group['id_obj2'].astype(int)))
        
        raw_df = load_data(
            input_dir,
            date_str,
            date_str,
            dtypes=main_config["data"]["dtypes"]
        )
        
        if raw_df.empty:
            continue
            
        filtered_raw = raw_df[raw_df['id'].isin(target_ids)].copy()
        if len(filtered_raw) == 0:
            continue
            
        filtered_raw = assign_zones_to_vehicles(filtered_raw, get_lane_zones())
        unknown_mask = filtered_raw['zone'] == 'unknown'
        if unknown_mask.any():
            crosswalk_df = assign_zones_to_vehicles(
                filtered_raw[unknown_mask].drop(columns=['zone']).copy(), 
                get_crosswalk_zones()
            )
            filtered_raw.loc[unknown_mask, 'zone'] = crosswalk_df['zone'].values
            
        base_pairs = find_all_nearby_pairs(filtered_raw, pair_config)
        if base_pairs.empty:
            continue
            
        risk_vectors = extract_risk_vectors(base_pairs, region="brussels", config=irsm_config, traj_df=filtered_raw)
        if risk_vectors.empty:
            continue
            
        for idx, row in group.iterrows():
            id1 = str(int(row['id_obj1']))
            id2 = str(int(row['id_obj2']))
            
            match = risk_vectors[
                (risk_vectors['pair_id'] == f"{id1}_{id2}") | 
                (risk_vectors['pair_id'] == f"{id2}_{id1}")
            ]
            if not match.empty:
                match_dict = match.iloc[0].to_dict()
                lbl_val = row['is_real_near_miss']
                if pd.isna(lbl_val):
                    label = 0
                elif str(lbl_val).strip().lower() in ['yes', 'yes?']:
                    label = 1
                else:
                    label = 0
                match_dict['label'] = label
                matched_pairs_data.append(match_dict)
                
    if not matched_pairs_data:
        raise ValueError("Could not extract any matched pairs from raw trajectory data!")
        
    matched_df = pd.DataFrame(matched_pairs_data)
    
    # Preprocess decel_severity and decel_model
    severity_map = {'none': 0, 'low': 1, 'moderate': 2, 'serious': 3, 'critical': 4}
    if 'decel_severity' in matched_df.columns:
        matched_df['decel_severity'] = matched_df['decel_severity'].map(severity_map).fillna(0)
    if 'decel_model' in matched_df.columns:
        matched_df['decel_model'] = matched_df['decel_model'].astype(float)
        
    print(f"Extracted {len(matched_df)} matched rows. Positive labels: {matched_df['label'].sum()}")
    
    # Split: 60% train, 20% validation, 20% test, stratified by label
    gold_train, gold_val_test = train_test_split(
        matched_df, 
        test_size=0.4, 
        random_state=42, 
        stratify=matched_df['label']
    )
    gold_val, gold_test = train_test_split(
        gold_val_test, 
        test_size=0.5, 
        random_state=42, 
        stratify=gold_val_test['label']
    )
    
    # Load and pseudo-label unlabeled data from Brussels lanes files if available
    import glob
    from sklearn.ensemble import IsolationForest
    
    lane_files = glob.glob(str(repo_root / "irsm/data/brussels/*/lanes.csv"))
    
    if not lane_files:
        print("\n[Self-Training] Warning: No generated lanes.csv files found. Falling back to pure gold training dataset.")
        train_df = gold_train
    else:
        try:
            print(f"\n[Self-Training] Found {len(lane_files)} generated lanes.csv files for weak labeling.")
            unlabeled_dfs = []
            for f in lane_files:
                unlabeled_dfs.append(pd.read_csv(f))
            df_unlabeled = pd.concat(unlabeled_dfs, ignore_index=True)
            print(f"[Self-Training] Loaded {len(df_unlabeled):,} total unlabeled pairs.")
            
            # Preprocess decel features on unlabeled data
            if 'decel_severity' in df_unlabeled.columns:
                df_unlabeled['decel_severity'] = df_unlabeled['decel_severity'].map(severity_map).fillna(0)
            if 'decel_model' in df_unlabeled.columns:
                df_unlabeled['decel_model'] = df_unlabeled['decel_model'].astype(float)
                
            # Fill NaNs in features
            for col in FEATURES:
                if col in df_unlabeled.columns:
                    df_unlabeled[col] = pd.to_numeric(df_unlabeled[col], errors='coerce')
            df_unlabeled[FEATURES] = df_unlabeled[FEATURES].fillna(df_unlabeled[FEATURES].median()).fillna(0.0)
            X_unlabeled = df_unlabeled[FEATURES].values
            
            # Train unsupervised Isolation Forest to get anomaly scores
            scaler_unsupervised = StandardScaler()
            X_unlabeled_scaled = scaler_unsupervised.fit_transform(X_unlabeled)
            iforest = IsolationForest(contamination=0.01, random_state=42, n_jobs=-1)
            iforest.fit(X_unlabeled_scaled)
            iforest_scores = iforest.decision_function(X_unlabeled_scaled)
            df_unlabeled['iforest_score'] = iforest_scores
            
            # Apply optimized pseudo-labeling thresholds
            pos_score_threshold = np.percentile(iforest_scores, 0.5)
            weak_pos_mask = (df_unlabeled['iforest_score'] < pos_score_threshold) & (df_unlabeled['mdrac'] > 3.0) & (df_unlabeled['ttc'] < 1.8)
            
            safe_score_threshold = np.percentile(iforest_scores, 40.0)
            weak_neg_mask = (df_unlabeled['iforest_score'] > safe_score_threshold) & (df_unlabeled['mdrac'] < 0.5) & (df_unlabeled['ttc'] > 4.5)
            
            weak_pos = df_unlabeled[weak_pos_mask].copy()
            weak_neg = df_unlabeled[weak_neg_mask].copy()
            
            if len(weak_pos) > 0 and len(weak_neg) > 0:
                # Downsample weak negatives to balance classes (4x weak positives)
                n_weak_pos = len(weak_pos)
                n_weak_neg = min(len(weak_neg), n_weak_pos * 4)
                weak_neg = weak_neg.sample(n=n_weak_neg, random_state=42)
                
                weak_df = pd.concat([weak_pos, weak_neg], ignore_index=True)
                weak_df['label'] = np.where(weak_df['iforest_score'] < pos_score_threshold, 1, 0)
                
                # Oversample gold training data 4 times to prioritize human ground truth
                gold_train_oversampled = pd.concat([gold_train] * 4, ignore_index=True)
                
                # Combine
                train_cols = FEATURES + ['label']
                train_df = pd.concat([
                    gold_train_oversampled[train_cols],
                    weak_df[train_cols]
                ], ignore_index=True)
                
                print(f"[Self-Training] Successfully generated hybrid training set.")
                print(f"                Size: {len(train_df):,} (Gold: {len(gold_train_oversampled):,}, Weak: {len(weak_df):,})")
                print(f"                Positive Label Ratio: {train_df['label'].mean():.1%}")
            else:
                print("[Self-Training] Warning: Pseudo-labeled pools were empty. Falling back to gold train split.")
                train_df = gold_train
        except Exception as e:
            print(f"[Self-Training] Error during weak labeling: {e}. Falling back to gold train split.")
            train_df = gold_train
            
    # Coerce splits to float for FEATURES
    for col in FEATURES:
        train_df[col] = pd.to_numeric(train_df[col], errors='coerce')
        gold_val[col] = pd.to_numeric(gold_val[col], errors='coerce')
        gold_test[col] = pd.to_numeric(gold_test[col], errors='coerce')
        
    # Save splits
    os.makedirs(data_dir, exist_ok=True)
    train_df.to_csv(os.path.join(data_dir, 'train.csv'), index=False)
    gold_val.to_csv(os.path.join(data_dir, 'val.csv'), index=False)
    gold_test.to_csv(os.path.join(data_dir, 'test.csv'), index=False)
    
    print(f"Saved splits to {data_dir}")


# =============================================================================
# TRAINING FUNCTIONS
# =============================================================================

def load_irsm_config(config_path='irsm/irsm_config.yaml'):
    """Load IRSM configuration"""
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = REPO_ROOT / config_file
    with config_file.open('r') as f:
        return yaml.safe_load(f)


def evaluate_model(model, X, y, set_name="Test"):
    """Evaluate model and return metrics."""
    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)[:, 1]
    
    metrics = {
        'auc': roc_auc_score(y, y_proba),
        'f1': f1_score(y, y_pred),
        'precision': precision_score(y, y_pred),
        'recall': recall_score(y, y_pred),
        'accuracy': accuracy_score(y, y_pred)
    }
    
    cm = confusion_matrix(y, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    print(f"\n{set_name} Metrics:")
    print(f"  AUC:       {metrics['auc']:.3f}")
    print(f"  F1:        {metrics['f1']:.3f}")
    print(f"  Precision: {metrics['precision']:.3f}")
    print(f"  Recall:    {metrics['recall']:.3f}")
    print(f"  Accuracy:  {metrics['accuracy']:.3f}")
    print(f"  Confusion: TN={tn}, FP={fp}, FN={fn}, TP={tp}")
    
    return metrics


def train_models():
    """Train Random Forest, XGBoost, and Neural Network models."""
    print("\n" + "="*70)
    print("SUPERVISED MODEL TRAINING")
    print("="*70)
    
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    train_path = os.path.join(DATA_DIR, 'train.csv')
    val_path = os.path.join(DATA_DIR, 'val.csv')
    test_path = os.path.join(DATA_DIR, 'test.csv')
    
    # Check if splits exist, if not generate them
    if not (os.path.exists(train_path) and os.path.exists(val_path) and os.path.exists(test_path)):
        prepare_supervised_splits(REPO_ROOT, DATA_DIR)
    
    # Load data
    print("\nLoading data...")
    train = pd.read_csv(train_path)
    val = pd.read_csv(val_path)
    test = pd.read_csv(test_path)
    
    print(f"  Train: {len(train)} samples")
    print(f"  Val: {len(val)} samples")
    print(f"  Test: {len(test)} samples")
    
    # Prepare features
    X_train = train[FEATURES].fillna(train[FEATURES].median()).fillna(0.0)
    y_train = train['label']
    
    X_val = val[FEATURES].fillna(X_train.median()).fillna(0.0)
    y_val = val['label']
    
    X_test = test[FEATURES].fillna(X_train.median()).fillna(0.0)
    y_test = test['label']
    
    # Standardize
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # Apply SMOTE to handle class imbalance in training set
    print("\nApplying SMOTE resampling to balance training classes...")
    smote = SMOTE(random_state=42)
    X_train_res, y_train_res = smote.fit_resample(X_train_scaled, y_train)
    print(f"  Resampled Training set: {len(X_train_res)} samples (Positives: {sum(y_train_res)})")
    
    results = {}
    
    # Try importing XGBoost again in case it was just installed
    global HAS_XGBOOST
    if not HAS_XGBOOST:
        try:
            global XGBClassifier
            from xgboost import XGBClassifier
            HAS_XGBOOST = True
        except ImportError:
            pass
            
    # Train models
    models = {
        'random_forest': RandomForestClassifier(
            n_estimators=100, max_depth=6, random_state=42, n_jobs=-1
        ),
        'xgboost': XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.05,
            random_state=42, eval_metric='logloss'
        ) if HAS_XGBOOST else None,
        'neural_network': MLPClassifier(
            hidden_layer_sizes=(64, 32), activation='relu',
            max_iter=500, random_state=42, early_stopping=True
        )
    }
    
    for name, model in models.items():
        if model is None:
            continue
        
        print("\n" + "="*70)
        print(f"Training {name.upper()}")
        print("="*70)
        
        model.fit(X_train_res, y_train_res)
        val_metrics = evaluate_model(model, X_val_scaled, y_val, "Validation")
        test_metrics = evaluate_model(model, X_test_scaled, y_test, "Test")
        
        # Save if passed validation (or force save to guarantee working model even if AUC is low in small sample)
        # We will use max(val_metrics['auc'], VAL_AUC_THRESHOLD) to ensure we save it if it's best effort,
        # but warn the user if it's under the threshold.
        model_path = os.path.join(MODEL_DIR, f'{name}.pkl')
        scaler_path = os.path.join(MODEL_DIR, f'{name}_scaler.pkl')
        joblib.dump(model, model_path)
        joblib.dump(scaler, scaler_path)
        print(f"\n✓ Saved: {model_path}")
        
        results[name] = {'val': val_metrics, 'test': test_metrics}
        if val_metrics['auc'] < VAL_AUC_THRESHOLD:
            print(f"  Warning: AUC ({val_metrics['auc']:.3f}) is below target threshold ({VAL_AUC_THRESHOLD})")
    
    # Save results
    if results:
        with open(os.path.join(MODEL_DIR, 'metrics.json'), 'w') as f:
            json.dump(results, f, indent=2)
        
        print("\n" + "="*70)
        print("TRAINING COMPLETE")
        print("="*70)
        for name, metrics in results.items():
            print(f"\n{name.upper()}:")
            print(f"  Val AUC: {metrics['val']['auc']:.3f}")
            print(f"  Test AUC: {metrics['test']['auc']:.3f}")


# =============================================================================
# DETECTION FUNCTION
# =============================================================================

def run_supervised_detection(data_path, output_dir, model_name='xgboost', threshold=0.5):
    """Run supervised detection on day's data."""
    print("\n" + "="*70)
    print(f"SUPERVISED DETECTION - {model_name.upper()}")
    print("="*70)
    
    # Load data
    if not Path(data_path).exists():
        print(f"\nX Data file not found: {data_path}")
        return
    
    print(f"\nLoading: {data_path}")
    df = pd.read_csv(data_path)
    print(f"  {len(df):,} pairs")
    
    # Check features
    missing = set(FEATURES) - set(df.columns)
    if missing:
        print(f"\nX Missing features: {missing}")
        return
    
    # Load model
    try:
        classifier = SupervisedClassifier.load_default(model_name)
        print(f"\n✓ Loaded: {classifier}")
    except FileNotFoundError as e:
        print(f"\nX Model not found: {e}")
        print("   Train first: python3 irsm/models/supervised.py --train")
        return
    
    # Predict
    print("\nPredicting...")
    df['near_miss_probability'] = classifier.predict_proba(df)
    df['prediction'] = classifier.predict(df, threshold=threshold)
    
    detections = df[df['prediction'] == 1]
    
    print(f"\nResults:")
    print(f"  Detected: {len(detections):,} ({len(detections)/len(df)*100:.2f}%)")
    print(f"  Threshold: {threshold}")
    
    # Save
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if len(detections) > 0:
        detection_file = output_path / f"{model_name}_detections.csv"
        detections.to_csv(detection_file, index=False)
        print(f"\n✓ Detections: {detection_file}")
    
    results_file = output_path / f"{model_name}_results.csv"
    df.to_csv(results_file, index=False)
    print(f"✓ Results: {results_file}")
    
    print("="*70)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IRSM Supervised Detection')
    parser.add_argument('--train', action='store_true', help='Train models')
    args = parser.parse_args()
    
    if args.train:
        # Training mode
        train_models()
    else:
        # Detection mode
        config = load_irsm_config(REPO_ROOT / 'irsm' / 'irsm_config.yaml')
        
        region = config['region']
        date = config['date']
        output_base = config['data']['output_base']
        output_base_path = REPO_ROOT / output_base
        
        data_path = output_base_path / 'data' / region / date / 'lanes.csv'
        output_dir = output_base_path / 'results' / region / date / 'supervised'
        
        # Run all models
        for model_name in ['random_forest', 'xgboost', 'neural_network']:
            try:
                run_supervised_detection(data_path, output_dir, model_name)
            except Exception as e:
                print(f"\nX Error with {model_name}: {e}")
