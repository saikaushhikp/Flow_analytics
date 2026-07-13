#!/usr/bin/env python3
"""
heatmaps.py: Brussels Near-Miss Risk Heatmap Generator.

Loads conflict detections for M-DRAC and IRSM, enriches them with coordinates 
from clean trajectory data, and generates normalized risk heatmaps using 
influence circles centered at the conflict locations.
"""

import os
import re
import sys
import glob
import time
import gc
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely import wkt
from pathlib import Path

# Central repository path utilities
from utils.paths import brussels_data_dir, output_root, repo_path


def get_available_dates(base_dir):
    """Scan directory to find available date subfolders."""
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    dates = []
    if os.path.exists(base_dir):
        for entry in os.listdir(base_dir):
            if os.path.isdir(os.path.join(base_dir, entry)) and date_pattern.match(entry):
                dates.append(entry)
    return sorted(dates)


def extract_positions(detections_df, data_dir):
    """
    Extract pos_x1, pos_y1 coordinates for each detection.
    Optimized day-by-day loading with PyArrow 'in' filters.
    """
    if len(detections_df) == 0:
        return pd.DataFrame()
        
    df_enriched = detections_df.copy()
    df_enriched['timestamp_dt'] = pd.to_datetime(df_enriched['timestamp'])
    df_enriched['date'] = df_enriched['timestamp_dt'].dt.date
    
    unique_dates = sorted(df_enriched['date'].dropna().unique())
    all_days_data = []
    
    for date in unique_dates:
        date_str = date.strftime('%Y-%m-%d')
        day_detections = df_enriched[df_enriched['date'] == date].copy()
        
        # Unique IDs for filter
        day_ids = list(set(day_detections['id1'].dropna().astype(int).unique()) | 
                       set(day_detections['id2'].dropna().astype(int).unique()))
                       
        if not day_ids:
            continue
            
        print(f"  Enriching {date_str}: {len(day_detections)} detections, {len(day_ids)} unique IDs...")
        
        # Get hourly folders
        hourly_folders = sorted(glob.glob(os.path.join(data_dir, f"{date_str}-*")))
        if not hourly_folders:
            print(f"  !  Warning: No hourly folders found for {date_str} in {data_dir}")
            continue
            
        # Collect parquet files with filters
        all_parquet = []
        for hour_folder in hourly_folders:
            parquet_files = sorted(glob.glob(os.path.join(hour_folder, "*.parquet")))
            for parquet_file in parquet_files:
                try:
                    df_parquet = pd.read_parquet(
                        parquet_file,
                        columns=['timestamp', 'id', 'pos_x', 'pos_y'],
                        filters=[('id', 'in', day_ids)]
                    )
                    if len(df_parquet) > 0:
                        df_parquet['timestamp'] = pd.to_datetime(df_parquet['timestamp'])
                        all_parquet.append(df_parquet)
                except Exception as e:
                    print(f"  !  Warning: Error reading {parquet_file}: {e}")
                    
        if not all_parquet:
            print(f"  !  Warning: No coordinate data found in parquet files for {date_str}")
            continue
            
        df_positions = pd.concat(all_parquet, ignore_index=True)
        
        # Match ID1
        day_detections = day_detections.merge(
            df_positions[['timestamp', 'id', 'pos_x', 'pos_y']],
            left_on=['timestamp_dt', 'id1'],
            right_on=['timestamp', 'id'],
            how='left',
            suffixes=('', '_tmp')
        )
        day_detections.rename(columns={'pos_x': 'pos_x1', 'pos_y': 'pos_y1'}, inplace=True)
        day_detections.drop(['id', 'timestamp_tmp'], axis=1, inplace=True, errors='ignore')
        
        # Match ID2
        day_detections = day_detections.merge(
            df_positions[['timestamp', 'id', 'pos_x', 'pos_y']],
            left_on=['timestamp_dt', 'id2'],
            right_on=['timestamp', 'id'],
            how='left',
            suffixes=('', '_tmp')
        )
        day_detections.rename(columns={'pos_x': 'pos_x2', 'pos_y': 'pos_y2'}, inplace=True)
        day_detections.drop(['id', 'timestamp_tmp'], axis=1, inplace=True, errors='ignore')
        
        matched = day_detections[['pos_x1', 'pos_y1', 'pos_x2', 'pos_y2']].notna().all(axis=1).sum()
        print(f"  \N{CHECK MARK}  Matched: {matched}/{len(day_detections)} ({matched/len(day_detections)*100:.1f}%)")
        
        all_days_data.append(day_detections)
        
        del df_positions
        gc.collect()
        
    if not all_days_data:
        return pd.DataFrame()
        
    df_combined = pd.concat(all_days_data, ignore_index=True)
    df_combined = df_combined.drop(['timestamp_dt', 'date'], axis=1, errors='ignore')
    return df_combined[df_combined[['pos_x1', 'pos_y1']].notna().all(axis=1)].copy()


def create_risk_heatmap(conflicts_df, gdf_zones, influence_radius=3.0, grid_resolution=0.5):
    """
    Generate normalized risk heatmap from conflict points.
    """
    conflict_points = conflicts_df[['pos_x1', 'pos_y1']].dropna()
    print(f"Generating heatmap for {len(conflict_points)} enriched conflicts...")
    
    # Grid bounds with padding
    bounds = gdf_zones.total_bounds
    x_min, y_min, x_max, y_max = bounds
    padding = 10
    x_min -= padding
    y_min -= padding
    x_max += padding
    y_max += padding
    
    x_range = np.arange(x_min, x_max, grid_resolution)
    y_range = np.arange(y_min, y_max, grid_resolution)
    X, Y = np.meshgrid(x_range, y_range)
    
    strength = np.zeros_like(X)
    
    for _, row in conflict_points.iterrows():
        x, y = row['pos_x1'], row['pos_y1']
        dist = np.sqrt((X - x)**2 + (Y - y)**2)
        influence = np.exp(-0.5 * (dist / influence_radius)**2)
        strength += influence
        
    if strength.max() > 0:
        strength_normalized = strength / strength.max()
    else:
        strength_normalized = strength
        
    return X, Y, strength_normalized, bounds


def plot_heatmap(heatmap_data, conflicts_df, gdf_zones, title, save_path):
    """
    Generate and save risk heatmap visualization.
    """
    X, Y, strength, bounds = heatmap_data
    
    fig, ax = plt.subplots(figsize=(16, 12))
    
    # Heatmap contour
    heatmap = ax.contourf(X, Y, strength, levels=20, cmap='Reds', alpha=0.7, vmin=0, vmax=1)
    
    # Lane Boundaries
    gdf_zones.boundary.plot(ax=ax, color='black', linewidth=2, alpha=0.8, label='Analysis Zone')
    
    # Conflict Scatter
    ax.scatter(
        conflicts_df['pos_x1'], conflicts_df['pos_y1'],
        c='blue', s=15, alpha=0.6, edgecolors='white', linewidths=0.5,
        label=f'Conflicts (n={len(conflicts_df)})', zorder=5
    )
    
    # Colorbar
    cbar = plt.colorbar(heatmap, ax=ax, label='Risk Strength (Normalized)', pad=0.02)
    cbar.ax.tick_params(labelsize=10)
    
    ax.set_xlabel('X Position (meters)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Y Position (meters)', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper right', fontsize=10)
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f" \N{CHECK MARK}  Saved risk heatmap to {save_path}")


def main():
    # Setup paths
    data_dir = str(brussels_data_dir())
    mdrac_base = output_root() / 'mdrac' / 'brussels'
    irsm_base = repo_path('irsm', 'results', 'brussels')
    
    # Define Brussels intersection analysis zone
    zone_wkt = (
        "POLYGON ((-28.977 34.253, -12.788 47.989, 11.576 19.046, 19.752 15.448, "
        "39.702 53.876, 48.205 49.788, 42.809 39.649, 43.136 36.215, 55.073 21.826, "
        "71.915 27.549, 76.167 19.046, 36.104 3.675, 36.104 -2.376, 46.733 -13.168, "
        "52.457 -24.287, 58.097 -31.792, 48.598 -39.498, 31.753 -19.785, 25.122 -23.907, "
        "1.466 -11.721, -28.821 -22.652, -30.792 -17.276, 0.032 -5.986, -1.402 1.003, "
        "-28.977 34.253))"
    )
    zone_geom = wkt.loads(zone_wkt)
    gdf_zones = gpd.GeoDataFrame([{'geometry': zone_geom}], geometry='geometry')
    
    print("="*60)
    print("Brussels Near-Miss Heatmap Generation Script")
    print("="*60)
    print(f"Data Directory: {data_dir}")
    print(f"M-DRAC Directory: {mdrac_base}")
    print(f"IRSM Directory: {irsm_base}")
    print("-"*60)
    
    # 1. Gather M-DRAC detections
    print("\n[1/2] PROCESSING M-DRAC DETECTIONS")
    mdrac_files = []
    # Match both lanes and crosswalks directories
    for p in glob.glob(str(mdrac_base / '**' / 'mdrac_*.csv'), recursive=True):
        basename = os.path.basename(p)
        if re.match(r'^mdrac_\d{4}-\d{2}-\d{2}\.csv$', basename):
            mdrac_files.append(p)
            
    mdrac_dfs = []
    for f in mdrac_files:
        df_temp = pd.read_csv(f)
        if len(df_temp) > 0:
            mdrac_dfs.append(df_temp)
            
    if mdrac_dfs:
        mdrac_df = pd.concat(mdrac_dfs, ignore_index=True)
        print(f"Loaded {len(mdrac_df)} total raw MDRAC conflicts.")
        
        # Enrich with coordinates
        mdrac_enriched = extract_positions(mdrac_df, data_dir)
        
        if len(mdrac_enriched) > 0:
            # Generate heatmap
            heatmap_mdrac = create_risk_heatmap(mdrac_enriched, gdf_zones)
            plot_heatmap(
                heatmap_mdrac, mdrac_enriched, gdf_zones,
                'Brussels Intersection - Near-Miss Risk Heatmap',
                str(mdrac_base / 'analysis' / 'risk_heatmap.png')
            )
        else:
            print("No matching coordinates found for M-DRAC conflicts.")
    else:
        print("No M-DRAC conflict files found.")
        
    # 2. Gather IRSM detections
    print("\n[2/2] PROCESSING IRSM DETECTIONS")
    irsm_files = glob.glob(str(irsm_base / '*' / 'gaussian_detections.csv'))
    
    irsm_dfs = []
    for f in irsm_files:
        df_temp = pd.read_csv(f)
        if len(df_temp) > 0:
            if 'pair_id' in df_temp.columns:
                df_temp['id1'] = df_temp['pair_id'].apply(lambda x: int(str(x).split('_')[0]))
                df_temp['id2'] = df_temp['pair_id'].apply(lambda x: int(str(x).split('_')[1]))
            irsm_dfs.append(df_temp)
            
    if irsm_dfs:
        irsm_df = pd.concat(irsm_dfs, ignore_index=True)
        print(f"Loaded {len(irsm_df)} total raw IRSM conflicts.")
        
        # Enrich with coordinates
        irsm_enriched = extract_positions(irsm_df, data_dir)
        
        if len(irsm_enriched) > 0:
            # Generate heatmap
            heatmap_irsm = create_risk_heatmap(irsm_enriched, gdf_zones)
            plot_heatmap(
                heatmap_irsm, irsm_enriched, gdf_zones,
                'Brussels Intersection - Near-Miss Risk Heatmap',
                str(irsm_base / 'analysis' / 'risk_heatmap.png')
            )
        else:
            print("No matching coordinates found for IRSM conflicts.")
    else:
        print("No IRSM conflict files found.")
        
    print("\nHeatmap generation complete!")
    print("="*60)


if __name__ == "__main__":
    main()
