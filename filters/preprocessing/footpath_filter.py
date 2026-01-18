"""
Footpath zone filtering - removes vehicles in pedestrian-only areas.

Filters based on:
1. Vehicle type (trucks/buses forbidden)
2. Speed limits per vehicle type
"""

import pandas as pd
import gc


def apply_footpath_zone_filter(df):
    """
    Remove vehicles that shouldn't be in footpath zones based on:
    1. Speed limits per vehicle type
    2. Forbidden vehicle types (trucks, buses)
    Memory-optimized with aggressive cleanup.
    """
    max_speed = {
        1: 4.0,   # pedestrian
        2: 6.0,   # bicycle
        3: 12.0,  # motorcycle
        4: 12.0,  # car
        5: 4.0,   # escooter
        6: 12.0,  # van
        7: 0.0,   # truck - forbidden
        8: 0.0,   # bus - forbidden
    }

    df_zone = df[df["zone"].notnull()].copy()
    speed_limit_series = df_zone["label"].map(max_speed)

    # Vehicles that shouldn't be in footpath zones
    forbidden_mask = df_zone["label"].isin([3, 4, 5, 6, 7, 8])

    # Vehicles exceeding speed limits
    speed_exceed_mask = df_zone["vel"] > speed_limit_series

    remove_mask = forbidden_mask | speed_exceed_mask

    removed_ids = df_zone.loc[remove_mask, "id"].unique()
    
    # Clean up intermediate variables immediately
    del df_zone, speed_limit_series, forbidden_mask, speed_exceed_mask, remove_mask
    
    df = df.loc[~df["id"].isin(removed_ids)].copy()

    print(f"[footpath zone] Removed {len(removed_ids)} objects")
    
    # Clean up IDs
    del removed_ids
    gc.collect()

    return df
