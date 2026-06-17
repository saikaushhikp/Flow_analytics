"""
Trajectory Visualization Module for Near-Miss Analysis

Functions:
    - plot_all_pairs_from_csv: Batch generate plots for all pairs in CSV (NEW!)
    - plot_conflict_analysis: Main function to generate all plots for a single pair
    - plot_trajectories: 2D spatial plot of vehicle paths
    - plot_distance_over_time: Distance between vehicles over time
    - plot_closing_speed_over_time: Closing speed over time
    - plot_velocity_over_time: Velocity comparison over time
    - plot_yaw_diff_over_time: Yaw difference over time

Usage:
    # Batch mode (recommended):
    df = load_data('/data/clean', '2025-06-01', '2025-06-01')
    plot_all_pairs_from_csv(
        csv_path='results/brussels/mdrac/01/mdrac_01.csv',
        data_df=df
    )
    
    # Single pair mode:
    plot_conflict_analysis(df, id1=11520140, id2=11520195)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Tuple, Optional
import warnings
import os
from tqdm import tqdm
warnings.filterwarnings('ignore')


def extract_trajectories(
    df: pd.DataFrame,
    id1: int,
    id2: int,
    time_window: Optional[float] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Extract trajectory data for two vehicles."""
    traj1 = df[df['id'] == id1].sort_values('timestamp').copy()
    traj2 = df[df['id'] == id2].sort_values('timestamp').copy()
    
    if len(traj1) == 0 or len(traj2) == 0:
        raise ValueError(f"No data found for vehicle pair ({id1}, {id2})")
    
    # Check temporal overlap
    overlap_start = max(traj1['timestamp'].min(), traj2['timestamp'].min())
    overlap_end = min(traj1['timestamp'].max(), traj2['timestamp'].max())
    
    if overlap_start > overlap_end:
        raise ValueError(
            f"No temporal overlap between vehicles!\n"
            f"  Vehicle {id1}: {traj1['timestamp'].min()} to {traj1['timestamp'].max()}\n"
            f"  Vehicle {id2}: {traj2['timestamp'].min()} to {traj2['timestamp'].max()}"
        )
    
    # Extract time window if specified
    if time_window is not None:
        mid_time = (overlap_start + overlap_end) / 2
        window_start = mid_time - pd.Timedelta(seconds=time_window/2)
        window_end = mid_time + pd.Timedelta(seconds=time_window/2)
        
        traj1 = traj1[(traj1['timestamp'] >= window_start) & (traj1['timestamp'] <= window_end)]
        traj2 = traj2[(traj2['timestamp'] >= window_start) & (traj2['timestamp'] <= window_end)]
    
    print(f"  \N{CHECK MARK} Temporal overlap: {overlap_start} to {overlap_end}")
    print(f"    Duration: {(overlap_end - overlap_start).total_seconds():.2f} seconds")
    
    return traj1, traj2


def calculate_temporal_metrics(
    traj1: pd.DataFrame,
    traj2: pd.DataFrame
) -> pd.DataFrame:
    """Calculate time-varying metrics between two trajectories.
    """
    # EXACT timestamp match
    merged = pd.merge(
        traj1[['timestamp', 'pos_x', 'pos_y', 'vel_x', 'vel_y', 'vel', 'yaw']].rename(
            columns={'pos_x': 'x1', 'pos_y': 'y1', 'vel_x': 'vx1', 'vel_y': 'vy1', 'vel': 'v1', 'yaw': 'yaw1'}
        ),
        traj2[['timestamp', 'pos_x', 'pos_y', 'vel_x', 'vel_y', 'vel', 'yaw']].rename(
            columns={'pos_x': 'x2', 'pos_y': 'y2', 'vel_x': 'vx2', 'vel_y': 'vy2', 'vel': 'v2', 'yaw': 'yaw2'}
        ),
        on='timestamp',
        how='inner'
    )
    
    # Calculate distance - same as utils.py line 249-260
    dx = merged['x2'] - merged['x1']
    dy = merged['y2'] - merged['y1']
    merged['distance'] = np.sqrt(dx**2 + dy**2)
    
    # Calculate closing speed - same as utils.py line 154-160
    dvx = merged['vx2'] - merged['vx1']
    dvy = merged['vy2'] - merged['vy1']
    dot_product = dvx * dx + dvy * dy
    merged['closing_speed'] = np.where(
        merged['distance'] > 0.01,  # Changed from 0.1 to 0.01 to match utils.py line 156
        -dot_product / merged['distance'],
        0.0
    )
    
    # Calculate yaw difference - same as utils.py
    yaw_diff = np.abs(merged['yaw1'] - merged['yaw2'])
    # Take the smaller angle (handle wrapping around 2π)
    yaw_diff = np.minimum(yaw_diff, 2*np.pi - yaw_diff)
    merged['yaw_diff'] = np.degrees(yaw_diff)  # Convert to degrees
    
    return merged[['timestamp', 'distance', 'closing_speed', 'v1', 'v2', 'yaw_diff']]


def plot_trajectories(
    traj1: pd.DataFrame,
    traj2: pd.DataFrame,
    id1: int,
    id2: int,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """Plot 2D trajectories of two vehicles."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 11))
    
    # Define colors
    color1 = '#E74C3C'  # Red
    color2 = '#3498DB'  # Blue
    
    # Plot trajectories
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
    
    # Find minimum distance point - EXACT timestamp match like utils.py
    merged = pd.merge(
        traj1[['timestamp', 'pos_x', 'pos_y']].rename(columns={'pos_x': 'x1', 'pos_y': 'y1'}),
        traj2[['timestamp', 'pos_x', 'pos_y']].rename(columns={'pos_x': 'x2', 'pos_y': 'y2'}),
        on='timestamp',
        how='inner'
    )
    
    distances = np.sqrt((merged['x2'] - merged['x1'])**2 + (merged['y2'] - merged['y1'])**2)
    min_idx = distances.idxmin()
    min_distance = distances[min_idx]
    
    min_pos1_x = merged.loc[min_idx, 'x1']
    min_pos1_y = merged.loc[min_idx, 'y1']
    min_pos2_x = merged.loc[min_idx, 'x2']
    min_pos2_y = merged.loc[min_idx, 'y2']
    
    # Highlight minimum distance
    ax.scatter(min_pos1_x, min_pos1_y, 
               c='#F39C12', s=300, marker='*', edgecolor='white', linewidth=2, zorder=11)
    ax.scatter(min_pos2_x, min_pos2_y, 
               c='#F39C12', s=300, marker='*', edgecolor='white', linewidth=2, zorder=11)
    
    ax.plot([min_pos1_x, min_pos2_x], 
            [min_pos1_y, min_pos2_y], 
            color='#F39C12', linestyle='--', linewidth=2, alpha=0.7, zorder=4)
    
    # Add distance annotation
    mid_x = (min_pos1_x + min_pos2_x) / 2
    mid_y = (min_pos1_y + min_pos2_y) / 2
    ax.text(mid_x, mid_y, f'{min_distance:.2f}m', 
            fontsize=11, fontweight='bold', color='#F39C12',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#F39C12', linewidth=2),
            ha='center', va='center', zorder=11)
    
    # Set labels and styling
    ax.set_xlabel('X Position (m)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Y Position (m)', fontsize=13, fontweight='bold')
    ax.set_title(f'Vehicle Trajectories: {id1} vs {id2}', 
                 fontsize=15, fontweight='bold', pad=20)
    
    ax.legend(loc='upper right', fontsize=11, framealpha=0.95, 
              edgecolor='gray', fancybox=True, shadow=True)
    
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    ax.axis('equal')
    ax.set_facecolor('#F8F9FA')
    
    return ax


def plot_distance_over_time(
    metrics: pd.DataFrame,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """Plot distance between vehicles over time."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4))
    
    # Plot distance
    ax.plot(metrics['timestamp'], metrics['distance'], 
            color='#27AE60', linewidth=2.5, zorder=3)
    
    # Highlight minimum distance
    min_dist = metrics['distance'].min()
    min_time = metrics.loc[metrics['distance'].idxmin(), 'timestamp']
    
    ax.axhline(y=min_dist, color='#E74C3C', linestyle='--', linewidth=2, 
               alpha=0.7, zorder=2, label=f'Min Distance: {min_dist:.2f}m')
    ax.scatter(min_time, min_dist, c='#E74C3C', s=150, 
               edgecolor='white', linewidth=2, zorder=5)
    
    # Format x-axis as MM:SS
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
    # Set labels and styling
    ax.set_xlabel('Time (MM:SS)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Distance (m)', fontsize=13, fontweight='bold')
    ax.set_title('Distance Between Vehicles Over Time', 
                 fontsize=15, fontweight='bold', pad=15)
    
    ax.legend(loc='best', fontsize=11, framealpha=0.95, 
              edgecolor='gray', fancybox=True, shadow=True)
    
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    ax.set_facecolor('#F8F9FA')
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    return ax

def plot_closing_speed_over_time(
    metrics: pd.DataFrame,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """Plot closing speed over time."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4))
    
    # Plot closing speed
    ax.plot(metrics['timestamp'], metrics['closing_speed'], 
            color='#E67E22', linewidth=2.5, zorder=3)
    
    # Zero line
    ax.axhline(y=0, color='#2C3E50', linestyle='-', linewidth=2, alpha=0.8, zorder=2)
    ax.fill_between(metrics['timestamp'], 0, metrics['closing_speed'], 
                     where=(metrics['closing_speed'] > 0), 
                     color='#E74C3C', alpha=0.15, zorder=1,
                     label='Approaching')
    ax.fill_between(metrics['timestamp'], 0, metrics['closing_speed'], 
                     where=(metrics['closing_speed'] <= 0), 
                     color='#27AE60', alpha=0.15, zorder=1,
                     label='Separating')
    
    # Format x-axis as MM:SS
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
    # Set labels and styling
    ax.set_xlabel('Time (MM:SS)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Closing Speed (m/s)', fontsize=13, fontweight='bold')
    ax.set_title('Relative Closing Speed Over Time', 
                 fontsize=15, fontweight='bold', pad=15)
    
    ax.legend(loc='best', fontsize=11, framealpha=0.95, 
              edgecolor='gray', fancybox=True, shadow=True)
    
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    ax.set_facecolor('#F8F9FA')
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add annotation
    ax.text(0.02, 0.98, 'Positive = Approaching\nNegative = Separating',
            transform=ax.transAxes, fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', 
                     edgecolor='gray', alpha=0.9))
    
    return ax


def plot_velocity_over_time(
    metrics: pd.DataFrame,
    id1: int,
    id2: int,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """Plot velocity comparison of both vehicles over time."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4))
    
    # Define colors (matching trajectory colors)
    color1 = '#E74C3C'  # Red
    color2 = '#3498DB'  # Blue
    
    # Plot velocities
    ax.plot(metrics['timestamp'], metrics['v1'], 
            color=color1, linewidth=2.5, label=f'Vehicle {id1}', alpha=0.8, zorder=3)
    ax.plot(metrics['timestamp'], metrics['v2'], 
            color=color2, linewidth=2.5, label=f'Vehicle {id2}', alpha=0.8, zorder=3)
    
    # Format x-axis as MM:SS
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
    # Set labels and styling
    ax.set_xlabel('Time (MM:SS)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Velocity (m/s)', fontsize=13, fontweight='bold')
    ax.set_title('Velocity Comparison Over Time', 
                 fontsize=15, fontweight='bold', pad=15)
    
    ax.legend(loc='best', fontsize=11, framealpha=0.95, 
              edgecolor='gray', fancybox=True, shadow=True)
    
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    ax.set_facecolor('#F8F9FA')
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    return ax



def plot_yaw_diff_over_time(
    metrics: pd.DataFrame,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """Plot yaw difference (heading angle difference) between vehicles over time."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4))
    
    # Plot yaw difference
    ax.plot(metrics['timestamp'], metrics['yaw_diff'], 
            color='#9B59B6', linewidth=2.5, zorder=3, label='Yaw Difference')
    
    # Add 30-degree threshold line (longitudinal vs non-longitudinal)
    ax.axhline(y=30, color='#E74C3C', linestyle='--', linewidth=2, 
               alpha=0.7, zorder=2, label='Longitudinal Threshold (30°)')
    
    # Fill regions
    ax.fill_between(metrics['timestamp'], 0, metrics['yaw_diff'], 
                     where=(metrics['yaw_diff'] <= 30), 
                     color='#27AE60', alpha=0.15, zorder=1,
                     label='Longitudinal (≤30°)')
    ax.fill_between(metrics['timestamp'], 30, metrics['yaw_diff'], 
                     where=(metrics['yaw_diff'] > 30), 
                     color='#E67E22', alpha=0.15, zorder=1,
                     label='Non-longitudinal (>30°)')
    
    # Format x-axis as MM:SS
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
    # Set labels and styling
    ax.set_xlabel('Time (MM:SS)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Yaw Difference (degrees)', fontsize=13, fontweight='bold')
    ax.set_title('Heading Angle Difference Over Time', 
                 fontsize=15, fontweight='bold', pad=15)
    
    ax.legend(loc='best', fontsize=11, framealpha=0.95, 
              edgecolor='gray', fancybox=True, shadow=True)
    
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    ax.set_facecolor('#F8F9FA')
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Set y-axis limits
    ax.set_ylim(0, max(metrics['yaw_diff'].max() * 1.1, 35))
    
    return ax


def plot_conflict_analysis(
    df: pd.DataFrame,
    id1: int,
    id2: int,
    time_window: Optional[float] = None,
    output_dir: str = 'results/plots',
    show_plot: bool = True
) -> tuple:
    """
    Generate complete conflict analysis visualization for a vehicle pair.
    
    Creates 5 plots and saves them in a dedicated folder:
    - Trajectory plot (2D spatial)
    - Distance over time
    - Closing speed over time  
    - Velocity comparison over time
    - Yaw difference over time
    
    Args:
        df: DataFrame with all object data
        id1: ID of first vehicle
        id2: ID of second vehicle
        time_window: Optional time window (seconds) around conflict
        output_dir: Base directory for saving (default: 'results/plots')
        show_plot: Whether to display the plots
    
    Returns:
        Tuple of (fig1, fig2, fig3, fig4, fig5) - matplotlib figure objects
    """
    # Extract trajectories
    traj1, traj2 = extract_trajectories(df, id1, id2, time_window)
    
    # Calculate temporal metrics
    metrics = calculate_temporal_metrics(traj1, traj2)
    
    # Create pair-specific folder
    pair_folder = f"{id1}_{id2}"
    save_dir = os.path.join(output_dir, pair_folder)
    os.makedirs(save_dir, exist_ok=True)
    
    # Figure 1: Trajectory plot
    fig1, ax1 = plt.subplots(figsize=(11, 8))
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
    
    # Figure 4: Velocity comparison over time
    fig4, ax4 = plt.subplots(figsize=(12, 6))
    plot_velocity_over_time(metrics, id1, id2, ax=ax4)
    fig4.suptitle(f'Velocity Analysis: Vehicle {id1} vs Vehicle {id2}', 
                  fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    # Figure 5: Yaw difference over time
    fig5, ax5 = plt.subplots(figsize=(12, 6))
    plot_yaw_diff_over_time(metrics, ax=ax5)
    fig5.suptitle(f'Yaw Difference Analysis: Vehicle {id1} vs Vehicle {id2}', 
                  fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    # Save all plots
    trajectory_file = os.path.join(save_dir, "trajectory.png")
    distance_file = os.path.join(save_dir, "distance.png")
    closing_file = os.path.join(save_dir, "closing_speed.png")
    velocity_file = os.path.join(save_dir, "velocity.png")
    yaw_diff_file = os.path.join(save_dir, "yaw_diff.png")
    
    fig1.savefig(trajectory_file, dpi=500, bbox_inches='tight')
    fig2.savefig(distance_file, dpi=500, bbox_inches='tight')
    fig3.savefig(closing_file, dpi=500, bbox_inches='tight')
    fig4.savefig(velocity_file, dpi=500, bbox_inches='tight')
    fig5.savefig(yaw_diff_file, dpi=500, bbox_inches='tight')
    
    print(f"\n\N{check mark} Saved plots to {save_dir}/")
    print(f"  - trajectory.png")
    print(f"  - distance.png")
    print(f"  - closing_speed.png")
    print(f"  - velocity.png")
    print(f"  - yaw_diff.png")
    
    # Show plots
    if show_plot:
        plt.show()
    else:
        plt.close('all')
    
    return fig1, fig2, fig3, fig4, fig5


def plot_all_pairs_from_csv(
    csv_path: str,
    data_df: pd.DataFrame,
    output_base_dir: Optional[str] = None,
    time_window: Optional[float] = None,
    show_plots: bool = False
) -> None:
    """
    Generate plots for all vehicle pairs in a CSV file.
    
    Reads M-DRAC detection results CSV and creates trajectory analysis plots
    for each unique pair. Each pair gets its own subfolder.
    
    Args:
        csv_path: Path to M-DRAC results CSV (with id1, id2 columns)
        data_df: DataFrame with all trajectory data (from parquet files)
        output_base_dir: Base directory for saving plots. If None, derived from csv_path
        time_window: Optional time window (seconds) around conflict
        show_plots: Whether to display plots (default: False for batch processing)
    
    Example:
        >>> df = load_data('/data/clean', '2025-06-01', '2025-06-01')
        >>> plot_all_pairs_from_csv(
        ...     csv_path='results/mdrac/brussels/lanes/2025-06-01/mdrac_2025-06-01.csv',
        ...     data_df=df
        ... )
        # Creates: results/mdrac/brussels/lanes/2025-06-01/plots/11520140_11520195/
        #          results/mdrac/brussels/lanes/2025-06-01/plots/11531151_11531576/
        #          etc.
    """
    # Read CSV to get all pairs
    print(f"\n{'='*60}")
    print(f"Batch Plotting from CSV")
    print(f"{'='*60}")
    print(f"Reading pairs from: {csv_path}")
    
    detections_df = pd.read_csv(csv_path)
    
    # Extract unique pairs
    pairs = detections_df[['id1', 'id2']].drop_duplicates().values
    print(f"Found {len(pairs)} unique pairs to plot")
    
    # Determine output directory
    if output_base_dir is None:
        # Default: create 'plots' folder next to CSV file
        csv_dir = os.path.dirname(csv_path)
        output_base_dir = os.path.join(csv_dir, 'plots')
    
    os.makedirs(output_base_dir, exist_ok=True)
    print(f"Output directory: {output_base_dir}")
    
    # Track statistics
    successful = 0
    failed = 0
    failed_pairs = []
    
    print(f"\n{'='*60}")
    print(f"Generating plots for {len(pairs)} pairs...")
    print(f"{'='*60}\n")
    
    # Process each pair
    for id1, id2 in tqdm(pairs, desc="Processing pairs", unit="pair"):
        try:
            plot_conflict_analysis(
                df=data_df,
                id1=int(id1),
                id2=int(id2),
                time_window=time_window,
                output_dir=output_base_dir,
                show_plot=show_plots
            )
            successful += 1
        except Exception as e:
            failed += 1
            failed_pairs.append((id1, id2, str(e)))
            print(f"\n\N{heavy ballot x} Failed for pair ({id1}, {id2}): {e}\n")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Batch Plotting Summary")
    print(f"{'='*60}")
    print(f"\N{heavy check mark} Successful: {successful}/{len(pairs)}")
    
    if failed > 0:
        print(f" \N{heavy ballot x} Failed: {failed}/{len(pairs)}")
        print(f"\nFailed pairs:")
        for id1, id2, error in failed_pairs:
            print(f"  - ({id1}, {id2}): {error}")
    
    print(f"\nAll plots saved to: {output_base_dir}/")
    print(f"{'='*60}\n")


# =============================================================================
# CONFIGURATION & DATA LOADING
# =============================================================================
def load_data(data_dir: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Load data with optimized dtypes for memory efficiency."""
    dtypes = {
        'id': 'int32',
        'label': 'int8',
        'pos_x': 'float32',
        'pos_y': 'float32',
        'pos_z': 'float32',
        'vel': 'float32',
        'vel_x': 'float32',
        'vel_y': 'float32',
        'yaw': 'float32',
        'size_x': 'float32',
        'size_y': 'float32',
    }
    
    dfs = []
    
    for folder in tqdm(sorted(os.listdir(data_dir)), desc="Loading data"):
        folder_path = os.path.join(data_dir, folder)
        
        if not os.path.isdir(folder_path):
            continue
        
        if folder.startswith(start_date) or folder.startswith(end_date):
            df_chunk = pd.read_parquet(folder_path)
            
            for col, dtype in dtypes.items():
                if col in df_chunk.columns:
                    df_chunk[col] = df_chunk[col].astype(dtype)
            
            dfs.append(df_chunk)
            del df_chunk
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        del dfs
        return df
    else:
        print("No data found for given date range.")
        return pd.DataFrame()


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    """
    Batch plot generation for M-DRAC detection results.
    """
    
    # Configuration
    from utils.paths import brussels_data_dir, output_root

    DATA_DIR = str(brussels_data_dir())
    START_DATE = "2025-06-01"
    END_DATE =   "2025-06-01"
    
    # Load trajectory data
    print("Loading trajectory data...")
    df = load_data(DATA_DIR, START_DATE, END_DATE)
    print(f"Loaded {len(df)} records from {START_DATE} to {END_DATE}")
    
    CSV_PATH = str(output_root() / 'mdrac' / 'brussels' / 'lanes' / START_DATE / f'mdrac_{START_DATE}.csv')
    
    plot_all_pairs_from_csv(
        csv_path=CSV_PATH,
        data_df=df,
        show_plots=False  # Set True to display each plot (slow for many pairs)
    )
