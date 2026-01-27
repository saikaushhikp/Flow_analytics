"""
Batch VLM Validation for Near-Miss Events

Validates multiple near-miss pairs using VLM with combined plot visualization.

Usage:
    from vlm.batch_validator import validate_pairs_batch
    
    # Define pairs to validate
    pairs = [(10520140, 10520195), (10520200, 10520250)]
    
    # Validate all pairs
    results = validate_pairs_batch(
        csv_path='/home/ubuntu/prem/results/brussels/mdrac/01/mdrac_01.csv',
        data_df=df,
        pairs=pairs,
        output_dir='results/brussels/vlm_validation'
    )
"""

import pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict
import json
from tqdm import tqdm
import gc

from vlm.utils import (
    load_mdrac_csv, 
    extract_pair_data,
    save_combined_plot
)
from vlm.vlm_backend import validate_event


def validate_pairs_batch(
    csv_path: str,
    data_df: pd.DataFrame,
    pairs: List[Tuple[int, int]] = None,
    output_dir: str = 'results/vlm_validation',
    time_window: float = None
) -> pd.DataFrame:
    """
    Validate multiple near-miss pairs using VLM.
    
    Workflow:
        1. Load CSV once → store in memory
        2. For each pair:
           a. Extract event data from CSV
           b. Generate combined plot (equal-sized subplots)
           c. Call VLM validation with plot + data
           d. Save result
           e. Clear plot memory
        3. Aggregate all results
        4. Save final CSV
    
    Args:
        csv_path: Path to MDRAC CSV file
        data_df: Full trajectory DataFrame (for plotting)
        pairs: List of (id1, id2) tuples to validate, or None to auto-detect from CSV
        output_dir: Where to save results
        save_interval: Save progress every N pairs
        time_window: Optional time window around conflict (seconds)
    
    Returns:
        DataFrame with validation results
    """
    # Step 1: Load CSV once
    print(f"Loading MDRAC data from {csv_path}...")
    mdrac_df = load_mdrac_csv(csv_path)    
    # Auto-detect pairs from CSV if not provided
    if pairs is None:
        print("Auto-detecting pairs from CSV...")
        pairs = [(int(row['id1']), int(row['id2'])) for _, row in mdrac_df.iterrows()]
        print(f"Found {len(pairs)} pairs in CSV")
    
    print(f"✓ Loaded {len(mdrac_df)} detections from CSV")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Results storage
    all_results = []
    
    # Step 2: Process each pair sequentially
    print(f"\nValidating {len(pairs)} pairs...")
    print("="*70)
    
    for idx, (id1, id2) in enumerate(tqdm(pairs, desc="Validating pairs"), start=1):
        try:
            print(f"\n[{idx}/{len(pairs)}] Processing pair ({id1}, {id2})...")
            
            # 2a. Extract event data from CSV
            event_data = extract_pair_data(mdrac_df, id1, id2)
            print(f"  ✓ Extracted event data: {event_data['interaction']} | "
                  f"MDRAC={event_data['MDRAC']:.2f}, TTC={event_data['TTC']:.2f}s")
            
            # 2b. Generate combined plot (equal-sized subplots, no metrics text)
            pair_folder = output_path / f"{id1}_{id2}"
            pair_folder.mkdir(parents=True, exist_ok=True)
            
            plot_path = save_combined_plot(
                data_df=data_df,
                id1=id1,
                id2=id2,
                event_data=event_data,
                output_path=str(pair_folder / "combined_analysis.png"),
                time_window=time_window
            )
            print(f"  ✓ Generated combined plot: {plot_path}")
            
            # 2c. VLM validation (plot + data passed separately)
            print(f"  → Calling VLM for validation...")
            validation_result = validate_event(plot_path, event_data)
            print(f"  ✓ VLM Result: {validation_result['classification']} "
                  f"({validation_result['confidence']}% confidence)")
            
            # 2d. Save result
            result = {
                'id1': id1,
                'id2': id2,
                'timestamp': event_data['timestamp'],
                'zone': event_data['zone'],
                'interaction': event_data['interaction'],
                'MDRAC': event_data['MDRAC'],
                'TTC': event_data['TTC'],
                'dist': event_data['dist'],
                'closing_speed': event_data['closing_speed'],
                'speed_diff': event_data['speed_diff'],
                'yaw_diff': event_data['yaw_diff'],
                'classification': validation_result['classification'],
                'confidence': validation_result['confidence'],
                'reasoning': validation_result['reasoning'],
                'backend': validation_result['backend'],
                'plot_path': str(plot_path)
            }
            all_results.append(result)
            
            # Save individual result JSON
            with open(pair_folder / "validation.json", 'w') as f:
                json.dump(result, f, indent=2)
            
            # 2e. Clear memory
            gc.collect()
            
            # Periodic saving
            if idx % save_interval == 0:
                temp_df = pd.DataFrame(all_results)
                temp_df.to_csv(output_path / "results_partial.csv", index=False)
                print(f"\n  ✓✓ Saved progress checkpoint: {idx}/{len(pairs)} pairs completed\n")
        
        except Exception as e:
            print(f"  ✗ Error processing pair ({id1}, {id2}): {e}")
            all_results.append({
                'id1': id1,
                'id2': id2,
                'timestamp': None,
                'zone': None,
                'interaction': None,
                'MDRAC': None,
                'TTC': None,
                'dist': None,
                'closing_speed': None,
                'speed_diff': None,
                'yaw_diff': None,
                'classification': 'error',
                'confidence': 0,
                'reasoning': f"Error: {str(e)}",
                'backend': 'none',
                'plot_path': None
            })
    
    # Step 3: Create final results DataFrame
    print("\n" + "="*70)
    print("Creating final results...")
    results_df = pd.DataFrame(all_results)
    
    # Step 4: Save final CSV
    final_path = output_path / "validation_results.csv"
    results_df.to_csv(final_path, index=False)
    print(f"✓ Saved final results to {final_path}")
        
    return results_df

