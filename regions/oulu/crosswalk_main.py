#!/usr/bin/env python
# Oulu Crosswalk Pedestrian-Vehicle Detection
# Separate pipeline optimized for ped-vehicle near-miss detection at crosswalk

import sys
sys.path.insert(0, '/home/ubuntu/prem')

import os
import pandas as pd
import numpy as np
import gc
from tqdm import tqdm
import geopandas as gpd
from shapely import wkt
import warnings
warnings.filterwarnings('ignore')

# Modular imports
from utils import log_memory, log_df_memory, save_detection_results
from filters.preprocessing import (
    filter_by_lifetime,
    attach_zones_to_objects,
    apply_footpath_zone_filter,
    compute_polygon_orientation,
    filter_parallel_vehicles,
    filter_static_objects
)
from regions.oulu.zones import get_footpath_zones, get_crosswalk_zone
from ssm.utils import load_config, find_all_nearby_pairs, get_mdrac_pairs
from ssm.m_drac import ModifiedDRAC

# Configuration
START_DATE = "2025-08-22"
END_DATE = "2025-08-22"
DATA_DIR = "/home/ubuntu/data/uploads/oulu_data/objects/clean/objects/clean"
OUTPUT_DIR = "/home/ubuntu/results/prem/mdrac"

# Load base config and modify for crosswalk detection
config = load_config("/home/ubuntu/prem/config.yaml")

# Include pedestrians and all relevant labels for crosswalk detection
config['filters']['vehicle_labels'] = [1, 2, 3, 4, 6, 7, 8]  # Ped, bike, motorcycle, car, truck, bus, van
config['filters']['min_vehicle_speed'] = 0.3  # Lower threshold for pedestrians

print("="*70)
print("OULU CROSSWALK PEDESTRIAN-VEHICLE DETECTION")
print("="*70)
print(f"Date: {START_DATE} to {END_DATE}")
print(f"Vehicle labels: {config['filters']['vehicle_labels']}")
print("="*70)

# ============================================================================
# DATA LOADING
# ============================================================================
def load_oulu_data(data_dir, start_date, end_date):
    """Load Oulu data from hourly parquet folders."""
    dfs = []
    folders = sorted([f for f in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, f))])
    
    for folder in tqdm(folders, desc="Loading data"):
        try:
            folder_date = folder[:10]  # YYYY-MM-DD
            if folder_date < start_date or folder_date > end_date:
                continue
            
            folder_path = os.path.join(data_dir, folder)
            df_hour = pd.read_parquet(folder_path)
            dfs.append(df_hour)
        except Exception as e:
            print(f"Error loading {folder}: {e}")
            continue
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        print(f"\n✓ Loaded {len(df):,} records from {len(dfs)} hour folders")
        return df
    else:
        print("No data found for given date range.")
        return pd.DataFrame()

print("\nLoading data...")
log_memory("Before loading")

df = load_oulu_data(DATA_DIR, START_DATE, END_DATE)
log_df_memory(df, "Loaded data")
df.reset_index(drop=True, inplace=True)

# ============================================================================
# PREPROCESSING
# ============================================================================
print("\n" + "="*70)
print("Lifetime Filtering")
print("="*70)

df = filter_by_lifetime(df, config['preprocessing']['lifetime_filter']['min_lifespan'])
log_df_memory(df, "After lifetime filter")

# Footpath filtering
print("\n" + "="*70)
print("Footpath Zone Filtering")
print("="*70)

footpath_zones = get_footpath_zones()
zones_df = pd.DataFrame(footpath_zones)
zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
gdf_zones = gpd.GeoDataFrame(zones_df, geometry="geometry")

print(f"Attaching footpath zones to {len(df):,} rows...")
df = attach_zones_to_objects(df, gdf_zones, how="left", batch_size=100000)
df = apply_footpath_zone_filter(df)
df = df.drop(columns=['zone'], errors='ignore')
gc.collect()

# ============================================================================
# CROSSWALK ZONE ASSIGNMENT
# ============================================================================
print("\n" + "="*70)
print("Crosswalk Zone Assignment")
print("="*70)

crosswalk_zone = get_crosswalk_zone()
zones_df = pd.DataFrame([crosswalk_zone])
zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
gdf_zones = gpd.GeoDataFrame(zones_df, geometry="geometry")
gdf_zones["orientation_deg"] = gdf_zones["geometry"].apply(compute_polygon_orientation)

print(f"Attaching crosswalk zone to {len(df):,} rows...")
df = attach_zones_to_objects(df, gdf_zones, how="left", batch_size=100000)

print(f"\nVehicles in crosswalk zone: {df['zone'].notnull().sum():,}")
print("Label distribution in crosswalk zone:")
print(df[df['zone'].notnull()]['label'].value_counts())

# Filter parallel vehicles (vehicles moving parallel to crosswalk, not crossing)
removed_ids_global = []
df_in_zones = df[df['zone'].notnull()].copy()

for zone_id in df_in_zones['zone'].unique():
    df_zone = df_in_zones[df_in_zones['zone'] == zone_id]
    orientation = gdf_zones[gdf_zones['id'] == zone_id]['orientation_deg'].iloc[0]
    parallel_ids, _ = filter_parallel_vehicles(df_zone, orientation, threshold=4.0)
    removed_ids_global.extend(parallel_ids)

df = df[~df['id'].isin(removed_ids_global)]
print(f"\n[crosswalk] Removed {len(removed_ids_global):,} parallel vehicles")

# Keep only vehicles in crosswalk zone
df_crosswalk = df[df['zone'].notnull()].copy()
print(f"[crosswalk] Final vehicles in zone: {len(df_crosswalk):,}")
print("\nLabel distribution after parallel filter:")
print(df_crosswalk['label'].value_counts())

# Cleanup
del df, df_in_zones
gc.collect()

# ============================================================================
# STATIC OBJECT REMOVAL
# ============================================================================
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

# ============================================================================
# PAIR GENERATION
# ============================================================================
print("\n" + "="*70)
print("CROSSWALK PAIR GENERATION")
print("="*70)

if len(df_crosswalk) > 0:
    print(f"\nGenerating pairs from {len(df_crosswalk):,} crosswalk vehicles...")
    log_memory("Before pair generation")
    
    # Generate nearby pairs within crosswalk zone
    crosswalk_base = find_all_nearby_pairs(df_crosswalk, config)
    print(f"  ✓ Generated {len(crosswalk_base):,} nearby pairs")
    
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
        print(f"  ✓ After MDRAC filters: {len(crosswalk_pairs):,} pairs")
        
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
            
            # WORKAROUND: detect() calls get_mdrac_pairs again with default label_sets=([4,6,7,8], [4,6,7,8])
            # Create a mapping before spoofing labels
            pair_key = crosswalk_pairs['id1'].astype(str) + '_' + crosswalk_pairs['id2'].astype(str) + '_' + crosswalk_pairs['timestamp'].astype(str)
            label_mapping = dict(zip(pair_key, zip(crosswalk_pairs['label1'], crosswalk_pairs['label2'])))
            
            # Temporarily set all labels to 4 (car) to pass filter
            crosswalk_pairs['label1'] = 4
            crosswalk_pairs['label2'] = 4
            
            detector = ModifiedDRAC(config, zone_type='crosswalks')
            crosswalk_conflicts = detector.detect(crosswalk_pairs, is_pairs_data=True)
            
            # Restore original labels
            if len(crosswalk_conflicts) > 0:
                def restore_labels(row):
                    key = f"{int(row['id1'])}_{int(row['id2'])}_{row['timestamp']}"
                    if key in label_mapping:
                        return label_mapping[key]
                    return (row['label1'], row['label2'])
                
                restored = crosswalk_conflicts.apply(restore_labels, axis=1, result_type='expand')
                crosswalk_conflicts['label1'] = restored[0]
                crosswalk_conflicts['label2'] = restored[1]
            
            print(f"\n{'='*70}")
            print(f"Crosswalk Ped-Vehicle Conflicts: {len(crosswalk_conflicts):,}")
            print(f"{'='*70}")
            
            # Clean up
            del crosswalk_pairs
            gc.collect()
            
            # Show label distribution
            if len(crosswalk_conflicts) > 0:
                print("\nLabel combination distribution:")
                label_combos = crosswalk_conflicts[['label1', 'label2']].value_counts()
                for (l1, l2), count in label_combos.items():
                    print(f"  ({l1}, {l2}): {count}")
                
                # Save results
                crosswalk_path = save_detection_results(
                    crosswalk_conflicts,
                    OUTPUT_DIR,
                    'mdrac',
                    'oulu',
                    START_DATE,
                    zone_name='crosswalks'
                )
                print(f"\n✓ Saved to {crosswalk_path}")
            else:
                print("\n⚠️  No conflicts detected above threshold.")
        else:
            print("\n⚠️  No crosswalk ped-vehicle pairs after filtering.")
            del crosswalk_pairs
            gc.collect()
    else:
        print("\n⚠️  No nearby pairs found in crosswalk zone.")
        del crosswalk_base
        gc.collect()
else:
    print("\n⚠️  No vehicles in crosswalk zone.")

print("\n" + "="*70)
print("CROSSWALK ANALYSIS COMPLETE")
print("="*70)
if 'crosswalk_conflicts' in locals():
    print(f"Total Conflicts: {len(crosswalk_conflicts):,}")
else:
    print("Total Conflicts: 0")
print("="*70)
