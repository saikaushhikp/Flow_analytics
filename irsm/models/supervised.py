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
sys.path.insert(0, '/home/ubuntu/prem')

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
from sklearn.metrics import (
    roc_auc_score, f1_score, precision_score, recall_score,
    accuracy_score, confusion_matrix
)
from sklearn.model_selection import train_test_split
import joblib
import matplotlib.pyplot as plt

# Try to import xgboost (optional)
try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


# =============================================================================
# CONFIGURATION
# =============================================================================

FEATURES = [
    'distance', 'closing_speed', 'closing_accel',
    'ttc', 'mdrac', 'yaw_diff', 'yaw_rate'
]

DATA_DIR = '/home/ubuntu/prem/irsm/data/supervised'
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
        
        X = features[self.FEATURES]
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
# TRAINING FUNCTIONS
# =============================================================================

def load_irsm_config(config_path='irsm/irsm_config.yaml'):
    """Load IRSM configuration"""
    with open(config_path, 'r') as f:
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
    
    # Load data
    print("\nLoading data...")
    train = pd.read_csv(os.path.join(DATA_DIR, 'train.csv'))
    val = pd.read_csv(os.path.join(DATA_DIR, 'val.csv'))
    test = pd.read_csv(os.path.join(DATA_DIR, 'test.csv'))
    
    print(f"  Train: {len(train)} samples")
    print(f"  Val: {len(val)} samples")
    print(f"  Test: {len(test)} samples")
    
    # Prepare features
    X_train, y_train = train[FEATURES], train['label']
    X_val, y_val = val[FEATURES], val['label']
    X_test, y_test = test[FEATURES], test['label']
    
    # Standardize
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    results = {}
    
    # Train models
    models = {
        'random_forest': RandomForestClassifier(
            n_estimators=100, max_depth=10, class_weight='balanced', 
            random_state=42, n_jobs=-1
        ),
        'xgboost': XGBClassifier(
            n_estimators=100, max_depth=6, learning_rate=0.1,
            random_state=42, eval_metric='logloss'
        ) if HAS_XGBOOST else None,
        'neural_network': MLPClassifier(
            hidden_layer_sizes=(64, 32, 16), activation='relu',
            max_iter=500, random_state=42, early_stopping=True
        )
    }
    
    for name, model in models.items():
        if model is None:
            continue
        
        print("\n" + "="*70)
        print(f"Training {name.upper()}")
        print("="*70)
        
        model.fit(X_train_scaled, y_train)
        val_metrics = evaluate_model(model, X_val_scaled, y_val, "Validation")
        test_metrics = evaluate_model(model, X_test_scaled, y_test, "Test")
        
        # Save if passed validation
        if val_metrics['auc'] >= VAL_AUC_THRESHOLD:
            model_path = os.path.join(MODEL_DIR, f'{name}.pkl')
            scaler_path = os.path.join(MODEL_DIR, f'{name}_scaler.pkl')
            joblib.dump(model, model_path)
            joblib.dump(scaler, scaler_path)
            print(f"\n✓ Saved: {model_path}")
            
            results[name] = {'val': val_metrics, 'test': test_metrics}
        else:
            print(f"\n✗ Failed validation (AUC < {VAL_AUC_THRESHOLD})")
    
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
        print(f"\n✗ Data file not found: {data_path}")
        return
    
    print(f"\nLoading: {data_path}")
    df = pd.read_csv(data_path)
    print(f"  {len(df):,} pairs")
    
    # Check features
    missing = set(FEATURES) - set(df.columns)
    if missing:
        print(f"\n✗ Missing features: {missing}")
        return
    
    # Load model
    try:
        classifier = SupervisedClassifier.load_default(model_name)
        print(f"\n✓ Loaded: {classifier}")
    except FileNotFoundError as e:
        print(f"\n✗ Model not found: {e}")
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
        config = load_irsm_config('/home/ubuntu/prem/irsm/irsm_config.yaml')
        
        region = config['region']
        date = config['date']
        output_base = config['data']['output_base']
        
        data_path = f'{output_base}/data/{region}/{date}/lanes.csv'
        output_dir = f'{output_base}/results/{region}/{date}/supervised'
        
        # Run all models
        for model_name in ['random_forest', 'xgboost', 'neural_network']:
            try:
                run_supervised_detection(data_path, output_dir, model_name)
            except Exception as e:
                print(f"\n✗ Error with {model_name}: {e}")
