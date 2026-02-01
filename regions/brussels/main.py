#!/usr/bin/env python
# Converted from main.ipynb
# Brussels MDRAC Analysis with Crosswalk Detection

# Cell 2
# Standard imports
import sys
sys.path.insert(0, '/home/ubuntu/prem')

import pandas as pd
import numpy as np
import gc
from tqdm import tqdm
import geopandas as gpd
from shapely import wkt

# Cell 3
# Modular imports
from utils import log_memory, log_df_memory, load_data, save_detection_results
from filters.preprocessing import (
    filter_by_lifetime,
    attach_zones_to_objects,
    apply_footpath_zone_filter,
    compute_polygon_orientation,
    filter_parallel_vehicles,
    filter_static_objects
)
from regions.brussels.zones import get_lane_zones, get_footpath_zones, get_crosswalk_zones
from ssm.utils import load_config, assign_zones_to_vehicles
from ssm.m_drac import ModifiedDRAC
from ssm.spf import SafetyPotentialField

# Cell 4
# Configuration
START_DATE = "2025-06-01"
END_DATE = "2025-06-01"
DATA_DIR = "/home/ubuntu/data/uploads/objects/clean"
OUTPUT_DIR = "/home/ubuntu/results/prem/mdrac"

config = load_config("/home/ubuntu/prem/config.yaml")

print("="*70)
print("BRUSSELS TRAFFIC ANALYSIS")
print("="*70)
print(f"Date: {START_DATE} to {END_DATE}")
print("="*70)

# Cell 5
print("\nLoading data...")
log_memory("Before loading")

df = load_data(DATA_DIR, START_DATE, END_DATE, dtypes=config['data']['dtypes'])

log_df_memory(df, "Loaded data")
print(f"Loaded {len(df):,} records")
df.reset_index(drop=True, inplace=True)

# Cell 6
print("\n" + "="*70)
print("Lifetime Filtering")
print("="*70)

df = filter_by_lifetime(df, config['preprocessing']['lifetime_filter']['min_lifespan'])
log_df_memory(df, "After lifetime filter")

# Cell 7
print("\n" + "="*70)
print("Footpath Zone Filtering")
print("="*70)

footpath_zones = get_footpath_zones()
zones_df = pd.DataFrame(footpath_zones)
zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
gdf_zones = gpd.GeoDataFrame(zones_df, geometry="geometry")

# CRITICAL: Call attach_zones_to_objects ONCE
print(f"Attaching footpath zones to {len(df):,} rows...")
log_memory("Before footpath zones")

df = attach_zones_to_objects(df, gdf_zones, how="left", batch_size=100000)

log_memory("After footpath zones")
print(f"✓ Zones attached! Total rows: {len(df):,}")

df = apply_footpath_zone_filter(df)
df = df.drop(columns=['zone'], errors='ignore')
gc.collect()
log_memory("After footpath filter")

# Cell 8
print("\n" + "="*70)
print("Crosswalk Zone Filtering")
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
print(f"✓ Zones attached! Total rows: {len(df):,}")

# Filter parallel vehicles
removed_ids_global = []
df_in_zones = df[df['zone'].notnull()].copy()

for zone_id in df_in_zones['zone'].unique():
    df_zone = df_in_zones[df_in_zones['zone'] == zone_id]
    orientation = gdf_zones[gdf_zones['id'] == zone_id]['orientation_deg'].iloc[0]
    parallel_ids, _ = filter_parallel_vehicles(df_zone, orientation, threshold=4.0)
    removed_ids_global.extend(parallel_ids)

df = df[~df['id'].isin(removed_ids_global)]
print(f"[crosswalk] Removed {len(removed_ids_global):,} parallel vehicles")

df = df.drop(columns=['zone'], errors='ignore')
gc.collect()
log_memory("After crosswalk filter")

# Cell 9
print("\n" + "="*70)
print("Static Object Removal")
print("="*70)

df = filter_static_objects(df, 
    static_threshold=config['preprocessing']['static_filter']['min_speed'],
    static_ratio_min=0.8)

log_df_memory(df, "After static filter")

# Cell 10
print("\n" + "="*70)
print("Lane Zone Assignment")
print("="*70)

lane_zones = get_lane_zones()
df = assign_zones_to_vehicles(df, lane_zones)

print(df['zone'].value_counts())
print(f"\nVehicles in lanes: {(df['zone'] != 'unknown').sum():,}")

df_lanes = df[df['zone'] != 'unknown'].copy()
log_df_memory(df_lanes, "Lane vehicles")

# Cell 11
print("\n" + "="*70)
print("M-DRAC Detection")
print("="*70)

# Generate base pairs first (EXACT OLD CODE WORKFLOW)
from ssm.utils import find_all_nearby_pairs, get_mdrac_pairs

print("\nGenerating nearby pairs...")
log_memory("Before pair generation")

# OLD code signature: find_all_nearby_pairs(df, config)
base_pairs = find_all_nearby_pairs(df_lanes, config)

print(f"✓ Generated {len(base_pairs):,} base pairs")
log_memory("After pair generation")

# Filter pairs for M-DRAC 
print("\nFiltering pairs for M-DRAC...")
mdrac_pairs = get_mdrac_pairs(base_pairs, config, skip_pair_generation=True)
print(f"✓ M-DRAC pairs after filtering: {len(mdrac_pairs):,}\"")

# Detect conflicts from filtered pairs
print("\nDetecting M-DRAC conflicts...")
mdrac_detector = ModifiedDRAC(config)
mdrac_conflicts = mdrac_detector.detect(mdrac_pairs, is_pairs_data=True)

print(f"\n{'='*70}")
print(f"M-DRAC Conflicts: {len(mdrac_conflicts):,}")
print(f"{'='*70}")


# Cell 12
# Save M-DRAC results
if len(mdrac_conflicts) > 0:
    mdrac_path = save_detection_results(mdrac_conflicts, OUTPUT_DIR, 'mdrac', 'brussels', START_DATE, zone_name='lanes')
    print(f"Saved to {mdrac_path}")

# Cell 13
print("\n" + "="*70)
print("BRUSSELS ANALYSIS COMPLETE")
print("="*70)
print(f"M-DRAC: {len(mdrac_conflicts):,}")
print("="*70)

# ============================================================================== 
# CROSSWALK PEDESTRIAN-VEHICLE DETECTION (NEW)
# ==============================================================================

print("\n" + "="*70)
print("CROSSWALK PEDESTRIAN-VEHICLE DETECTION")
print("="*70)

# Get crosswalk zones
crosswalk_zones_list = get_crosswalk_zones()
crosswalk_zone_ids = [z['id'] for z in crosswalk_zones_list]
print(f"\nCrosswalk zones ({len(crosswalk_zones_list)}):")
for zone in crosswalk_zones_list:
    print(f"  - {zone['id']}: {zone['name']}")

# Filter base pairs to crosswalk zones
crosswalk_base = base_pairs[
    base_pairs['zone1'].isin(crosswalk_zone_ids) &
    base_pairs['zone2'].isin(crosswalk_zone_ids)
].copy()
print(f"\nBase pairs in crosswalk zones: {len(crosswalk_base):,}")

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
        skip_same_lane_filter=True  # NEW: Skip same-lane for crosswalks
    )
    print(f"  After MDRAC filters: {len(crosswalk_pairs):,} pairs")
    
    if len(crosswalk_pairs) > 0:
        # Detect near-misses with crosswalk-specific config
        print("\nDetecting pedestrian-vehicle conflicts...")
        print("  Using crosswalk-specific detection parameters (reduced avg_window)")
        
        mdrac_detector_crosswalk = ModifiedDRAC(config, zone_type='crosswalks')
        crosswalk_conflicts = mdrac_detector_crosswalk.detect(crosswalk_pairs, is_pairs_data=True)
        print(f"\n{' '*70}")
        print(f"Crosswalk Ped-Vehicle Conflicts: {len(crosswalk_conflicts):,}")
        print(f"{'='*70}")
        
        # Show label distribution
        if len(crosswalk_conflicts) > 0:
            print("\nLabel combination distribution:")
            label_combos = crosswalk_conflicts[['label1', 'label2']].value_counts()
            for (l1, l2), count in label_combos.items():
                print(f"  ({l1}, {l2}): {count}")
            
            # Save results
            crosswalk_path = save_detection_results(
                crosswalk_conflicts, OUTPUT_DIR, 'mdrac', 'brussels', START_DATE, zone_name='crosswalks'
            )
            print(f"\nSaved to {crosswalk_path}")
    else:
        print("\n⚠️  No crosswalk ped-vehicle pairs after filtering.")
else:
    print("\n⚠️  No pairs found in crosswalk zones.")

print("\n" + "="*70)
print("BRUSSELS ANALYSIS COMPLETE (WITH CROSSWALKS)")
print("="*70)
print(f"M-DRAC (Lanes): {len(mdrac_conflicts):,}")
if 'crosswalk_conflicts' in locals() and len(crosswalk_conflicts) > 0:
    print(f"Crosswalks (Ped-Vehicle): {len(crosswalk_conflicts):,}")
print("="*70)
