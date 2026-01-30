"""
Zone Visualization Tool - Proper map-like view

Plots all zones with correct aspect ratio and proportions.

Usage:
    python plot_zones.py --region oulu
    python plot_zones.py --region brussels
"""

import sys
sys.path.insert(0, '/home/ubuntu/prem')

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from shapely import wkt
import argparse
from pathlib import Path
import numpy as np


def load_zones_by_category(region):
    """Load zones grouped by category"""
    if region == 'oulu':
        from regions.oulu.zones import get_crosswalk_zone, get_footpath_zones, get_lane_zones, get_near_miss_zones
        
        categories = {
            'Crosswalk': [get_crosswalk_zone()],
            'Footpaths': get_footpath_zones(),
            'Lanes': get_lane_zones(),
            'Near-Miss Zones': get_near_miss_zones()
        }
    elif region == 'brussels':
        from regions.brussels.zones import get_lane_zones, get_footpath_zones, get_crosswalk_zones
        
        categories = {
            'Lanes': get_lane_zones(),
            'Footpaths': get_footpath_zones(),
            'Crosswalks': get_crosswalk_zones()
        }
    else:
        raise ValueError(f"Unknown region: {region}")
    
    return categories


def plot_all_zones(region='oulu'):
    """Plot all zones with proper aspect ratio"""
    print(f"\nPlotting zones for {region.upper()}...")
    
    categories = load_zones_by_category(region)
    
    color_map = {
        'Lanes': '#3498DB',
        'Crosswalk': '#E74C3C',
        'Crosswalks': '#E74C3C',
        'Footpaths': '#95A5A6',
        'Near-Miss Zones': '#F39C12',
    }
    
    # Calculate bounds first to set proper figure size
    all_polys = []
    for zones_list in categories.values():
        for zone in zones_list:
            poly = wkt.loads(zone['vertices'])
            all_polys.append(poly)
    
    if not all_polys:
        print("No zones found!")
        return
    
    # Get overall bounds
    all_bounds = [p.bounds for p in all_polys]
    minx = min(b[0] for b in all_bounds)
    miny = min(b[1] for b in all_bounds)
    maxx = max(b[2] for b in all_bounds)
    maxy = max(b[3] for b in all_bounds)
    
    # Calculate dimensions
    width = maxx - minx
    height = maxy - miny
    aspect_ratio = width / height
    
    # Set figure size based on aspect ratio (max 16 inches on long side)
    if aspect_ratio > 1:
        figsize = (16, 16 / aspect_ratio)
    else:
        figsize = (16 * aspect_ratio, 16)
    
    print(f"  Zone dimensions: {width:.1f}m x {height:.1f}m")
    print(f"  Aspect ratio: {aspect_ratio:.2f}")
    print(f"  Figure size: {figsize[0]:.1f} x {figsize[1]:.1f} inches")
    
    fig, ax = plt.subplots(figsize=figsize)
    
    legend_handles = []
    
    # Plot each category
    for category_name, zones_list in categories.items():
        if not zones_list:
            continue
        
        color = color_map.get(category_name, '#BDC3C7')
        
        # Add to legend
        legend_patch = patches.Patch(color=color, label=f"{category_name} ({len(zones_list)})", alpha=0.5)
        legend_handles.append(legend_patch)
        
        # Plot zones
        for zone in zones_list:
            poly = wkt.loads(zone['vertices'])
            x, y = poly.exterior.xy
            
            patch = patches.Polygon(
                list(zip(x, y)),
                facecolor=color,
                edgecolor='black',
                alpha=0.5,
                linewidth=2
            )
            ax.add_patch(patch)
            
            # Label
            centroid = poly.centroid
            zone_label = zone.get('name', zone.get('id', ''))
            ax.text(centroid.x, centroid.y, zone_label,
                    fontsize=10, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='white', 
                             edgecolor='black', alpha=0.9, linewidth=1))
    
    # Set exact bounds with small padding
    padding = max(width, height) * 0.05
    ax.set_xlim(minx - padding, maxx + padding)
    ax.set_ylim(miny - padding, maxy + padding)
    
    # Force equal aspect ratio
    ax.set_aspect('equal', adjustable='box')
    
    # Title and labels
    ax.set_title(f'{region.upper()} - Zone Layout', 
                 fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('X Position (m)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Y Position (m)', fontsize=13, fontweight='bold')
    
    # Legend
    ax.legend(handles=legend_handles, loc='upper right', fontsize=11, 
              framealpha=0.95, edgecolor='gray', fancybox=True, shadow=True)
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    ax.set_facecolor('#F8F9FA')
    
    plt.tight_layout()
    
    # Save with reasonable DPI
    output_dir = Path(f'regions/{region}/zone_plots')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'all_zones.png'
    
    plt.savefig(output_path, dpi=120, bbox_inches='tight')
    plt.close('all')
    
    print(f"✓ Saved to: {output_path}")
    
    # Summary
    total_zones = sum(len(zones) for zones in categories.values())
    print(f"\nZone Summary:")
    for category_name, zones_list in categories.items():
        print(f"  {category_name}: {len(zones_list)} zones")
    print(f"  Total: {total_zones} zones")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Plot all zones with proper aspect ratio')
    parser.add_argument('--region', type=str, default='oulu',
                       choices=['oulu', 'brussels'],
                       help='Region to plot (default: oulu)')
    
    args = parser.parse_args()
    plot_all_zones(region=args.region)
