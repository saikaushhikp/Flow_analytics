import os
import sys
import pandas as pd
import numpy as np
import argparse
from pathlib import Path
from sklearn.metrics import precision_recall_curve, auc, roc_auc_score, precision_score, recall_score, f1_score

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from irsm.canonical_utils import CANONICAL_COLUMNS

def parse_date(date_str):
    """Normalize date strings MM/DD/YYYY or YYYY-MM-DD to YYYY-MM-DD."""
    if '-' in str(date_str):
        return str(date_str).strip()
    parts = str(date_str).split('/')
    if len(parts) == 3:
        return f"{parts[2]}-{int(parts[0]):02d}-{int(parts[1]):02d}"
    return str(date_str).strip()

def load_gold_labels(gold_path):
    """Load and standardize gold labels from brussels_june_in.csv."""
    if not os.path.exists(gold_path):
        raise FileNotFoundError(f"Gold labels not found at: {gold_path}")
        
    df = pd.read_csv(gold_path)
    df['parsed_date'] = df['date'].apply(parse_date)
    
    # Parse label_gold
    def parse_label(val):
        if pd.isna(val):
            return 0
        v_str = str(val).strip().lower()
        if v_str in ['yes', 'yes?']:
            return 1
        return 0
        
    df['label_gold'] = df['is_real_near_miss'].apply(parse_label)
    
    # Standardize pair_id: min_id_max_id
    def make_pair_id(r):
        try:
            i1, i2 = int(r['id_obj1']), int(r['id_obj2'])
            return f"{min(i1, i2)}_{max(i1, i2)}"
        except (ValueError, TypeError):
            return f"{min(str(r['id_obj1']), str(r['id_obj2']))}_{max(str(r['id_obj1']), str(r['id_obj2']))}"
            
    df['canonical_pair_id'] = df.apply(make_pair_id, axis=1)
    
    # Parse LiDAR_artifact
    df['is_lidar_artifact'] = df['LiDAR_artifact'].fillna('No')
    
    # Keep essential columns
    gold_df = df[['parsed_date', 'canonical_pair_id', 'label_gold', 'is_lidar_artifact', 'replay_link']].copy()
    gold_df.columns = ['date', 'pair_id', 'label_gold', 'is_lidar_artifact', 'replay_link']
    
    # Deduplicate in case same pair is listed multiple times on the same date
    # Keep the one with positive label if discrepancy
    gold_df = gold_df.sort_values(by=['date', 'pair_id', 'label_gold'], ascending=[True, True, False])
    gold_df = gold_df.drop_duplicates(subset=['date', 'pair_id'], keep='first')
    
    return gold_df

def evaluate_predictions(preds_df, gold_df, source_family, date_str):
    """Compute metrics for a single detector family on a given day."""
    if preds_df.empty:
        return {}
        
    # Standardize pair_id in predictions
    preds_df = preds_df.copy()
    
    # Join with gold labels
    # We do a left join to align prediction with gold labels
    aligned = pd.merge(preds_df, gold_df, on=['date', 'pair_id'], how='left', suffixes=('', '_gold_df'))
    
    # Fill missing gold labels with 0 (since they are unlabeled and assumed safe)
    aligned['label_gold'] = aligned['label_gold'].fillna(0).astype(int)
    aligned['is_lidar_artifact'] = aligned['is_lidar_artifact'].fillna('No')
    
    # Filter out LiDAR artifacts from metric computations (as per PLAN.md)
    # But count them separately
    total_lidar_artifacts = (aligned['is_lidar_artifact'] == 'Yes').sum()
    
    metrics_subset = compute_set_metrics(aligned[aligned['is_lidar_artifact'] != 'Yes'], label_col='label_gold', score_col='score_raw')
    
    # Add info
    metrics_subset['lidar_artifacts'] = total_lidar_artifacts
    metrics_subset['total_pairs'] = len(aligned)
    metrics_subset['gold_positives_in_preds'] = (aligned['label_gold'] == 1).sum()
    
    return metrics_subset

def compute_set_metrics(df, label_col='label_gold', score_col='score_raw'):
    """Compute ROC-AUC, PR-AUC, and P/R @ 5, 10, 20."""
    if df.empty or df[label_col].sum() == 0:
        return {
            'roc_auc': np.nan, 'pr_auc': np.nan,
            'p5': np.nan, 'r5': np.nan,
            'p10': np.nan, 'r10': np.nan,
            'p20': np.nan, 'r20': np.nan,
            'total_positives': df[label_col].sum() if not df.empty else 0
        }
        
    y_true = df[label_col].values
    y_scores = df[score_col].values
    
    # ROC-AUC
    try:
        if len(np.unique(y_true)) > 1:
            roc_auc = roc_auc_score(y_true, y_scores)
        else:
            roc_auc = np.nan
    except Exception:
        roc_auc = np.nan
        
    # PR-AUC
    try:
        precision, recall, _ = precision_recall_curve(y_true, y_scores)
        pr_auc = auc(recall, precision)
    except Exception:
        pr_auc = np.nan
        
    # Sort descending for Precision@K and Recall@K
    df_sorted = df.sort_values(by=score_col, ascending=False).reset_index(drop=True)
    y_sorted = df_sorted[label_col].values
    total_pos = sum(y_true)
    
    p5 = sum(y_sorted[:5]) / 5.0
    r5 = sum(y_sorted[:5]) / total_pos if total_pos > 0 else 0.0
    
    p10 = sum(y_sorted[:10]) / 10.0
    r10 = sum(y_sorted[:10]) / total_pos if total_pos > 0 else 0.0
    
    p20 = sum(y_sorted[:20]) / 20.0
    r20 = sum(y_sorted[:20]) / total_pos if total_pos > 0 else 0.0
    
    return {
        'roc_auc': roc_auc,
        'pr_auc': pr_auc,
        'p5': p5, 'r5': r5,
        'p10': p10, 'r10': r10,
        'p20': p20, 'r20': r20,
        'total_positives': total_pos
    }

def main():
    parser = argparse.ArgumentParser(description='Brussels Near-Miss Quality Evaluator')
    parser.add_argument('--start-date', type=str, default="2025-06-01", help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default="2025-06-07", help='End date (YYYY-MM-DD)')
    parser.add_argument('--region', type=str, default="brussels", help='Region name')
    parser.add_argument('--canonical-dir', type=str, default=None, help='Path to canonical results')
    parser.add_argument('--gold-path', type=str, default="brussels_june_in.csv", help='Path to gold labels CSV')
    args = parser.parse_args()
    
    # Load gold labels
    print(f"Loading gold labels from: {args.gold_path}...")
    try:
        gold_df = load_gold_labels(args.gold_path)
        print(f"Loaded {len(gold_df)} standardized labeled pairs.")
        print(f"  Positive gold labels: {gold_df['label_gold'].sum()}")
        print(f"  LiDAR artifacts: {(gold_df['is_lidar_artifact'] == 'Yes').sum()}")
    except Exception as e:
        print(f"Error loading gold labels: {e}")
        sys.exit(1)
        
    # Canonical predictions dir
    if args.canonical_dir is None:
        canonical_dir = REPO_ROOT / 'irsm' / 'results' / args.region
    else:
        canonical_dir = Path(args.canonical_dir)
        
    print(f"Searching for canonical predictions in: {canonical_dir}")
    
    # Date range
    dates = pd.date_range(start=args.start_date, end=args.end_date).strftime('%Y-%m-%d').tolist()
    print(f"Evaluating date range: {dates[0]} to {dates[-1]}")
    
    # Load all canonical predictions
    all_preds = []
    for d in dates:
        d_path = canonical_dir / d / 'canonical'
        if d_path.exists():
            for f in d_path.glob("*.csv"):
                try:
                    df = pd.read_csv(f)
                    # Ensure basic columns
                    missing = set(CANONICAL_COLUMNS) - set(df.columns)
                    if missing:
                        # Add missing columns
                        for col in missing:
                            df[col] = np.nan
                    all_preds.append(df)
                except Exception as e:
                    print(f"Error reading prediction file {f}: {e}")
                    
    if not all_preds:
        print("No canonical predictions found in the date range.")
        return
        
    preds_df = pd.concat(all_preds, ignore_index=True)
    preds_df['date'] = preds_df['date'].astype(str)
    print(f"Loaded {len(preds_df):,} total canonical predictions across {len(preds_df['source_family'].unique())} source families.")
    
    # Group and compute metrics
    families = preds_df['source_family'].unique()
    
    # 1. Full-Day Ranked Evaluation (Assume unlabeled are safe 0)
    print("\n" + "="*80)
    print("EVALUATION 1: FULL-DAY SHORTLIST RANKING PERFORMANCE (Unlabeled assumed Safe)")
    print("="*80)
    
    full_day_results = []
    for family in families:
        f_df = preds_df[preds_df['source_family'] == family].copy()
        
        # Aggregate daily metrics
        daily_metrics = []
        for d in dates:
            df_day = f_df[f_df['date'] == d].copy()
            if df_day.empty:
                continue
            m = evaluate_predictions(df_day, gold_df, family, d)
            if m:
                m['date'] = d
                daily_metrics.append(m)
                
        if daily_metrics:
            daily_df = pd.DataFrame(daily_metrics)
            avg_m = {
                'family': family,
                'roc_auc': daily_df['roc_auc'].mean(),
                'pr_auc': daily_df['pr_auc'].mean(),
                'p5': daily_df['p5'].mean(),
                'r5': daily_df['r5'].mean(),
                'p10': daily_df['p10'].mean(),
                'r10': daily_df['r10'].mean(),
                'p20': daily_df['p20'].mean(),
                'r20': daily_df['r20'].mean(),
                'total_pos_found': daily_df['gold_positives_in_preds'].sum(),
                'avg_lidar_fp': daily_df['lidar_artifacts'].mean()
            }
            full_day_results.append(avg_m)
            
    if full_day_results:
        res_df = pd.DataFrame(full_day_results)
        print("\nAverage Daily Metrics (Shortlist Quality):")
        print(res_df.to_markdown(index=False, floatfmt=".3f"))
    else:
        print("No daily evaluations possible.")
        
    # 2. Gold-Aligned Subset Evaluation (Only evaluate on the labeled subset)
    print("\n" + "="*80)
    print("EVALUATION 2: GOLD-ALIGNED SUBSET PERFORMANCE (Strictly Labeled Pairs Only)")
    print("="*80)
    
    gold_subset_results = []
    for family in families:
        f_df = preds_df[preds_df['source_family'] == family].copy()
        # Merge strictly on the gold labeled subset
        aligned_gold = pd.merge(f_df, gold_df, on=['date', 'pair_id'], how='inner', suffixes=('', '_gold_df'))
        # Exclude lidar artifacts
        aligned_gold = aligned_gold[aligned_gold['is_lidar_artifact'] != 'Yes']
        
        # Calculate global PR-AUC and ROC-AUC on the strictly labeled set
        if len(aligned_gold) > 0:
            m = compute_set_metrics(aligned_gold, label_col='label_gold', score_col='score_raw')
            m['family'] = family
            m['subset_size'] = len(aligned_gold)
            gold_subset_results.append(m)
            
    if gold_subset_results:
        sub_df = pd.DataFrame(gold_subset_results)
        # Select columns of interest
        cols = ['family', 'subset_size', 'roc_auc', 'pr_auc', 'p5', 'r5', 'p10', 'r10', 'p20', 'r20']
        print(sub_df[cols].to_markdown(index=False, floatfmt=".3f"))
    else:
        print("No gold-aligned subset evaluations possible.")

    # 3. Error Analysis and LiDAR Artifact Review
    print("\n" + "="*80)
    print("EVALUATION 3: DETECTOR ERROR AND SLICE ANALYSIS")
    print("="*80)
    
    # Let's show how many LiDAR artifacts are generated in the top shortlists of each model
    for family in families:
        f_df = preds_df[preds_df['source_family'] == family].copy()
        # Join with gold to see if any top ranks are LiDAR artifacts
        aligned = pd.merge(f_df, gold_df, on=['date', 'pair_id'], how='left')
        aligned['is_lidar_artifact'] = aligned['is_lidar_artifact'].fillna('No')
        
        print(f"\nModel Family: {family.upper()}")
        # Check top-20 shortlists across all dates for LiDAR artifacts
        top_20_all = aligned[aligned['rank_within_day'] <= 20]
        lidar_fp_top_20 = top_20_all[top_20_all['is_lidar_artifact'] == 'Yes']
        print(f"  LiDAR artifacts in top-20 shortlists: {len(lidar_fp_top_20)} total across dates.")
        if len(lidar_fp_top_20) > 0:
            print("  Top LiDAR Artifact pairs:")
            print(lidar_fp_top_20[['date', 'pair_id', 'rank_within_day', 'score_raw', 'link']].head().to_markdown(index=False))
            
        # Missed Positives (Gold positives not detected or ranked very low)
        # Gold positives on these dates:
        gold_pos_dates = gold_df[(gold_df['date'].isin(dates)) & (gold_df['label_gold'] == 1)]
        # Merge to see ranks
        missed = pd.merge(gold_pos_dates, f_df, on=['date', 'pair_id'], how='left')
        
        not_found = missed[missed['rank_within_day'].isna()]
        ranked_low = missed[missed['rank_within_day'] > 50]
        print(f"  Missed gold positives (unranked/not found): {len(not_found)} out of {len(gold_pos_dates)}")
        print(f"  Ranked low gold positives (rank > 50): {len(ranked_low)} out of {len(gold_pos_dates)}")
        if len(ranked_low) > 0:
            print("  Top ranked-low positives:")
            print(ranked_low[['date', 'pair_id', 'rank_within_day', 'score_raw']].head().to_markdown(index=False))

    # 4. Duplicate Event Inflation Check
    print("\n" + "="*80)
    print("EVALUATION 4: DUPLICATE-EVENT INFLATION ANALYSIS")
    print("="*80)
    for family in families:
        f_df = preds_df[preds_df['source_family'] == family].copy()
        # Check if same pair_id appears multiple times per date
        dups = f_df[f_df.duplicated(subset=['date', 'pair_id'], keep=False)]
        print(f"  Model Family: {family.upper()}")
        print(f"    Duplicate rows for same pair in a single day: {len(dups)}")
        if len(dups) > 0:
            print(f"    Example duplicate pairs:")
            print(dups[['date', 'pair_id', 'timestamp', 'score_raw']].head(6).to_markdown(index=False))

if __name__ == '__main__':
    main()
