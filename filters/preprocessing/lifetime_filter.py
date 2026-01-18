"""
Lifetime filtering - removes short-lived detections (noise/false positives).

Short-lived detections are likely noise, sensor artifacts, or false positives.
This filter removes vehicles that don't persist long enough to be considered real.
"""

import pandas as pd
import gc
from typing import Dict


def filter_by_lifetime(df: pd.DataFrame, 
                       min_lifespan_by_label: Dict[int, int],
                       verbose: bool = True) -> pd.DataFrame:
    """
    Remove short-lived vehicle detections based on detection count.
    
    Vehicles that appear for too few frames are likely:
    - Sensor noise
    - False positives
    - Tracking artifacts
    
    Args:
        df: Vehicle trajectory data with columns [id, label, timestamp]
        min_lifespan_by_label: Minimum required frames per vehicle type
            Example: {1: 30, 2: 80, 3: 60, 4: 90, ...}
        verbose: Print filtering statistics
        
    Returns:
        Filtered DataFrame without short-lived vehicles
        
    Example:
        >>> thresholds = {4: 90, 6: 100, 7: 100, 8: 180}
        >>> df_clean = filter_by_lifetime(df, thresholds)
        [lifespan filter] Removed 6,396 short-lived IDs
    """
    initial_count = len(df)
    initial_ids = df['id'].nunique()
    
    # Compute lifespan as detection count in full dataset
    lifespan = (
        df.groupby(["id", "label"])["timestamp"]
        .count()
        .reset_index(name="lifespan")
    )
    
    # Attach thresholds
    lifespan["min_required"] = lifespan["label"].map(min_lifespan_by_label)
    
    # Identify short-lived objects
    lifespan["is_outlier"] = lifespan["lifespan"] < lifespan["min_required"]
    
    # Get outlier IDs
    short_lived_ids = set(lifespan.loc[lifespan["is_outlier"], "id"].tolist())
    
    # Destroy lifespan DataFrame immediately
    del lifespan
    gc.collect()
    
    # Drop them from the cleaned dataframe
    df = df[~df["id"].isin(short_lived_ids)]
    
    if verbose:
        print(f"[lifespan filter] Removed {len(short_lived_ids):,} short-lived IDs")
        print(f"  Before: {initial_ids:,} IDs ({initial_count:,} rows)")
        print(f"  After: {df['id'].nunique():,} IDs ({len(df):,} rows)")
    
    # Clean up IDs set
    del short_lived_ids
    gc.collect()
    
    return df
