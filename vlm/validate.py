"""
Near-Miss VLM Validation Script

Configure day parameter. Script auto-detects all pairs from CSV
and loads required trajectory data.
"""

import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')
sys.path.insert(0, str(Path(__file__).parent.parent))

from ssm.utils import load_config
config = load_config()
vlm_config = config.get('vlm', {})
paths_config = vlm_config.get('paths', {})

# =============================================================================
# CONFIGURATION
# =============================================================================

day = "01"  # Day to process

# =============================================================================
# Auto-construct paths
# =============================================================================

base_results = paths_config.get('base_results', '/home/ubuntu/prem/results/brussels/mdrac')
base_data = paths_config.get('base_data', '/home/ubuntu/data/uploads/objects/clean')

csv_path = f"{base_results}/{day}/mdrac_{day}.csv"
output_dir = f"{base_results}/{day}/plots"

def load_trajectory_data(csv_path, base_data):
    """Load trajectory data for required hours from CSV timestamps."""
    
    print(f"\n[1/3] Loading trajectory data...")
    
    # Read CSV to find required hours
    mdrac_df = pd.read_csv(csv_path)
    mdrac_df['hour'] = pd.to_datetime(mdrac_df['timestamp']).dt.hour
    required_hours = sorted(mdrac_df['hour'].unique())
    
    print(f"  Required hours from CSV: {required_hours}")
    
    # Load parquet files for each hour
    dfs = []
    for hour in required_hours:
        hour_dir = Path(base_data) / f"2025-06-{day}-{hour:02d}"
        
        if not hour_dir.exists():
            print(f"  ⚠ Skipping hour {hour:02d}: directory not found")
            continue
        
        parquet_files = list(hour_dir.glob("*.parquet"))
        print(f"  Loading hour {hour:02d}: {len(parquet_files)} files")
        
        for pf in parquet_files:
            try:
                df = pd.read_parquet(pf)
                dfs.append(df)
            except Exception as e:
                print(f"    Error loading {pf.name}: {e}")
    
    if not dfs:
        raise ValueError("No trajectory data loaded!")
    
    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
    
    print(f"  ✓ Loaded {len(combined_df):,} records, {combined_df['id'].nunique():,} unique IDs")
    
    return combined_df

def main():
    """Main validation workflow."""
    
    print("=" * 70)
    print("Near-Miss VLM Validation - Brussels Day", day)
    print("=" * 70)
    print(f"\nCSV: {csv_path}")
    print(f"Data: {base_data}/2025-06-{day}-XX/")
    print(f"Output: {output_dir}")
    
    # Verify CSV exists
    if not Path(csv_path).exists():
        print(f"\n✗ Error: CSV not found: {csv_path}")
        return
    
    # Load trajectory data
    try:
        data_df = load_trajectory_data(csv_path, base_data)
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Run validation
    print(f"\n[2/3] Running VLM validation...")
    print("  Mode: Auto-detect all pairs from CSV")
    
    try:
        from vlm.batch_validator import validate_pairs_batch
        
        results_df = validate_pairs_batch(
            csv_path=csv_path,
            data_df=data_df,
            pairs=None,  # Auto-detect all
            output_dir=output_dir
        )
        
        print(f"\n✓ Validation complete!")
        successful = results_df[results_df['classification'] != 'error']
        print(f"  Successful: {len(successful)}/{len(results_df)}")
        
    except Exception as e:
        print(f"✗ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Display summary
    print(f"\n[3/3] Results Summary")
    print('='*70)
    print(f"\nSaved to: {output_dir}/")
    print("\nClassification breakdown:")
    print(results_df['classification'].value_counts().to_string())
    
    if len(successful) > 0:
        print(f"\nConfidence statistics:")
        print(f"  Mean: {successful['confidence'].mean():.1f}%")
        print(f"  Median: {successful['confidence'].median():.1f}%")
    
    print("\n" + "=" * 70)
    print("✓ Validation completed!")
    print("=" * 70)

if __name__ == "__main__":
    main()
