import os
import sys
import pandas as pd
import numpy as np
import json
import yaml
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, precision_recall_curve, auc, 
    precision_score, recall_score, f1_score
)
import joblib

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from irsm.models.supervised import SupervisedClassifier, FEATURES
from irsm.evaluator import load_gold_labels

def main():
    print("\n" + "="*50)
    print("META-ENSEMBLE RANKER STAGING")
    print("="*50)
    
    # 1. Load data
    train_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'train.csv'
    val_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'val.csv'
    test_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'test.csv'
    
    if not (train_path.exists() and val_path.exists() and test_path.exists()):
        print("Error: Labeled splits not found!")
        sys.exit(1)
        
    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)
    
    # Load gold labels
    gold_path = str(REPO_ROOT / 'brussels_june_in.csv')
    gold_df = load_gold_labels(gold_path)
    
    # Parse dates (only val and test have timestamp columns)
    for df in [val_df, test_df]:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        
    # 2. Load models for scoring
    try:
        rf_clf = SupervisedClassifier.load_default('random_forest')
        xgb_clf = SupervisedClassifier.load_default('xgboost')
    except Exception as e:
        print(f"Error loading supervised models: {e}. Please run supervised.py --train first.")
        sys.exit(1)
        
    # Load unsupervised models configuration/logic
    # For Isolation Forest
    from sklearn.ensemble import IsolationForest
    from sklearn.covariance import ledoit_wolf
    from scipy.stats import multivariate_normal
    
    # We fit unsupervised models on train to get baseline scores
    # Safety core features are best for unsupervised
    SAFETY_CORE = [
        'mdrac', 'ttc', 'closing_speed', 'closing_accel', 'speed_diff', 
        'yaw_diff', 'yaw_rate', 'ttc_severity_score', 'traj_severity_score', 
        'env_severity_score', 'decel_avg_deceleration', 'decel_max_deceleration'
    ]
    
    # Clean features
    for df in [train_df, val_df, test_df]:
        for col in FEATURES:
            if col in df.columns:
                if df[col].dtype == object or df[col].dtype == bool:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df[col] = df[col].fillna(df[col].median()).fillna(0.0)
                
    X_train_un = train_df[SAFETY_CORE].values
    scaler_un = StandardScaler()
    X_train_un_scaled = scaler_un.fit_transform(X_train_un)
    
    # Winsorize
    lower_limits = np.percentile(X_train_un_scaled, 1, axis=0)
    upper_limits = np.percentile(X_train_un_scaled, 99, axis=0)
    X_train_un_win = np.clip(X_train_un_scaled, lower_limits, upper_limits)
    
    iforest = IsolationForest(n_estimators=300, contamination=0.01, random_state=42, n_jobs=-1)
    iforest.fit(X_train_un_win)
    
    cov_lw, _ = ledoit_wolf(X_train_un_scaled)
    mu = np.mean(X_train_un_scaled, axis=0)
    gaussian_model = multivariate_normal(mean=mu, cov=cov_lw, allow_singular=True)
    
    # Helper to compute unsupervised scores
    def get_unsupervised_scores(df):
        X = df[SAFETY_CORE].values
        X_scaled = scaler_un.transform(X)
        X_win = np.clip(X_scaled, lower_limits, upper_limits)
        
        if_scores = -iforest.decision_function(X_win)
        g_scores = -gaussian_model.logpdf(X_scaled)
        return if_scores, g_scores
        
    # 3. Build features for Meta-Ensemble
    def extract_meta_features(df):
        rf_prob = rf_clf.predict_proba(df)
        xgb_prob = xgb_clf.predict_proba(df)
        if_scores, g_scores = get_unsupervised_scores(df)
        
        # Scale/normalize unsupervised scores
        z_if = (if_scores - np.mean(if_scores)) / (np.std(if_scores) + 1e-8)
        z_g = (g_scores - np.mean(g_scores)) / (np.std(g_scores) + 1e-8)
        
        mdrac_composite = df['mdrac'].values * (1.0 / (df['ttc'].values + 0.1))
        z_composite = (mdrac_composite - np.mean(mdrac_composite)) / (np.std(mdrac_composite) + 1e-8)
        
        meta_X = np.column_stack([
            z_composite,
            z_if,
            z_g,
            rf_prob,
            xgb_prob
        ])
        return meta_X
        
    print("\nExtracting meta-features...")
    X_train_meta = extract_meta_features(train_df)
    X_val_meta = extract_meta_features(val_df)
    X_test_meta = extract_meta_features(test_df)
    
    y_train = train_df['label'].values
    y_val = val_df['label'].values
    y_test = test_df['label'].values
    
    # 4. Train Meta-Ensemble Ranker (Logistic Regression)
    # We train on the gold (non-weak) portion of the training set to prevent self-training bias
    gold_mask = train_df['is_weak'] == 0
    X_train_gold = X_train_meta[gold_mask]
    y_train_gold = y_train[gold_mask]
    
    print(f"Training Logistic Regression meta-ranker on {len(X_train_gold)} gold training samples...")
    meta_scaler = StandardScaler()
    X_train_gold_scaled = meta_scaler.fit_transform(X_train_gold)
    
    meta_model = LogisticRegression(random_state=42)
    meta_model.fit(X_train_gold_scaled, y_train_gold)
    
    # 5. Evaluate on Validation and Test Sets
    X_val_scaled = meta_scaler.transform(X_val_meta)
    X_test_scaled = meta_scaler.transform(X_test_meta)
    
    val_probs = meta_model.predict_proba(X_val_scaled)[:, 1]
    test_probs = meta_model.predict_proba(X_test_scaled)[:, 1]
    
    # Helper to evaluate daily shortlist Precision@10
    def evaluate_shortlist(df, probs, gold_df, top_k=10):
        temp_df = df.copy()
        temp_df['score'] = probs
        
        # Exclude lidar artifacts
        temp_df = pd.merge(temp_df, gold_df, on=['date', 'pair_id'], how='left', suffixes=('', '_gold'))
        temp_df['label_gold'] = temp_df['label_gold'].fillna(temp_df['label']).fillna(0).astype(int)
        temp_df['is_lidar_artifact'] = temp_df['is_lidar_artifact'].fillna('No')
        temp_df = temp_df[temp_df['is_lidar_artifact'] != 'Yes']
        
        dates = temp_df['date'].unique()
        daily_precisions = []
        for d in dates:
            day_df = temp_df[temp_df['date'] == d]
            if day_df.empty:
                daily_precisions.append(0.0)
                continue
            day_top = day_df.sort_values(by='score', ascending=False).head(top_k)
            tp = (day_top['label_gold'] == 1).sum()
            daily_precisions.append(tp / float(top_k))
            
        return np.mean(daily_precisions) if daily_precisions else 0.0
        
    val_p10 = evaluate_shortlist(val_df, val_probs, gold_df)
    test_p10 = evaluate_shortlist(test_df, test_probs, gold_df)
    
    val_auc = roc_auc_score(y_val, val_probs)
    test_auc = roc_auc_score(y_test, test_probs)
    
    print("\n" + "="*40)
    print("META-ENSEMBLE PERFORMANCE")
    print("="*40)
    print(f"Validation AUC:          {val_auc:.3f}")
    print(f"Validation Precision@10: {val_p10:.3f}")
    print(f"Test AUC:                {test_auc:.3f}")
    print(f"Test Precision@10:       {test_p10:.3f}")
    
    # Save model artifacts
    output_dir = Path(__file__).resolve().parent / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(meta_model, output_dir / 'meta_ensemble_model.pkl')
    joblib.dump(meta_scaler, output_dir / 'meta_ensemble_scaler.pkl')
    
    # Save metrics JSON
    metrics = {
        'val_auc': val_auc,
        'val_precision_at_10': val_p10,
        'test_auc': test_auc,
        'test_precision_at_10': test_p10,
        'coefficients': {
            'composite_mdrac': float(meta_model.coef_[0][0]),
            'isolation_forest': float(meta_model.coef_[0][1]),
            'gaussian_anomaly': float(meta_model.coef_[0][2]),
            'random_forest_prob': float(meta_model.coef_[0][3]),
            'xgboost_prob': float(meta_model.coef_[0][4])
        },
        'intercept': float(meta_model.intercept_[0])
    }
    
    with open(output_dir / 'evaluation_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)
        
    print(f"\n\N{CHECK MARK} Meta-ensemble models and metrics saved to: {output_dir}")

if __name__ == '__main__':
    main()
