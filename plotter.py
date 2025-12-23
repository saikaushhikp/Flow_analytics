"""
Trajectory Visualization Module for Near-Miss Analysis

This module provides visualization functions to analyze detected conflicts
by plotting vehicle trajectories and temporal metrics.

Functions:
    - plot_conflict_analysis: Main function to generate all plots for a pair
    - plot_trajectories: 2D spatial plot of vehicle paths
    - plot_distance_over_time: Distance between vehicles over time
    - plot_closing_speed_over_time: Closing speed over time
    - plot_relative_angle_over_time: Angle between velocity vectors over time
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import Tuple, Optional
import warnings
from tqdm import tqdm
warnings.filterwarnings('ignore')


def extract_trajectories(
    df: pd.DataFrame,
    id1: int,
    id2: int,
    time_window: Optional[float] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extract trajectory data for two vehicles.
    
    Args:
        df: DataFrame with all object data (must have: id, timestamp, pos_x, pos_y, vel_x, vel_y, vel)
        id1: ID of first vehicle
        id2: ID of second vehicle
        time_window: Optional time window (seconds) to extract around conflict
                    If None, extract full trajectories
    
    Returns:
        (traj1, traj2): DataFrames with trajectory data for each vehicle
        
    Raises:
        ValueError: If no data found or no temporal overlap
    """
    # Extract trajectories
    traj1 = df[df['id'] == id1].sort_values('timestamp').copy()
    traj2 = df[df['id'] == id2].sort_values('timestamp').copy()
    
    if len(traj1) == 0 or len(traj2) == 0:
        raise ValueError(f"No data found for vehicle pair ({id1}, {id2})")
    
    # Check for temporal overlap
    overlap_start = max(traj1['timestamp'].min(), traj2['timestamp'].min())
    overlap_end = min(traj1['timestamp'].max(), traj2['timestamp'].max())
    
    if overlap_start > overlap_end:
        # No overlap - provide detailed info
        raise ValueError(
            f"No temporal overlap between vehicles!\n"
            f"  Vehicle {id1}: {traj1['timestamp'].min()} to {traj1['timestamp'].max()}\n"
            f"  Vehicle {id2}: {traj2['timestamp'].min()} to {traj2['timestamp'].max()}\n"
            f"  Gap: {(overlap_start - overlap_end).total_seconds():.2f} seconds"
        )
    
    # If time window specified, find overlap and extract window
    if time_window is not None:
        # Extract window around midpoint of overlap
        mid_time = (overlap_start + overlap_end) / 2
        window_start = mid_time - pd.Timedelta(seconds=time_window/2)
        window_end = mid_time + pd.Timedelta(seconds=time_window/2)
        
        traj1 = traj1[(traj1['timestamp'] >= window_start) & (traj1['timestamp'] <= window_end)]
        traj2 = traj2[(traj2['timestamp'] >= window_start) & (traj2['timestamp'] <= window_end)]
    
    print(f"  ✓ Temporal overlap: {overlap_start} to {overlap_end}")
    print(f"    Duration: {(overlap_end - overlap_start).total_seconds():.2f} seconds")
    
    return traj1, traj2


def calculate_temporal_metrics(
    traj1: pd.DataFrame,
    traj2: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate time-varying metrics between two trajectories.
    
    Args:
        traj1: Trajectory DataFrame for vehicle 1
        traj2: Trajectory DataFrame for vehicle 2
    
    Returns:
        DataFrame with columns: timestamp, distance, closing_speed, angle
    """
    # Find common timestamps (or nearest timestamps)
    # Merge on timestamp with tolerance
    merged = pd.merge_asof(
        traj1[['timestamp', 'pos_x', 'pos_y', 'vel_x', 'vel_y', 'vel']].rename(
            columns={'pos_x': 'x1', 'pos_y': 'y1', 'vel_x': 'vx1', 'vel_y': 'vy1', 'vel': 'v1'}
        ),
        traj2[['timestamp', 'pos_x', 'pos_y', 'vel_x', 'vel_y', 'vel']].rename(
            columns={'pos_x': 'x2', 'pos_y': 'y2', 'vel_x': 'vx2', 'vel_y': 'vy2', 'vel': 'v2'}
        ),
        on='timestamp',
        direction='nearest',
        tolerance=pd.Timedelta(seconds=0.5)
    )
    
    # Calculate distance
    dx = merged['x2'] - merged['x1']
    dy = merged['y2'] - merged['y1']
    merged['distance'] = np.sqrt(dx**2 + dy**2)
    
    # Calculate closing speed
    dvx = merged['vx2'] - merged['vx1']
    dvy = merged['vy2'] - merged['vy1']
    dot_product = dvx * dx + dvy * dy
    merged['closing_speed'] = np.where(
        merged['distance'] > 0.1,
        -dot_product / merged['distance'],
        0.0
    )
    
    # Calculate angle between velocity vectors
    # angle = arccos((v1 · v2) / (|v1| * |v2|))
    dot_vel = merged['vx1'] * merged['vx2'] + merged['vy1'] * merged['vy2']
    mag_product = merged['v1'] * merged['v2']
    merged['angle'] = np.where(
        mag_product > 0.1,
        np.degrees(np.arccos(np.clip(dot_vel / mag_product, -1.0, 1.0))),
        0.0
    )
    
    # Convert timestamp to seconds from start
    merged['time_sec'] = (merged['timestamp'] - merged['timestamp'].min()).dt.total_seconds()
    
    return merged[['timestamp', 'time_sec', 'distance', 'closing_speed', 'angle']]


def plot_trajectories(
    traj1: pd.DataFrame,
    traj2: pd.DataFrame,
    id1: int,
    id2: int,
    ax: Optional[plt.Axes] = None,
    show_vectors: bool = False,
    vector_scale: float = 0.5
) -> plt.Axes:
    """
    Plot 2D trajectories of two vehicles.
    
    Args:
        traj1: Trajectory DataFrame for vehicle 1
        traj2: Trajectory DataFrame for vehicle 2
        id1: ID of vehicle 1
        id2: ID of vehicle 2
        ax: Matplotlib axes (if None, create new)
        show_vectors: Whether to show velocity vectors
        vector_scale: Scale factor for velocity vectors
    
    Returns:
        Matplotlib axes object
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 10))
    
    # Define professional colors
    color1 = '#E74C3C'  # Professional red
    color2 = '#3498DB'  # Professional blue
    
    # Plot trajectories with smooth lines
    ax.plot(traj1['pos_x'], traj1['pos_y'], 
            color=color1, linewidth=3, label=f'Vehicle {id1}', alpha=0.8, zorder=3)
    ax.plot(traj2['pos_x'], traj2['pos_y'], 
            color=color2, linewidth=3, label=f'Vehicle {id2}', alpha=0.8, zorder=3)
    
    # Mark start points (circles)
    ax.scatter(traj1['pos_x'].iloc[0], traj1['pos_y'].iloc[0], 
               c=color1, s=150, marker='o', edgecolor='white', linewidth=2.5, zorder=5)
    ax.scatter(traj2['pos_x'].iloc[0], traj2['pos_y'].iloc[0], 
               c=color2, s=150, marker='o', edgecolor='white', linewidth=2.5, zorder=5)
    
    # Mark end points (squares)
    ax.scatter(traj1['pos_x'].iloc[-1], traj1['pos_y'].iloc[-1], 
               c=color1, s=150, marker='s', edgecolor='white', linewidth=2.5, zorder=5)
    ax.scatter(traj2['pos_x'].iloc[-1], traj2['pos_y'].iloc[-1], 
               c=color2, s=150, marker='s', edgecolor='white', linewidth=2.5, zorder=5)
    
    # Find minimum distance point (FIXED: properly align trajectories by timestamp)
    # Merge trajectories on timestamp to get synchronized positions
    merged = pd.merge_asof(
        traj1[['timestamp', 'pos_x', 'pos_y']].rename(columns={'pos_x': 'x1', 'pos_y': 'y1'}),
        traj2[['timestamp', 'pos_x', 'pos_y']].rename(columns={'pos_x': 'x2', 'pos_y': 'y2'}),
        on='timestamp',
        direction='nearest',
        tolerance=pd.Timedelta(seconds=0.5)
    )
    
    # Calculate distances at synchronized timestamps
    distances = np.sqrt((merged['x2'] - merged['x1'])**2 + (merged['y2'] - merged['y1'])**2)
    min_idx = distances.idxmin()
    min_distance = distances[min_idx]
    
    # Get positions at minimum distance
    min_pos1_x = merged.loc[min_idx, 'x1']
    min_pos1_y = merged.loc[min_idx, 'y1']
    min_pos2_x = merged.loc[min_idx, 'x2']
    min_pos2_y = merged.loc[min_idx, 'y2']
    
    # Highlight minimum distance point with star
    ax.scatter(min_pos1_x, min_pos1_y, 
               c='#F39C12', s=300, marker='*', edgecolor='white', linewidth=2, zorder=10)
    ax.scatter(min_pos2_x, min_pos2_y, 
               c='#F39C12', s=300, marker='*', edgecolor='white', linewidth=2, zorder=10)
    
    # Draw line between vehicles at min distance
    ax.plot([min_pos1_x, min_pos2_x], 
            [min_pos1_y, min_pos2_y], 
            color='#F39C12', linestyle='--', linewidth=2, alpha=0.7, zorder=4)
    
    # Add minimum distance annotation
    mid_x = (min_pos1_x + min_pos2_x) / 2
    mid_y = (min_pos1_y + min_pos2_y) / 2
    ax.text(mid_x, mid_y, f'{min_distance:.2f}m', 
            fontsize=11, fontweight='bold', color='#F39C12',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#F39C12', linewidth=2),
            ha='center', va='center', zorder=11)
    
    # Set labels and title with better formatting
    ax.set_xlabel('X Position (m)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Y Position (m)', fontsize=13, fontweight='bold')
    ax.set_title(f'Vehicle Trajectories: {id1} vs {id2}', 
                 fontsize=15, fontweight='bold', pad=20)
    
    # Professional legend
    ax.legend(loc='upper right', fontsize=11, framealpha=0.95, 
              edgecolor='gray', fancybox=True, shadow=True)
    
    # Clean grid
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    
    # Equal aspect ratio
    ax.axis('equal')
    
    # Set background color
    ax.set_facecolor('#F8F9FA')
    
    return ax


def plot_distance_over_time(
    metrics: pd.DataFrame,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """
    Plot distance between vehicles over time.
    
    Args:
        metrics: DataFrame with 'time_sec' and 'distance' columns
        ax: Matplotlib axes (if None, create new)
    
    Returns:
        Matplotlib axes object
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 4))
    
    # Plot distance with professional styling
    ax.plot(metrics['time_sec'], metrics['distance'], 
            color='#27AE60', linewidth=2.5, zorder=3)
    
    # Highlight minimum distance
    min_dist = metrics['distance'].min()
    min_time = metrics.loc[metrics['distance'].idxmin(), 'time_sec']
    
    ax.axhline(y=min_dist, color='#E74C3C', linestyle='--', linewidth=2, 
               alpha=0.7, zorder=2, label=f'Min Distance: {min_dist:.2f}m')
    ax.scatter(min_time, min_dist, c='#E74C3C', s=150, 
               edgecolor='white', linewidth=2, zorder=5)
    
    # Set labels and title
    ax.set_xlabel('Time (seconds)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Distance (m)', fontsize=13, fontweight='bold')
    ax.set_title('Distance Between Vehicles Over Time', 
                 fontsize=15, fontweight='bold', pad=15)
    
    # Professional legend
    ax.legend(loc='best', fontsize=11, framealpha=0.95, 
              edgecolor='gray', fancybox=True, shadow=True)
    
    # Clean grid
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    
    # Background color
    ax.set_facecolor('#F8F9FA')
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    return ax


def plot_closing_speed_over_time(
    metrics: pd.DataFrame,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """
    Plot closing speed over time.
    
    Args:
        metrics: DataFrame with 'time_sec' and 'closing_speed' columns
        ax: Matplotlib axes (if None, create new)
    
    Returns:
        Matplotlib axes object
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 4))
    
    # Plot closing speed with professional styling
    ax.plot(metrics['time_sec'], metrics['closing_speed'], 
            color='#E67E22', linewidth=2.5, zorder=3)
    
    # Highlight approaching region (positive closing speed)
    ax.axhline(y=0, color='#2C3E50', linestyle='-', linewidth=2, alpha=0.8, zorder=2)
    ax.fill_between(metrics['time_sec'], 0, metrics['closing_speed'], 
                     where=(metrics['closing_speed'] > 0), 
                     color='#E74C3C', alpha=0.15, zorder=1,
                     label='Approaching')
    ax.fill_between(metrics['time_sec'], 0, metrics['closing_speed'], 
                     where=(metrics['closing_speed'] <= 0), 
                     color='#27AE60', alpha=0.15, zorder=1,
                     label='Separating')
    
    # Set labels and title
    ax.set_xlabel('Time (seconds)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Closing Speed (m/s)', fontsize=13, fontweight='bold')
    ax.set_title('Relative Closing Speed Over Time', 
                 fontsize=15, fontweight='bold', pad=15)
    
    # Professional legend
    ax.legend(loc='best', fontsize=11, framealpha=0.95, 
              edgecolor='gray', fancybox=True, shadow=True)
    
    # Clean grid
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    
    # Background color
    ax.set_facecolor('#F8F9FA')
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add annotation for interpretation
    ax.text(0.02, 0.98, 'Positive = Approaching\nNegative = Separating',
            transform=ax.transAxes, fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', 
                     edgecolor='gray', alpha=0.9))
    
    return ax




def plot_conflict_analysis(
    df: pd.DataFrame,
    id1: int,
    id2: int,
    time_window: Optional[float] = None,
    save_path: Optional[str] = None,
    show_plot: bool = True
) -> tuple:
    """
    Generate complete conflict analysis visualization for a vehicle pair.
    
    Creates 3 separate plots:
    - Plot 1: Trajectory plot (2D spatial)
    - Plot 2: Distance over time
    - Plot 3: Closing speed over time
    
    Args:
        df: DataFrame with all object data
        id1: ID of first vehicle
        id2: ID of second vehicle
        time_window: Optional time window (seconds) around conflict to plot
                    If None, plot full trajectories
        save_path: Optional base path to save figures (e.g., 'results/conflict_123_456')
                   Will create: {save_path}_trajectory.png, {save_path}_distance.png, etc.
        show_plot: Whether to display the plots
    
    Returns:
        Tuple of (fig1, fig2, fig3) - three matplotlib figure objects
    """
    # Extract trajectories
    traj1, traj2 = extract_trajectories(df, id1, id2, time_window)
    
    # Calculate temporal metrics
    metrics = calculate_temporal_metrics(traj1, traj2)
    
    # Create separate figures
    
    # Figure 1: Trajectory plot (2D spatial)
    fig1, ax1 = plt.subplots(figsize=(10, 8))
    plot_trajectories(traj1, traj2, id1, id2, ax=ax1)
    fig1.suptitle(f'Trajectory Analysis: Vehicle {id1} vs Vehicle {id2}', 
                  fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    # Figure 2: Distance over time
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    plot_distance_over_time(metrics, ax=ax2)
    fig2.suptitle(f'Distance Analysis: Vehicle {id1} vs Vehicle {id2}', 
                  fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    # Figure 3: Closing speed over time
    fig3, ax3 = plt.subplots(figsize=(12, 6))
    plot_closing_speed_over_time(metrics, ax=ax3)
    fig3.suptitle(f'Closing Speed Analysis: Vehicle {id1} vs Vehicle {id2}', 
                  fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        # Extract directory and create proper filenames
        import os
        save_dir = os.path.dirname(save_path) if os.path.dirname(save_path) else '.'
        
        # Create clean filenames: veh123_vs_veh456_trajectory.png
        base_name = f"veh{id1}_vs_veh{id2}"
        
        trajectory_file = os.path.join(save_dir, f"{base_name}_trajectory.png")
        distance_file = os.path.join(save_dir, f"{base_name}_distance.png")
        closing_file = os.path.join(save_dir, f"{base_name}_closing_speed.png")
        
        fig1.savefig(trajectory_file, dpi=150, bbox_inches='tight')
        fig2.savefig(distance_file, dpi=150, bbox_inches='tight')
        fig3.savefig(closing_file, dpi=150, bbox_inches='tight')
        
        print(f"✓ Saved plots to:")
        print(f"  - {trajectory_file}")
        print(f"  - {distance_file}")
        print(f"  - {closing_file}")
    
    # Show plots
    if show_plot:
        plt.show()
    else:
        plt.close('all')
    
    return fig1, fig2, fig3


# =============================================================================
# Run to visualize a specific conflict pair
# =============================================================================

if __name__ == "__main__":
    """
    Visualize a specific conflict pair.
    
    Usage:
        python trajectory_viz.py
    """
    import os
    
    # =========================================================================
    # CONFIGURE THESE VALUES
    # =========================================================================
    DATA_DIR = '/home/ubuntu/data/uploads/objects/clean'  # Path to your preprocessed data
    START_DATE = "2025-06-01"
    END_DATE = "2025-06-01"
    CHUNK_SIZE = 500000
    # 10292540_10292655 - Apporach at a intersection, not a real near miss
    # 10447042_10446808
    ID1 = 10447042  # First vehicle ID
    ID2 = 10446808  # Second vehicle ID
    # =========================================================================
    def load_data(data_dir, start_date, end_date):
        """
        Load data with optimized dtypes for memory efficiency
        """
        # Define optimal dtypes upfront - saves ~50% memory
        dtypes = {
            'id': 'int32',           # Was int64 → Save 50%
            'label': 'int8',         # Values 1-8 → Save 87.5%
            'pos_x': 'float32',      # Was float64 → Save 50%
            'pos_y': 'float32',
            'pos_z': 'float32',
            'vel': 'float32',
            'vel_x': 'float32',
            'vel_y': 'float32',
            'yaw': 'float32',
            'size_x': 'float32',
            'size_y': 'float32',
            # timestamp stays int64 (needed for precision)
        }
        
        # List to collect dataframes
        dfs = []
        
        # Loop over all folders within date range
        for folder in tqdm(sorted(os.listdir(data_dir)), desc="Loading data"):
            folder_path = os.path.join(data_dir, folder)
            
            # Skip non-folders
            if not os.path.isdir(folder_path):
                continue
            
            if folder.startswith(start_date) or folder.startswith(end_date):
                # Load all parquet files inside the folder
                df_chunk = pd.read_parquet(folder_path)
                
                # Apply dtypes to matching columns
                for col, dtype in dtypes.items():
                    if col in df_chunk.columns:
                        df_chunk[col] = df_chunk[col].astype(dtype)
                
                dfs.append(df_chunk)
                del df_chunk  # Clean up immediately
        
        # Combine all into single dataframe
        if dfs:
            df = pd.concat(dfs, ignore_index=True)
            
            # Destroy the list immediately
            del dfs
            return df
        else:
            print("No data found for given date range.")
            return pd.DataFrame()

    # Usage
    df = load_data(DATA_DIR, START_DATE, END_DATE)
    print(f"Loaded {len(df)} records from {START_DATE} to {END_DATE}")    
    # Create output directory
    os.makedirs('results/viz', exist_ok=True)
    
    # Generate visualization
    print(f"\nGenerating visualization for vehicles {ID1} and {ID2}...")
    
    try:
        plot_conflict_analysis(
            df, 
            id1=ID1, 
            id2=ID2,
            save_path='results/viz',  # Just directory, function creates proper names
            show_plot=True
        )
        print(f"✓ Done!")
    except Exception as e:
        print(f"✗ Error: {e}")