#!/usr/bin/env python
# Oulu Lane-based MDRAC Detection
# Vehicle-vehicle near-miss detection in lane zones

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
import argparse
warnings.filterwarnings('ignore')

# Modular imports
from utils import log_memory, log_df_memory, save_detection_results
from filters.preprocessing import (
    filter_by_lifetime,
    attach_zones_to_objects,
    apply_footpath_zone_filter,
    filter_static_objects
)
from regions.oulu.zones import get_footpath_zones, get_exclusion_zone, get_lane_zones
from ssm.utils import load_config, find_all_nearby_pairs, get_mdrac_pairs, assign_zones_to_vehicles
from ssm.m_drac import ModifiedDRAC

# Configuration - CLI arguments with fallback to defaults
parser = argparse.ArgumentParser(description='Oulu Lane-based MDRAC Detection')
parser.add_argument('--start-date', type=str, default="2025-08-22",
                    help='Start date (YYYY-MM-DD). Default: 2025-08-22')
parser.add_argument('--end-date', type=str, default="2025-09-11",
                    help='End date (YYYY-MM-DD). Default: 2025-09-11')
args = parser.parse_args()

START_DATE = args.start_date
END_DATE = args.end_date
DATA_DIR = "/home/ubuntu/data/uploads/oulu_data/objects/clean/objects/clean"
OUTPUT_DIR = "/home/ubuntu/results/prem/mdrac"

config = load_config("/home/ubuntu/prem/config.yaml")

print("="*70)
print("OULU LANE ANALYSIS")
print("="*70)
print(f"Date: {START_DATE} to {END_DATE}")
print("="*70)
print("="*70)
print(f"Date: {START_DATE} to {END_DATE}")
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

print("\nLoading Oulu data...")
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

# Exclusion zone filtering
print("\n" + "="*70)
print("Exclusion Zone Filtering")
print("="*70)

exclusion_zone = get_exclusion_zone()
zones_df = pd.DataFrame([exclusion_zone])
zones_df["geometry"] = zones_df["vertices"].apply(wkt.loads)
gdf_exclusion = gpd.GeoDataFrame(zones_df, geometry="geometry")

print(f"Attaching exclusion zone to {len(df):,} rows...")
df = attach_zones_to_objects(df, gdf_exclusion, how="left", batch_size=100000)

# Remove objects in exclusion zone
df = df[df['zone'].isnull()].copy()
df = df.drop(columns=['zone'], errors='ignore')
gc.collect()
log_df_memory(df, "After exclusion filter")

# Static object removal
print("\n" + "="*70)
print("Static Object Removal")
print("="*70)

df = filter_static_objects(
    df,
    static_threshold=config['preprocessing']['static_filter']['min_speed'],
    static_ratio_min=0.8
)
log_df_memory(df, "After static filter")

# ============================================================================
# LANE ZONE ASSIGNMENT
# ============================================================================
print("\n" + "="*70)
print("Lane Zone Assignment")
print("="*70)

lane_zones = get_lane_zones()
df = assign_zones_to_vehicles(df, lane_zones)

print(df['zone'].value_counts())
print(f"\nVehicles in lanes: {(df['zone'] != 'unknown').sum():,}")

df_lanes = df[df['zone'] != 'unknown'].copy()
log_df_memory(df_lanes, "Lane vehicles")

# ============================================================================
# LANE MDRAC DETECTION
# ============================================================================
print("\n" + "="*70)
print("M-DRAC Detection")
print("="*70)

print("\nGenerating nearby pairs...")
log_memory("Before pair generation")

base_pairs = find_all_nearby_pairs(df_lanes, config)
print(f"✓ Generated {len(base_pairs):,} base pairs")

# Filter pairs for M-DRAC
print("\nFiltering pairs for M-DRAC...")
mdrac_pairs = get_mdrac_pairs(base_pairs, config, skip_pair_generation=True)
print(f"✓ M-DRAC pairs after filtering: {len(mdrac_pairs):,}")

# Detect conflicts
print("\nDetecting M-DRAC conflicts...")
mdrac_detector = ModifiedDRAC(config)
lane_conflicts = mdrac_detector.detect(mdrac_pairs, is_pairs_data=True)

print(f"\n{'='*70}")
print(f"Lane M-DRAC Conflicts: {len(lane_conflicts):,}")
print(f"{'='*70}")

# Save results
if len(lane_conflicts) > 0:
    lane_path = save_detection_results(
        lane_conflicts, OUTPUT_DIR, 'mdrac', 'oulu', START_DATE, zone_name='lanes'
    )
    print(f"✓ Saved to {lane_path}")

print("\n" + "="*70)
print("OULU LANE ANALYSIS COMPLETE")
print("="*70)
print(f"Total Conflicts: {len(lane_conflicts):,}")
print("="*70)
print("\nNote: For crosswalk pedestrian-vehicle detection, run: python regions/oulu/crosswalk_main.py")
