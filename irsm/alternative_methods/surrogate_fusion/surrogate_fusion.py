import os
import sys
import pandas as pd
import numpy as np
import json
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def main():
    print("\n" + "="*50)
    print("SURROGATE FUSION PIPELINE STAGING")
    print("="*50)
    
    # Load splits
    val_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'val.csv'
    test_path = REPO_ROOT / 'irsm' / 'data' / 'supervised' / 'test.csv'
    
    if not (val_path.exists() and test_path.exists()):
        print("Error: Splits not found!")
        sys.exit(1)
        
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)
    
    print(f"Loaded {len(val_df)} validation rows and {len(test_df)} test rows.")
    
    # Define surrogate rule evaluation
    # Rule 1: Baseline M-DRAC (risky if mdrac >= 3.0)
    # Rule 2: Post-filtered M-DRAC (risky if mdrac >= 3.0 AND (decel_max_deceleration < -0.8 OR ttc < 1.5))
    
    def evaluate_rule(df, prediction_mask, label_col='label'):
        y_true = df[label_col].values
        y_pred = prediction_mask.astype(int)
        
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        
        return {
            'precision': float(prec),
            'recall': float(rec),
            'f1': float(f1),
            'tp': int(tp),
            'fp': int(fp),
            'fn': int(fn),
            'tn': int(tn)
        }
        
    print("\nEvaluating rules on Validation Split:")
    # Baseline
    val_baseline_mask = val_df['mdrac'] >= 3.0
    val_baseline_metrics = evaluate_rule(val_df, val_baseline_mask)
    print("  Baseline (mdrac >= 3.0):")
    print(f"    Precision: {val_baseline_metrics['precision']:.3f}, Recall: {val_baseline_metrics['recall']:.3f}, F1: {val_baseline_metrics['f1']:.3f}")
    print(f"    FP: {val_baseline_metrics['fp']}, TP: {val_baseline_metrics['tp']}")
    
    # Filtered
    # decel_max_deceleration is deceleration (negative value represents braking)
    val_filtered_mask = (val_df['mdrac'] >= 3.0) & (
        (val_df['decel_max_deceleration'] < -0.8) | (val_df['ttc'] < 1.5)
    )
    val_filtered_metrics = evaluate_rule(val_df, val_filtered_mask)
    print("  Post-Filtered M-DRAC (requires braking response OR low TTC):")
    print(f"    Precision: {val_filtered_metrics['precision']:.3f}, Recall: {val_filtered_metrics['recall']:.3f}, F1: {val_filtered_metrics['f1']:.3f}")
    print(f"    FP: {val_filtered_metrics['fp']}, TP: {val_filtered_metrics['tp']}")
    
    print("\nEvaluating rules on Test Split:")
    test_baseline_mask = test_df['mdrac'] >= 3.0
    test_baseline_metrics = evaluate_rule(test_df, test_baseline_mask)
    print("  Baseline (mdrac >= 3.0):")
    print(f"    Precision: {test_baseline_metrics['precision']:.3f}, Recall: {test_baseline_metrics['recall']:.3f}, F1: {test_baseline_metrics['f1']:.3f}")
    print(f"    FP: {test_baseline_metrics['fp']}, TP: {test_baseline_metrics['tp']}")
    
    test_filtered_mask = (test_df['mdrac'] >= 3.0) & (
        (test_df['decel_max_deceleration'] < -0.8) | (test_df['ttc'] < 1.5)
    )
    test_filtered_metrics = evaluate_rule(test_df, test_filtered_mask)
    print("  Post-Filtered M-DRAC (requires braking response OR low TTC):")
    print(f"    Precision: {test_filtered_metrics['precision']:.3f}, Recall: {test_filtered_metrics['recall']:.3f}, F1: {test_filtered_metrics['f1']:.3f}")
    print(f"    FP: {test_filtered_metrics['fp']}, TP: {test_filtered_metrics['tp']}")
    
    # Save results
    output_dir = Path(__file__).resolve().parent / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        'validation': {
            'baseline': val_baseline_metrics,
            'filtered': val_filtered_metrics
        },
        'test': {
            'baseline': test_baseline_metrics,
            'filtered': test_filtered_metrics
        }
    }
    
    with open(output_dir / 'evaluation_metrics.json', 'w') as f:
        json.dump(results, f, indent=2)
        
    print(f"\n\N{CHECK MARK} Saved surrogate fusion metrics to: {output_dir}")

if __name__ == '__main__':
    main()
