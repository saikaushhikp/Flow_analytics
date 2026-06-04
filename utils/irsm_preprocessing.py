"""
IRSM Preprocessing Utilities

Preprocessing filters for IRSM to remove data quality issues before anomaly detection.
Adapted from Brussels MDRAC filtering pipeline.
"""

import pandas as pd
import geopandas as gpd
from shapely import wkt
from tqdm import tqdm
import gc


def apply_preprocessing_filters(df, region='brussels', config=None, verbose=True):
    """
    Apply all preprocessing filters to remove data quality issues.
    
    Filters applied (in order):
    1. Lifetime filtering - Remove short-lived IDs
    2. Footpath zone filtering - Remove pedestrian area vehicles
    3. Crosswalk zone filtering - Remove parallel-moving vehicles
    4. Static object removal - Remove parked vehicles
    
    Args:
        df: Raw trajectory DataFrame
        region: Region name ('brussels' or 'oulu')
        config: Configuration dict (loaded from config.yaml)
        verbose: Print progress messages
        
    Returns:
        Filtered DataFrame ready for near-miss detection
    """
    from filters.preprocessing import (
        filter_by_lifetime,
        attach_zones_to_objects,
        apply_footpath_zone_filter,
        compute_polygon_orientation,
        filter_parallel_vehicles,
        filter_static_objects
    )
    
    if region == 'brussels':
        from regions.brussels.zones import get_footpath_zones, get_crosswalk_zones
    elif region == 'oulu':
        from regions.oulu.zones import get_footpath_zones, get_crosswalk_zones
    else:
        raise ValueError(f"Unknown region: {region}")
    
    if config is None:
        from ssm.utils import load_config
        from utils.paths import default_config_path
        config = load_config(str(default_config_path()))
    
    initial_ids = df['id'].nunique()
    initial_rows = len(df)
    
    if verbose:
        print("\n" + "="*70)
        print("IRSM PREPROCESSING FILTERS")
        print("="*70)
        print(f"Initial: {initial_ids:,} IDs, {initial_rows:,} rows")
    
    # -------------------------------------------------------------------------
    # 1. LIFETIME FILTERING
    # -------------------------------------------------------------------------
    if verbose:
        print("\n[1/4] Lifetime filtering...")
    
    df = filter_by_lifetime(
        df, 
        config['preprocessing']['lifetime_filter']['min_lifespan']
    )
    
    if verbose:
        removed_ids = initial_ids - df['id'].nunique()
        print(f"  Removed {removed_ids:,} short-lived IDs")
        print(f"  Remaining: {df['id'].nunique():,} IDs, {len(df):,} rows")
    
    # -------------------------------------------------------------------------
    # 2. FOOTPATH ZONE FILTERING
    # -------------------------------------------------------------------------
    if verbose:
        print("\n[2/4] Footpath zone filtering...")
    
    footpath_zones = get_footpath_zones()
    zones_df = pd.DataFrame(footpath_zones)
    zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
    gdf_zones = gpd.GeoDataFrame(zones_df, geometry="geometry")
    
    df = attach_zones_to_objects(df, gdf_zones, how="left", batch_size=100000)
    df = apply_footpath_zone_filter(df)
    df = df.drop(columns=['zone'], errors='ignore')
    gc.collect()
    
    if verbose:
        print(f"  Remaining: {df['id'].nunique():,} IDs, {len(df):,} rows")
    
    # -------------------------------------------------------------------------
    # 3. CROSSWALK ZONE FILTERING
    # -------------------------------------------------------------------------
    if verbose:
        print("\n[3/4] Crosswalk zone filtering...")
    
    crosswalk_zones = get_crosswalk_zones()
    zones_df = pd.DataFrame(crosswalk_zones)
    zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
    gdf_zones = gpd.GeoDataFrame(zones_df, geometry="geometry")
    gdf_zones["orientation_deg"] = gdf_zones["geometry"].apply(compute_polygon_orientation)
    
    df = attach_zones_to_objects(df, gdf_zones, how="left", batch_size=100000)
    
    # Filter parallel vehicles per zone
    removed_ids_global = []
    df_in_zones = df[df['zone'].notnull()].copy()
    
    for zone_id in df_in_zones['zone'].unique():
        df_zone = df_in_zones[df_in_zones['zone'] == zone_id]
        orientation = gdf_zones[gdf_zones['id'] == zone_id]['orientation_deg'].iloc[0]
        parallel_ids, _ = filter_parallel_vehicles(df_zone, orientation, threshold=4.0)
        removed_ids_global.extend(parallel_ids)
    
    df = df[~df['id'].isin(removed_ids_global)]
    df = df.drop(columns=['zone'], errors='ignore')
    gc.collect()
    
    if verbose:
        print(f"  Removed {len(removed_ids_global):,} parallel vehicles")
        print(f"  Remaining: {df['id'].nunique():,} IDs, {len(df):,} rows")
    
    # -------------------------------------------------------------------------
    # 4. STATIC OBJECT REMOVAL
    # -------------------------------------------------------------------------
    if verbose:
        print("\n[4/4] Static object removal...")
    
    ids_before_static = df['id'].nunique()
    
    df = filter_static_objects(
        df, 
        static_threshold=config['preprocessing']['static_filter']['min_speed'],
        static_ratio_min=0.8
    )
    
    if verbose:
        removed_static = ids_before_static - df['id'].nunique()
        print(f"  Removed {removed_static:,} static objects")
        print(f"  Remaining: {df['id'].nunique():,} IDs, {len(df):,} rows")
    
    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    if verbose:
        print("\n" + "="*70)
        print("PREPROCESSING COMPLETE")
        print("="*70)
        total_removed_ids = initial_ids - df['id'].nunique()
        total_removed_rows = initial_rows - len(df)
        print(f"Total removed: {total_removed_ids:,} IDs ({total_removed_ids/initial_ids*100:.1f}%)")
        print(f"Total removed: {total_removed_rows:,} rows ({total_removed_rows/initial_rows*100:.1f}%)")
        print(f"Final dataset: {df['id'].nunique():,} IDs, {len(df):,} rows")
        print("="*70)
    
    return df
