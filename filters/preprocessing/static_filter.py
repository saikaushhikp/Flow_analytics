"""
Static object filtering - removes stationary vehicles (parked cars, etc.).

Identifies vehicles that remain below speed threshold for most of their lifetime.
"""

import pandas as pd
import gc


def filter_static_objects(df, static_threshold=0.5, static_ratio_min=0.8, verbose=True):
    """
    Remove stationary vehicles based on sustained low velocity.
    
    Args:
        df: Vehicle data with 'vel' column
        static_threshold: Velocity threshold (m/s) - below this is static
        static_ratio_min: Minimum ratio of static frames (0-1) to be removed
        verbose: Print filtering statistics
        
    Returns:
        Filtered DataFrame without static objects
        
    Example:
        >>> df = filter_static_objects(df, static_threshold=0.5, static_ratio_min=0.8)
        [static filter] Found 11,558 static objects
        [static filter] Removed 11,558 static objects
    """
    initial_count = len(df)
    initial_ids = df['id'].nunique()
    
    # Build per-object velocity history
    df_vel = (
        df.groupby(["id", "label"])["vel"]
        .apply(list)
        .reset_index()
    )

    # Compute lifespan
    df_vel["lifespan"] = df_vel["vel"].apply(len)

    # Count static frames
    df_vel["static_frames"] = df_vel["vel"].apply(
        lambda v: sum(vi < static_threshold for vi in v)
    )

    # Calculate static ratio
    df_vel["static_ratio"] = df_vel["static_frames"] / df_vel["lifespan"]

    # Flag static objects
    df_vel["is_static"] = df_vel["static_ratio"] >= static_ratio_min

    # Get IDs to remove
    removable_static_ids = set(
        df_vel[df_vel["is_static"]]["id"].astype(int).tolist()
    )

    if verbose:
        print(f"[static filter] Found {len(removable_static_ids):,} static objects")

    # Destroy df_vel immediately
    del df_vel
    gc.collect()

    # Remove static objects
    df = df[~df['id'].isin(removable_static_ids)]

    if verbose:
        print(f"[static filter] Removed {len(removable_static_ids):,} static objects")
        print(f"  Before: {initial_ids:,} IDs ({initial_count:,} rows)")
        print(f"  After: {df['id'].nunique():,} IDs ({len(df):,} rows)")
    
    # Clean up
    del removable_static_ids
    gc.collect()
    
    return df
