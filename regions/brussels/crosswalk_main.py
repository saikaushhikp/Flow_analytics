#!/usr/bin/env python
# Brussels Crosswalk Pedestrian-Vehicle Detection
# Separate pipeline optimized for ped-vehicle near-miss detection at crosswalks

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import numpy as np
import gc
import argparse
from tqdm import tqdm
import geopandas as gpd
from shapely import wkt

# Modular imports
from utils import (
    MDRAC_RESULT_COLUMNS,
    brussels_data_dir,
    default_config_path,
    log_memory,
    log_df_memory,
    load_data,
    output_root,
    save_detection_results,
)
from filters.preprocessing import (
    filter_by_lifetime,
    attach_zones_to_objects,
    apply_footpath_zone_filter,
    compute_polygon_orientation,
    filter_parallel_vehicles,
    filter_static_objects
)
from regions.brussels.zones import get_footpath_zones, get_crosswalk_zones
from ssm.utils import load_config, find_all_nearby_pairs, get_mdrac_pairs
from ssm.m_drac import ModifiedDRAC

# Configuration - CLI arguments with fallback to defaults
parser = argparse.ArgumentParser(description='Brussels Crosswalk Pedestrian-Vehicle Detection')
parser.add_argument('--start-date', type=str, default="2025-06-10",
                    help='Start date (YYYY-MM-DD). Default: 2025-06-10')
parser.add_argument('--start-time', type=str, default="00",
                    help='Start hour on the start date (HH or HH:MM). Default: 00')
parser.add_argument('--end-date', type=str, default="2025-06-10",
                    help='End date (YYYY-MM-DD). Default: 2025-06-10')
parser.add_argument('--data-dir', type=str, default=str(brussels_data_dir()),
                    help='Trajectory parquet root. Defaults to FLOW_ANALYTICS_DATA_BRUSSELS.')
parser.add_argument('--output-dir', type=str, default=str(output_root() / 'mdrac'),
                    help='Detection output root. Defaults to FLOW_ANALYTICS_OUTPUT_ROOT/mdrac.')
parser.add_argument('--config', type=str, default=str(default_config_path()),
                    help='Path to config.yaml.')
parser.add_argument('--max-hours', type=int, default=None,
                    help='Smoke-run limit: load only the first N hourly folders.')
parser.add_argument('--sample-limit', type=int, default=None,
                    help='Smoke-run limit: keep only the first N rows after loading.')
args = parser.parse_args()

START_DATE = args.start_date
END_DATE = args.end_date
DATA_DIR = args.data_dir
OUTPUT_DIR = args.output_dir

# Load base config and modify for crosswalk detection
config = load_config(args.config)

# CRITICAL: Include pedestrians and all relevant labels for crosswalk detection
config['filters']['vehicle_labels'] = [1, 2, 3, 4, 6, 7, 8]  # Ped, bike, motorcycle, car, truck, bus, van
config['filters']['min_vehicle_speed'] = 0.3  # Lower threshold for pedestrians (walking speed ~1.5 m/s)

print("="*70)
print("BRUSSELS CROSSWALK PEDESTRIAN-VEHICLE DETECTION")
print("="*70)
print(f"Date: {START_DATE} {args.start_time} to {END_DATE}")
print(f"Data: {DATA_DIR}")
print(f"Output: {OUTPUT_DIR}")
if args.max_hours:
    print(f"Smoke mode: max_hours={args.max_hours}")
if args.sample_limit:
    print(f"Smoke mode: sample_limit={args.sample_limit}")
print(f"Vehicle labels: {config['filters']['vehicle_labels']}")
print("="*70)

# ============================================================================
# DATA LOADING
# ============================================================================
print("\nLoading data...")
log_memory("Before loading")

df = load_data(
    DATA_DIR,
    START_DATE,
    END_DATE,
    start_time=args.start_time,
    dtypes=config['data']['dtypes'],
    max_hours=args.max_hours,
    sample_limit=args.sample_limit,
)

log_df_memory(df, "Loaded data")
print(f"Loaded {len(df):,} records")
df.reset_index(drop=True, inplace=True)

# ============================================================================
# PREPROCESSING
# ============================================================================
print("\n" + "="*70)
print("Lifetime Filtering")
print("="*70)

df = filter_by_lifetime(df, config['preprocessing']['lifetime_filter']['min_lifespan'])
log_df_memory(df, "After lifetime filter")

# ----------------------------------------------------------------------------
# Footpath Zone Filtering
# ----------------------------------------------------------------------------
print("\n" + "="*70)
print("Footpath Zone Filtering")
print("="*70)

footpath_zones = get_footpath_zones()
zones_df = pd.DataFrame(footpath_zones)
zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
gdf_zones = gpd.GeoDataFrame(zones_df, geometry="geometry")

print(f"Attaching footpath zones to {len(df):,} rows...")
log_memory("Before footpath zones")

df = attach_zones_to_objects(df, gdf_zones, how="left", batch_size=100000)

log_memory("After footpath zones")
print(f"\N{CHECK MARK} Zones attached! Total rows: {len(df):,}")

df = apply_footpath_zone_filter(df)
df = df.drop(columns=['zone'], errors='ignore')
gc.collect()
log_memory("After footpath filter")

# ----------------------------------------------------------------------------
# Crosswalk Zone Assignment
# ----------------------------------------------------------------------------
print("\n" + "="*70)
print("Crosswalk Zone Assignment")
print("="*70)

crosswalk_zones = get_crosswalk_zones()
zones_df = pd.DataFrame(crosswalk_zones)
zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
gdf_zones = gpd.GeoDataFrame(zones_df, geometry="geometry")
gdf_zones["orientation_deg"] = gdf_zones["geometry"].apply(compute_polygon_orientation)

print(f"Attaching crosswalk zones to {len(df):,} rows...")
log_memory("Before crosswalk zones")

df = attach_zones_to_objects(df, gdf_zones, how="left", batch_size=100000)

log_memory("After crosswalk zones")
print(f"\N{CHECK MARK} Zones attached! Total rows: {len(df):,}")

# Filter parallel vehicles (vehicles moving parallel to crosswalk, not crossing)
removed_ids_global = []
df_in_zones = df[df['zone'].notnull()].copy()

print(f"\nVehicles in crosswalk zones: {len(df_in_zones):,}")
print("Label distribution in crosswalk zones:")
print(df_in_zones['label'].value_counts())

for zone_id in df_in_zones['zone'].unique():
    df_zone = df_in_zones[df_in_zones['zone'] == zone_id]
    orientation = gdf_zones[gdf_zones['id'] == zone_id]['orientation_deg'].iloc[0]
    parallel_ids, _ = filter_parallel_vehicles(df_zone, orientation, threshold=4.0)
    removed_ids_global.extend(parallel_ids)

df = df[~df['id'].isin(removed_ids_global)]
print(f"\n[crosswalk] Removed {len(removed_ids_global):,} parallel vehicles")

# Keep only vehicles in crosswalk zones
df_crosswalk = df[df['zone'].notnull()].copy()
print(f"[crosswalk] Final vehicles in zones: {len(df_crosswalk):,}")
print("\nLabel distribution after parallel filter:")
print(df_crosswalk['label'].value_counts())

# Cleanup
del df, df_in_zones
gc.collect()
log_memory("After crosswalk zone filtering")

# ----------------------------------------------------------------------------
# Static Object Removal
# ----------------------------------------------------------------------------
print("\n" + "="*70)
print("Static Object Removal")
print("="*70)

df_crosswalk = filter_static_objects(
    df_crosswalk, 
    static_threshold=config['preprocessing']['static_filter']['min_speed'],
    static_ratio_min=0.8
)

log_df_memory(df_crosswalk, "After static filter")
print(f"Final objects for pair generation: {len(df_crosswalk):,}")
crosswalk_conflicts = pd.DataFrame(columns=MDRAC_RESULT_COLUMNS)

# ============================================================================
# PAIR GENERATION
# ============================================================================
print("\n" + "="*70)
print("CROSSWALK PAIR GENERATION")
print("="*70)

if len(df_crosswalk) > 0:
    print(f"\nGenerating pairs from {len(df_crosswalk):,} crosswalk vehicles...")
    log_memory("Before pair generation")
    
    # Generate nearby pairs within crosswalk zones
    crosswalk_base = find_all_nearby_pairs(df_crosswalk, config)
    print(f"  \N{CHECK MARK} Generated {len(crosswalk_base):,} nearby pairs")
    
    # Clean up
    del df_crosswalk
    gc.collect()
    
    if len(crosswalk_base) > 0:
        # Apply MDRAC filters with pedestrian-vehicle label sets
        print("\nApplying MDRAC filters with ped-vehicle label sets...")
        print("  Label sets: Pedestrians [1] × Vehicles [4,6,7,8,3,2]")
        print("  Skipping same-lane filter (pedestrians cross between lanes)")
        
        crosswalk_pairs = get_mdrac_pairs(
            crosswalk_base,
            config,
            skip_pair_generation=True,
            label_sets=([1], [4, 6, 7, 8, 3, 2]),  # Ped × Vehicles
            skip_same_lane_filter=True  # Critical for crossing detection
        )
        print(f"  \N{CHECK MARK} After MDRAC filters: {len(crosswalk_pairs):,} pairs")
        
        # Clean up
        del crosswalk_base
        gc.collect()
        
        # ====================================================================
        # DETECTION
        # ====================================================================
        if len(crosswalk_pairs) > 0:
            print("\n" + "="*70)
            print("PEDESTRIAN-VEHICLE CONFLICT DETECTION")
            print("="*70)
            print("Using crosswalk-specific detection parameters (reduced avg_window)")
            print(f"Input pairs: {len(crosswalk_pairs):,}")
            
            # Clean detection without label spoofing
            detector = ModifiedDRAC(config, zone_type='crosswalks')
            crosswalk_conflicts = detector.detect(crosswalk_pairs, is_pairs_data=True,
                                                 skip_label_filter=True,
                                                 skip_same_lane_filter=True)
            
            print(f"\n{'='*70}")
            print(f"Crosswalk Ped-Vehicle Conflicts: {len(crosswalk_conflicts):,}")
            print(f"{'='*70}")
            
            # Clean up
            del crosswalk_pairs
            gc.collect()
            
            if len(crosswalk_conflicts) == 0:
                print("\n!  No conflicts detected above threshold.")
        else:
            print("\n!  No crosswalk ped-vehicle pairs after filtering.")
            del crosswalk_pairs
            gc.collect()
    else:
        print("\n!  No nearby pairs found in crosswalk zones.")
        del crosswalk_base
        gc.collect()
else:
    print("\n!  No vehicles in crosswalk zones.")

crosswalk_path = save_detection_results(
    crosswalk_conflicts,
    OUTPUT_DIR,
    'mdrac',
    'brussels',
    START_DATE,
    zone_name='crosswalks'
)
print(f"\n\N{CHECK MARK} Saved to {crosswalk_path}")

# Save canonical predictions
if not crosswalk_conflicts.empty:
    crosswalk_conflicts['binary_prediction'] = 1
from irsm.canonical_utils import save_canonical_predictions
canonical_path = save_canonical_predictions(
    df=crosswalk_conflicts,
    region='brussels',
    date=START_DATE,
    source_family='mdrac',
    score_col='composite_score' if 'composite_score' in crosswalk_conflicts.columns else 'MDRAC',
    binary_pred_col='binary_prediction',
    zone='crosswalks',
    threshold_version='tuned_v1'
)
print(f"Saved canonical predictions to {canonical_path}")

print("\n" + "="*70)
print("CROSSWALK ANALYSIS COMPLETE")
print("="*70)
if 'crosswalk_conflicts' in locals():
    print(f"Total Conflicts: {len(crosswalk_conflicts):,}")
else:
    print("Total Conflicts: 0")
print("="*70)
