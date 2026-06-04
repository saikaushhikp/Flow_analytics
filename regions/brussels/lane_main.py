#!/usr/bin/env python
# Converted from main.ipynb
# Brussels MDRAC Analysis with Crosswalk Detection

# Standard imports
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

# Cell 3
# Modular imports
from utils import (
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
from regions.brussels.zones import get_lane_zones, get_footpath_zones, get_crosswalk_zones
from ssm.utils import load_config, assign_zones_to_vehicles
from ssm.m_drac import ModifiedDRAC

# Cell 4
# Configuration - CLI arguments with fallback to defaults
parser = argparse.ArgumentParser(description='Brussels Lane-based MDRAC Detection')
parser.add_argument('--start-date', type=str, default="2025-06-11",
                    help='Start date (YYYY-MM-DD). Default: 2025-06-11')
parser.add_argument('--end-date', type=str, default="2025-06-11",
                    help='End date (YYYY-MM-DD). Default: 2025-06-11')
parser.add_argument('--data-dir', type=str, default=str(brussels_data_dir()),
                    help='Trajectory parquet root. Defaults to PREM_DATA_BRUSSELS.')
parser.add_argument('--output-dir', type=str, default=str(output_root() / 'mdrac'),
                    help='Detection output root. Defaults to PREM_OUTPUT_ROOT/mdrac.')
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

config = load_config(args.config)

print("="*70)
print("BRUSSELS TRAFFIC ANALYSIS")
print("="*70)
print(f"Date: {START_DATE} to {END_DATE}")
print(f"Data: {DATA_DIR}")
print(f"Output: {OUTPUT_DIR}")
if args.max_hours:
    print(f"Smoke mode: max_hours={args.max_hours}")
if args.sample_limit:
    print(f"Smoke mode: sample_limit={args.sample_limit}")
print("="*70)

# Cell 5
print("\nLoading data...")
log_memory("Before loading")

df = load_data(
    DATA_DIR,
    START_DATE,
    END_DATE,
    dtypes=config['data']['dtypes'],
    max_hours=args.max_hours,
    sample_limit=args.sample_limit,
)

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
print(f"\N[CHECK MARK] Zones attached! Total rows: {len(df):,}")

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
print(f"\N[CHECK MARK] Zones attached! Total rows: {len(df):,}")

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

print(f"\N[CHECK MARK] Generated {len(base_pairs):,} base pairs")
log_memory("After pair generation")

# Filter pairs for M-DRAC 
print("\nFiltering pairs for M-DRAC...")
mdrac_pairs = get_mdrac_pairs(base_pairs, config, skip_pair_generation=True)
print(f"\N[CHECK MARK] M-DRAC pairs after filtering: {len(mdrac_pairs):,}")

# Detect conflicts from filtered pairs
print("\nDetecting M-DRAC conflicts...")
mdrac_detector = ModifiedDRAC(config)
mdrac_conflicts = mdrac_detector.detect(mdrac_pairs, is_pairs_data=True)

print(f"\n{'='*70}")
print(f"M-DRAC Conflicts: {len(mdrac_conflicts):,}")
print(f"{'='*70}")


# Cell 12
# Save M-DRAC results
mdrac_path = save_detection_results(mdrac_conflicts, OUTPUT_DIR, 'mdrac', 'brussels', START_DATE, zone_name='lanes')
print(f"Saved to {mdrac_path}")

# Cell 13
print("\n" + "="*70)
print("BRUSSELS LANE ANALYSIS COMPLETE")
print("="*70)
print(f"M-DRAC (Lanes): {len(mdrac_conflicts):,}")
print("="*70)
print("\nNote: For crosswalk pedestrian-vehicle detection, run: python regions/brussels/crosswalk_main.py")
