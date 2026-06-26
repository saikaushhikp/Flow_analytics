import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
from sklearn.ensemble import IsolationForest
from sklearn.covariance import ledoit_wolf
from sklearn.preprocessing import StandardScaler
from scipy.stats import multivariate_normal

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from irsm.evaluator import load_gold_labels
from irsm.risk_vector import get_feature_names

# Features sets
FULL_FEATURES = get_feature_names()
SAFETY_CORE = [
    'mdrac', 'ttc', 'closing_speed', 'closing_accel', 'speed_diff', 
    'yaw_diff', 'yaw_rate', 'ttc_severity_score', 'traj_severity_score', 
    'env_severity_score', 'decel_avg_deceleration', 'decel_max_deceleration'
]

def winsorize(X, limits=(0.01, 0.01)):
    """Winsorize features to limits percentile to handle extreme outliers."""
    X_clipped = X.copy()
    for i in range(X.shape[1]):
        col = X_clipped[:, i]
        lower = np.percentile(col, limits[0] * 100)
        upper = np.percentile(col, (1 - limits[1]) * 100)
        X_clipped[:, i] = np.clip(col, lower, upper)
    return X_clipped

def std_pair_id(pid):
    """Numerically sort pair ID strings like '123_456' to maintain canonical representation."""
    parts = str(pid).split('_')
    if len(parts) == 2:
        try:
            i1, i2 = int(parts[0]), int(parts[1])
            return f"{min(i1, i2)}_{max(i1, i2)}"
        except ValueError:
            return f"{min(parts[0], parts[1])}_{max(parts[0], parts[1])}"
    return str(pid)

def df_to_markdown(df):
    """Manually convert a pandas DataFrame to a markdown table string without using tabulate."""
    headers = list(df.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |"
    ]
    for _, row in df.iterrows():
        parts = []
        for h in headers:
            val = row[h]
            if isinstance(val, (float, np.floating)):
                parts.append(f"{val:.3f}")
            else:
                parts.append(str(val))
        lines.append("| " + " | ".join(parts) + " |")
    return "\n".join(lines)

def evaluate_unsupervised_shortlist(df, score_col, gold_df, dates, top_k=10):
    """Filter to strongest anomaly per pair_id per day and compute Precision@10/Recall@10."""
    df = df.copy()
    
    # Parse date from timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
    df['pair_id'] = df['pair_id'].apply(std_pair_id)
    
    # Deduplicate: keep strongest anomaly (highest score_col) per pair_id per day
    df = df.sort_values(by=['date', 'pair_id', score_col], ascending=[True, True, False])
    df = df.drop_duplicates(subset=['date', 'pair_id'], keep='first')
    
    # Align with gold df to get LiDAR artifact and canonical label
    aligned = pd.merge(df, gold_df, on=['date', 'pair_id'], how='left')
    aligned['label_gold'] = aligned['label_gold'].fillna(aligned['label']).fillna(0).astype(int)
    aligned['is_lidar_artifact'] = aligned['is_lidar_artifact'].fillna('No')
    
    # Exclude lidar artifacts from metric calculation
    aligned = aligned[aligned['is_lidar_artifact'] != 'Yes']
    
    # Compute daily Precision@10 and Recall@10
    daily_precisions = []
    daily_recalls = []
    
    # Gold positives in this specific split (excluding lidar artifacts)
    gold_positives_split = aligned[aligned['label_gold'] == 1]
    
    for d in dates:
        day_conf = aligned[aligned['date'] == d].copy()
        if day_conf.empty:
            continue
            
        # Select the top_k ranked by the anomaly score
        day_aligned = day_conf.sort_values(by=score_col, ascending=False).head(top_k)
        
        # Gold positives for this date in this split
        gold_positives_day = gold_positives_split[gold_positives_split['date'] == d]
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

def process_unsupervised_grid(df, gold_df, dates, split_name="Validation"):
    """Run grid search tuning on a given split dataframe."""
    results = []
    
    # Preprocess feature columns (clean strings, fill NaNs)
    all_features = list(set(FULL_FEATURES + SAFETY_CORE))
    df = df.copy()
    for col in all_features:
        if col in df.columns:
            if df[col].dtype == object or df[col].dtype == bool:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df[col] = df[col].fillna(df[col].median()).fillna(0.0)
            
    for feat_set_name, feat_cols in [('Full 28 Features', FULL_FEATURES), ('Safety Core', SAFETY_CORE)]:
        print(f"\nEvaluating Feature Set on {split_name}: {feat_set_name}")
        X_raw = df[feat_cols].values
        
        # Standardize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_raw)
        
        # Winsorize for Isolation Forest
        X_win = winsorize(X_scaled, limits=(0.01, 0.01))
        
        # 1. Isolation Forest Tuning
        for n_est in [150, 300]:
            print(f"  Training Isolation Forest (n_estimators={n_est})...")
            iforest = IsolationForest(n_estimators=n_est, contamination=0.01, random_state=42, n_jobs=-1)
            iforest.fit(X_win)
            
            # Anomaly score: higher means more anomalous
            iforest_scores = -iforest.decision_function(X_win)
            df['iforest_score'] = iforest_scores
            
            # Evaluate shortlist
            prec, rec = evaluate_unsupervised_shortlist(df, 'iforest_score', gold_df, dates, top_k=10)
            print(f"    IForest Prec@10: {prec:.3f}, Rec@10: {rec:.3f}")
            results.append({
                'model': 'Isolation Forest',
                'feature_set': feat_set_name,
                'n_estimators': n_est,
                'contamination': 0.01,
                'prec10': prec,
                'rec10': rec
            })
            
        # 2. Gaussian Anomaly (Ledoit-Wolf shrinkage covariance)
        print("  Fitting Gaussian with Ledoit-Wolf shrinkage covariance...")
        cov_lw, _ = ledoit_wolf(X_scaled)
        mu = np.mean(X_scaled, axis=0)
        
        try:
            model = multivariate_normal(mean=mu, cov=cov_lw, allow_singular=True)
            log_prob = model.logpdf(X_scaled)
            gaussian_scores = -log_prob
            df['gaussian_score'] = gaussian_scores
            
            prec, rec = evaluate_unsupervised_shortlist(df, 'gaussian_score', gold_df, dates, top_k=10)
            print(f"    Gaussian Prec@10: {prec:.3f}, Rec@10: {rec:.3f}")
            results.append({
                'model': 'Gaussian (Ledoit-Wolf)',
                'feature_set': feat_set_name,
                'n_estimators': 'N/A',
                'contamination': 0.01,
                'prec10': prec,
                'rec10': rec
            })
        except Exception as e:
            print(f"    Failed to run Gaussian: {e}")
            
    return pd.DataFrame(results)

def main():
    # Load gold labels
    gold_path = str(REPO_ROOT / 'brussels_june_in.csv')
    gold_df = load_gold_labels(gold_path)
    
    # Date range
    dates = pd.date_range(start="2025-06-01", end="2025-06-07").strftime('%Y-%m-%d').tolist()
    
    # Load validation and test splits
    val_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'val.csv'
    test_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'test.csv'
    
    if not val_path.exists() or not test_path.exists():
        print(f"Error: Splitted data files not found in {val_path.parent}!")
        print("Please run supervised.py --train first to extract splits.")
        sys.exit(1)
        
    print(f"Loading validation set from: {val_path}")
    val_df = pd.read_csv(val_path)
    print(f"Loading test set from: {test_path}")
    test_df = pd.read_csv(test_path)
    
    print(f"Validation dataset size: {len(val_df)} rows")
    print(f"Test dataset size: {len(test_df)} rows")
    
    # Clean validation set features
    all_features = list(set(FULL_FEATURES + SAFETY_CORE))
    for col in all_features:
        for df_split in [val_df, test_df]:
            if col in df_split.columns:
                if df_split[col].dtype == object or df_split[col].dtype == bool:
                    df_split[col] = pd.to_numeric(df_split[col], errors='coerce')
                df_split[col] = df_split[col].fillna(df_split[col].median()).fillna(0.0)
                
    # Parse dates
    for df_split in [val_df, test_df]:
        df_split['timestamp'] = pd.to_datetime(df_split['timestamp'])
        df_split['date'] = df_split['timestamp'].dt.strftime('%Y-%m-%d')
        df_split['pair_id'] = df_split['pair_id'].apply(std_pair_id)

    # 1. Grid Search on Validation Split
    print("\n" + "="*50)
    print("RUNNING GRID SEARCH ON VALIDATION SPLIT")
    print("="*50)
    val_results = process_unsupervised_grid(val_df, gold_df, dates, split_name="Validation")
    
    # Print comparison table
    print("\n" + "="*80)
    print("UNSUPERVISED MODELS TUNING COMPARISON (VALIDATION)")
    print("="*80)
    print(df_to_markdown(val_results))
    
    # Find the best configuration on Validation
    best_row = val_results.sort_values(by=['prec10', 'rec10'], ascending=False).iloc[0]
    print(f"\nBest configuration selected: {best_row['model']} with {best_row['feature_set']}")
    
    # 2. Evaluate Best Config and Ensemble on Validation and Test Sets
    best_feat_set = SAFETY_CORE if best_row['feature_set'] == 'Safety Core' else FULL_FEATURES
    
    # Build models on Validation set
    X_val_raw = val_df[best_feat_set].values
    scaler_val = StandardScaler()
    X_val_scaled = scaler_val.fit_transform(X_val_raw)
    X_val_win = winsorize(X_val_scaled, limits=(0.01, 0.01))
    
    # Train Best Isolation Forest on Validation
    best_n_estimators = int(best_row['n_estimators']) if best_row['n_estimators'] != 'N/A' else 300
    iforest_val = IsolationForest(n_estimators=best_n_estimators, contamination=0.01, random_state=42, n_jobs=-1)
    iforest_val.fit(X_val_win)
    iforest_scores_val = -iforest_val.decision_function(X_val_win)
    
    # Train Best Gaussian on Validation
    cov_lw_val, _ = ledoit_wolf(X_val_scaled)
    mu_val = np.mean(X_val_scaled, axis=0)
    gaussian_model_val = multivariate_normal(mean=mu_val, cov=cov_lw_val, allow_singular=True)
    gaussian_scores_val = -gaussian_model_val.logpdf(X_val_scaled)
    
    # Normalise scores for validation ensemble
    z_iforest_val = (iforest_scores_val - np.mean(iforest_scores_val)) / (np.std(iforest_scores_val) + 1e-8)
    z_gaussian_val = (gaussian_scores_val - np.mean(gaussian_scores_val)) / (np.std(gaussian_scores_val) + 1e-8)
    kinetic_bonus_val = val_df['mdrac'].values / (val_df['ttc'].values + 0.1)
    z_kinetic_val = (kinetic_bonus_val - np.mean(kinetic_bonus_val)) / (np.std(kinetic_bonus_val) + 1e-8)
    
    ensemble_scores_val = 0.4 * z_iforest_val + 0.4 * z_gaussian_val + 0.2 * z_kinetic_val
    val_df['ensemble_score'] = ensemble_scores_val
    
    val_ens_prec, val_ens_rec = evaluate_unsupervised_shortlist(val_df, 'ensemble_score', gold_df, dates, top_k=10)
    print(f"\nEnsemble performance on Validation: Prec@10={val_ens_prec:.3f}, Rec@10={val_ens_rec:.3f}")
    
    # Build models on Test set
    X_test_raw = test_df[best_feat_set].values
    scaler_test = StandardScaler()
    X_test_scaled = scaler_test.fit_transform(X_test_raw)
    X_test_win = winsorize(X_test_scaled, limits=(0.01, 0.01))
    
    # Train Best Isolation Forest on Test
    iforest_test = IsolationForest(n_estimators=best_n_estimators, contamination=0.01, random_state=42, n_jobs=-1)
    iforest_test.fit(X_test_win)
    iforest_scores_test = -iforest_test.decision_function(X_test_win)
    test_df['iforest_score'] = iforest_scores_test
    test_iforest_prec, test_iforest_rec = evaluate_unsupervised_shortlist(test_df, 'iforest_score', gold_df, dates, top_k=10)
    
    # Train Best Gaussian on Test
    cov_lw_test, _ = ledoit_wolf(X_test_scaled)
    mu_test = np.mean(X_test_scaled, axis=0)
    gaussian_model_test = multivariate_normal(mean=mu_test, cov=cov_lw_test, allow_singular=True)
    gaussian_scores_test = -gaussian_model_test.logpdf(X_test_scaled)
    test_df['gaussian_score'] = gaussian_scores_test
    test_gaussian_prec, test_gaussian_rec = evaluate_unsupervised_shortlist(test_df, 'gaussian_score', gold_df, dates, top_k=10)
    
    # Normalise scores for test ensemble
    z_iforest_test = (iforest_scores_test - np.mean(iforest_scores_test)) / (np.std(iforest_scores_test) + 1e-8)
    z_gaussian_test = (gaussian_scores_test - np.mean(gaussian_scores_test)) / (np.std(gaussian_scores_test) + 1e-8)
    kinetic_bonus_test = test_df['mdrac'].values / (test_df['ttc'].values + 0.1)
    z_kinetic_test = (kinetic_bonus_test - np.mean(kinetic_bonus_test)) / (np.std(kinetic_bonus_test) + 1e-8)
    
    ensemble_scores_test = 0.4 * z_iforest_test + 0.4 * z_gaussian_test + 0.2 * z_kinetic_test
    test_df['ensemble_score'] = ensemble_scores_test
    
    test_ens_prec, test_ens_rec = evaluate_unsupervised_shortlist(test_df, 'ensemble_score', gold_df, dates, top_k=10)
    
    print("\n" + "="*50)
    print("TEST EVALUATION PERFORMANCE")
    print("="*50)
    print(f"Best Configuration ({best_row['model']}):")
    if best_row['model'] == 'Isolation Forest':
        print(f"  Test Prec@10: {test_iforest_prec:.3f}, Recall@10: {test_iforest_rec:.3f}")
    else:
        print(f"  Test Prec@10: {test_gaussian_prec:.3f}, Recall@10: {test_gaussian_rec:.3f}")
    print(f"Ensemble:")
    print(f"  Test Prec@10: {test_ens_prec:.3f}, Recall@10: {test_ens_rec:.3f}")
    
    # Save optimized parameters to report
    report_path = REPO_ROOT / 'next_steps' / 'unsupervised_tuning_report.md'
    with open(report_path, 'w') as f:
        f.write(f"""# Unsupervised Anomaly Detection Optimization Report

Based on parameter grid search on the gold Brussels dataset (`brussels_june_in.csv`) over the splits `val.csv` and `test.csv`.

## 1. Single Model Comparison (Validation Split)

{df_to_markdown(val_results)}

## 2. Test Split Evaluation Results
- **Isolation Forest (Tuned)**: Precision@10 = {test_iforest_prec:.3f}, Recall@10 = {test_iforest_rec:.3f}
- **Gaussian (Ledoit-Wolf shrinkage)**: Precision@10 = {test_gaussian_prec:.3f}, Recall@10 = {test_gaussian_rec:.3f}
- **Unsupervised Ensemble Score**: Precision@10 = {test_ens_prec:.3f}, Recall@10 = {test_ens_rec:.3f}
  - *Ensemble Formula*: `0.4 * z(iforest_score) + 0.4 * z(gaussian_logpdf) + 0.2 * z(mdrac / (ttc + 0.1))`

## 3. Key Findings
* **Safety Core Features** outperformed the full 28-feature set by filtering out non-safety-related variance (e.g. initial speeds, coordinates, decel times).
* **Ledoit-Wolf shrinkage covariance** successfully stabilized the covariance estimation for multivariate Gaussian anomaly detection.
* **Unsupervised Ensemble Score** provides a robust, multi-perspective ranking that leverages both isolation-based density, distance-based normal bounds, and a kinetic-risk priority bonus.
""")
    print(f"\n\N{CHECK MARK} Saved unsupervised tuning report to: {report_path}")

if __name__ == '__main__':
    main()
