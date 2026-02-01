"""
Supervised Near-Miss Detection Runner

Uses trained supervised models (Random Forest, XGBoost, Neural Network) to detect
near-misses in lane pair data.

Usage:
    python3 irsm/supervised_detect.py
"""

import sys
sys.path.insert(0, '/home/ubuntu/prem')

import pandas as pd
import numpy as np
from pathlib import Path
from irsm.models.supervised import SupervisedClassifier

# =============================================================================
# CONFIGURATION - EDIT THESE VARIABLES
# =============================================================================

# Path to input data
DATA_PATH = '/home/ubuntu/prem/irsm/data/brussels/2025-06-01/lanes.csv'

# Output directory (will create: {OUTPUT_DIR}/{model_name}.csv)
OUTPUT_DIR = '/home/ubuntu/prem/irsm/results/brussels/2025-06-01'

# Models to run
MODELS = ['random_forest', 'xgboost', 'neural_network']

# Classification threshold (probability >= threshold → near-miss)
THRESHOLD = 0.5

# =============================================================================
# DETECTION FUNCTION
# =============================================================================

def detect_near_misses(data_path, output_dir, models, threshold=0.5):
    """
    Run supervised detection with multiple models.
    
    Args:
        data_path: Path to lanes.csv
        output_dir: Directory to save results
        models: List of model names to run
        threshold: Probability threshold for classification
    """
    print("\n" + "="*70)
    print("SUPERVISED NEAR-MISS DETECTION")
    print("="*70)
    
    # Load data
    data_path = Path(data_path)
    if not data_path.exists():
        print(f"\n✗ Data file not found: {data_path}")
        return
    
    print(f"\nLoading data: {data_path}")
    df = pd.read_csv(data_path)
    print(f"  Total pairs: {len(df):,}")
    
    # Handle NaN values (fill with median for neural network compatibility)
    feature_cols = ['distance', 'closing_speed', 'closing_accel', 'ttc', 'mdrac', 'yaw_diff', 'yaw_rate']
    df[feature_cols] = df[feature_cols].fillna(df[feature_cols].median())
    
    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run each model
    results_summary = []
    
    for model_name in models:
        print(f"\n{'='*70}")
        print(f"MODEL: {model_name.upper()}")
        print(f"{'='*70}")
        
        try:
            # Load model
            classifier = SupervisedClassifier.load_default(model_name)
            print(f"✓ Loaded model")
            
            # Predict
            print(f"Running predictions...")
            probabilities = classifier.predict_proba(df)
            predictions = classifier.predict(df, threshold=threshold)
            
            # Add predictions to dataframe
            df_results = df.copy()
            df_results['near_miss_probability'] = probabilities
            df_results['prediction'] = predictions
            
            # Get only near-miss detections (prediction == 1)
            detections = df_results[df_results['prediction'] == 1].copy()
            
            # Save detections
            output_file = output_dir / f"{model_name}.csv"
            detections.to_csv(output_file, index=False)
            
            # Summary
            detection_rate = len(detections) / len(df) * 100
            print(f"\nResults:")
            print(f"  Detections: {len(detections):,} / {len(df):,} ({detection_rate:.1f}%)")
            print(f"  Saved: {output_file}")
            
            # Show top 5
            if len(detections) > 0:
                top_5 = detections.nlargest(5, 'near_miss_probability')
                print(f"\n  Top 5 highest risk:")
                for idx, row in top_5.iterrows():
                    if 'pair_id' in row.index:
                        id_str = row['pair_id']
                    else:
                        id_str = f"idx={idx}"
                    prob = row['near_miss_probability']
                    mdrac = row['mdrac']
                    print(f"    {id_str}: prob={prob:.3f}, mdrac={mdrac:.2f}")
            
            # Track results
            results_summary.append({
                'model': model_name,
                'detections': len(detections),
                'total': len(df),
                'rate': detection_rate,
                'output_file': str(output_file)
            })
            
        except FileNotFoundError as e:
            print(f"\n✗ Model not found: {e}")
            print(f"   Train first: python3 irsm/models/supervised.py --train")
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Final summary
    print(f"\n{'='*70}")
    print("DETECTION SUMMARY")
    print(f"{'='*70}")
    print(f"\nInput: {data_path}")
    print(f"Output: {output_dir}/")
    print(f"Threshold: {threshold}")
    print(f"\nResults:")
    
    if results_summary:
        print(f"\n{'Model':<20} {'Detections':<12} {'Rate':<10}")
        print(f"{'-'*50}")
        for result in results_summary:
            print(f"{result['model']:<20} {result['detections']:<12} {result['rate']:.1f}%")
        
        print(f"\nOutput files:")
        for result in results_summary:
            print(f"  - {result['output_file']}")
    
    print(f"\n{'='*70}")
    print("✓ DETECTION COMPLETE")
    print(f"{'='*70}\n")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    detect_near_misses(
        data_path=DATA_PATH,
        output_dir=OUTPUT_DIR,
        models=MODELS,
        threshold=THRESHOLD
    )
