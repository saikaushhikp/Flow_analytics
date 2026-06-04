"""
IRSM Plotter - Trajectory Visualization for IRSM Detection Results

Adapted for IRSM's lanes.csv schema which uses pair_id instead of separate id1/id2.

Usage:
    # Load data
    df = load_data('/data/clean', '2025-06-01', '2025-06-01')
    
    # Batch mode (recommended):
    plot_all_pairs_from_csv(
        csv_path='irsm/data/brussels/2025-06-01/lanes.csv',
        data_df=df,
        output_dir='irsm/results/brussels/2025-06-01/plots'
    )
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Tuple, Optional
import warnings
import os
from tqdm import tqdm
warnings.filterwarnings('ignore')


def parse_pair_id(pair_id: str) -> Tuple[int, int]:
    """Parse pair_id string (e.g., '10296306_10296324') into (id1, id2)"""
    parts = pair_id.split('_')
    return int(parts[0]), int(parts[1])


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
            f"No temporal overlap between vehicles!\\n"
            f"  Vehicle {id1}: {traj1['timestamp'].min()} to {traj1['timestamp'].max()}\\n"
            f"  Vehicle {id2}: {traj2['timestamp'].min()} to {traj2['timestamp'].max()}"
        )
    
    # Extract time window if specified
    if time_window is not None:
        mid_time = (overlap_start + overlap_end) / 2
        window_start = mid_time - pd.Timedelta(seconds=time_window/2)
        window_end = mid_time + pd.Timedelta(seconds=time_window/2)
        
        traj1 = traj1[(traj1['timestamp'] >= window_start) & (traj1['timestamp'] <= window_end)]
        traj2 = traj2[(traj2['timestamp'] >= window_start) & (traj2['timestamp'] <= window_end)]
    
    return traj1, traj2


def calculate_temporal_metrics(
    traj1: pd.DataFrame,
    traj2: pd.DataFrame
) -> pd.DataFrame:
    """Calculate time-varying metrics between two trajectories."""
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
    
    # Calculate distance
    dx = merged['x2'] - merged['x1']
    dy = merged['y2'] - merged['y1']
    merged['distance'] = np.sqrt(dx**2 + dy**2)
    
    # Calculate closing speed
    dvx = merged['vx2'] - merged['vx1']
    dvy = merged['vy2'] - merged['vy1']
    dot_product = dvx * dx + dvy * dy
    merged['closing_speed'] = np.where(
        merged['distance'] > 0.01,
        -dot_product / merged['distance'],
        0.0
    )
    
    # Calculate yaw difference
    yaw_diff = np.abs(merged['yaw1'] - merged['yaw2'])
    yaw_diff = np.minimum(yaw_diff, 2*np.pi - yaw_diff)
    merged['yaw_diff'] = np.degrees(yaw_diff)
    
    return merged[['timestamp', 'distance', 'closing_speed', 'v1', 'v2', 'yaw_diff']]


def plot_trajectories(
    traj1: pd.DataFrame,
    traj2: pd.DataFrame,
    id1: int,
    id2: int,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """Plot 2D trajectories of two objects."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 11))
    
    color1 = '#E74C3C'  # Red
    color2 = '#3498DB'  # Blue
    
    # Plot trajectories
    ax.plot(traj1['pos_x'], traj1['pos_y'], 
            color=color1, linewidth=3, label=f'Object {id1}', alpha=0.8, zorder=3)
    ax.plot(traj2['pos_x'], traj2['pos_y'], 
            color=color2, linewidth=3, label=f'Object {id2}', alpha=0.8, zorder=3)
    
    # Mark start points
    ax.scatter(traj1['pos_x'].iloc[0], traj1['pos_y'].iloc[0], 
               c=color1, s=150, marker='o', edgecolor='white', linewidth=2.5, zorder=5)
    ax.scatter(traj2['pos_x'].iloc[0], traj2['pos_y'].iloc[0], 
               c=color2, s=150, marker='o', edgecolor='white', linewidth=2.5, zorder=5)
    
    # Mark end points
    ax.scatter(traj1['pos_x'].iloc[-1], traj1['pos_y'].iloc[-1], 
               c=color1, s=150, marker='s', edgecolor='white', linewidth=2.5, zorder=5)
    ax.scatter(traj2['pos_x'].iloc[-1], traj2['pos_y'].iloc[-1], 
               c=color2, s=150, marker='s', edgecolor='white', linewidth=2.5, zorder=5)
    
    # Find minimum distance point
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
    ax.set_title(f'Interaction Trajectories: {id1} vs {id2}', 
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
    """Plot distance between objects over time."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4))
    
    ax.plot(metrics['timestamp'], metrics['distance'], 
            color='#27AE60', linewidth=2.5, zorder=3)
    
    min_dist = metrics['distance'].min()
    min_time = metrics.loc[metrics['distance'].idxmin(), 'timestamp']
    
    ax.axhline(y=min_dist, color='#E74C3C', linestyle='--', linewidth=2, 
               alpha=0.7, zorder=2, label=f'Min Distance: {min_dist:.2f}m')
    ax.scatter(min_time, min_dist, c='#E74C3C', s=150, 
               edgecolor='white', linewidth=2, zorder=5)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
    ax.set_xlabel('Time (MM:SS)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Distance (m)', fontsize=13, fontweight='bold')
    ax.set_title('Distance Over Time', fontsize=15, fontweight='bold', pad=15)
    
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
    
    ax.plot(metrics['timestamp'], metrics['closing_speed'], 
            color='#E67E22', linewidth=2.5, zorder=3)
    
    ax.axhline(y=0, color='#2C3E50', linestyle='-', linewidth=2, alpha=0.8, zorder=2)
    ax.fill_between(metrics['timestamp'], 0, metrics['closing_speed'], 
                     where=(metrics['closing_speed'] > 0), 
                     color='#E74C3C', alpha=0.15, zorder=1,
                     label='Approaching')
    ax.fill_between(metrics['timestamp'], 0, metrics['closing_speed'], 
                     where=(metrics['closing_speed'] <= 0), 
                     color='#27AE60', alpha=0.15, zorder=1,
                     label='Separating')
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
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
    
    return ax


def plot_velocity_over_time(
    metrics: pd.DataFrame,
    id1: int,
    id2: int,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """Plot velocity comparison of both objects over time."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4))
    
    color1 = '#E74C3C'  # Red
    color2 = '#3498DB'  # Blue
    
    ax.plot(metrics['timestamp'], metrics['v1'], 
            color=color1, linewidth=2.5, label=f'Object {id1}', alpha=0.8, zorder=3)
    ax.plot(metrics['timestamp'], metrics['v2'], 
            color=color2, linewidth=2.5, label=f'Object {id2}', alpha=0.8, zorder=3)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
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
    """Plot yaw difference (heading angle difference) over time."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4))
    
    ax.plot(metrics['timestamp'], metrics['yaw_diff'], 
            color='#9B59B6', linewidth=2.5, zorder=3, label='Yaw Difference')
    
    # Add 30-degree threshold line
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
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
    
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
    
    ax.set_ylim(0, max(metrics['yaw_diff'].max() * 1.1, 35))
    
    return ax


def plot_pair_analysis(
    df: pd.DataFrame,
    pair_id: str,
    output_dir: str,
    show_plot: bool = False
) -> None:
    """Generate complete trajectory analysis plots for a pair."""
    # Parse pair_id
    id1, id2 = parse_pair_id(pair_id)
    
    # Extract trajectories
    traj1, traj2 = extract_trajectories(df, id1, id2)
    
    # Calculate metrics
    metrics = calculate_temporal_metrics(traj1, traj2)
    
    # Create pair folder
    pair_folder = pair_id
    save_dir = os.path.join(output_dir, pair_folder)
    os.makedirs(save_dir, exist_ok=True)
    
    # Figure 1: Trajectory plot
    fig1, ax1 = plt.subplots(figsize=(11, 8))
    plot_trajectories(traj1, traj2, id1, id2, ax=ax1)
    plt.tight_layout()
    fig1.savefig(os.path.join(save_dir, "trajectory.png"), dpi=150, bbox_inches='tight')
    
    # Figure 2: Distance over time
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    plot_distance_over_time(metrics, ax=ax2)
    plt.tight_layout()
    fig2.savefig(os.path.join(save_dir, "distance.png"), dpi=150, bbox_inches='tight')
    
    # Figure 3: Closing speed over time
    fig3, ax3 = plt.subplots(figsize=(12, 6))
    plot_closing_speed_over_time(metrics, ax=ax3)
    plt.tight_layout()
    fig3.savefig(os.path.join(save_dir, "closing_speed.png"), dpi=150, bbox_inches='tight')
    
    # Figure 4: Velocity comparison over time
    fig4, ax4 = plt.subplots(figsize=(12, 6))
    plot_velocity_over_time(metrics, id1, id2, ax=ax4)
    plt.tight_layout()
    fig4.savefig(os.path.join(save_dir, "velocity.png"), dpi=150, bbox_inches='tight')
    
    # Figure 5: Yaw difference over time
    fig5, ax5 = plt.subplots(figsize=(12, 6))
    plot_yaw_diff_over_time(metrics, ax=ax5)
    plt.tight_layout()
    fig5.savefig(os.path.join(save_dir, "yaw_diff.png"), dpi=150, bbox_inches='tight')
    
    if show_plot:
        plt.show()
    else:
        plt.close('all')


def load_data_for_pairs(data_dir: str, date: str, pair_ids: list) -> pd.DataFrame:
    """
    Efficiently load only the data needed for specific pairs.
    
    Args:
        data_dir: Base data directory
        date: Date folder (e.g., '2025-06-01')
        pair_ids: List of pair_id strings to load data for
    
    Returns:
        DataFrame with only the IDs needed for these pairs
    """
    import glob
    
    # Extract all unique IDs from pair_ids
    all_ids = set()
    for pair_id in pair_ids:
        id1, id2 = parse_pair_id(pair_id)
        all_ids.add(id1)
        all_ids.add(id2)
    
    print(f"  Loading data for {len(all_ids)} unique object IDs...")
    
    # Find all hourly parquet files for the date
    pattern = f'{data_dir}/{date}*/**.parquet'
    parquet_files = glob.glob(pattern)
    
    if not parquet_files:
        # Try direct folder
        pattern = f'{data_dir}/{date}/'
        if os.path.exists(pattern):
            df = pd.read_parquet(pattern)
        else:
            raise FileNotFoundError(f"No data found for date {date} in {data_dir}")
    else:
        # Load all hourly files and concatenate
        dfs = []
        for file in parquet_files:
            df_chunk = pd.read_parquet(file)
            # Filter early to save memory
            df_chunk = df_chunk[df_chunk['id'].isin(all_ids)]
            if len(df_chunk) > 0:
                dfs.append(df_chunk)
        
        if not dfs:
            raise ValueError(f"No data found for any of the {len(all_ids)} IDs")
        
        df = pd.concat(dfs, ignore_index=True)
    
    # Final filter
    df = df[df['id'].isin(all_ids)].copy()
    
    print(f"  ✓ Loaded {len(df):,} records for these objects")
    return df


def plot_all_pairs_from_csv(
    csv_path: str,
    data_df: Optional[pd.DataFrame] = None,
    data_dir: Optional[str] = None,
    date: Optional[str] = None,
    output_dir: Optional[str] = None,
    show_plots: bool = False
) -> None:
    """
    Generate plots for all pairs in IRSM lanes.csv file.
    
    Args:
        csv_path: Path to IRSM lanes.csv (with pair_id column)
        data_df: DataFrame with trajectory data (optional if data_dir and date provided)
        data_dir: Base data directory (optional, for efficient loading)
        date: Date folder (optional, for efficient loading)
        output_dir: Output directory for plots. If None, creates 'plots' next to CSV
        show_plots: Whether to display plots
    
    Example (efficient mode):
        >>> plot_all_pairs_from_csv(
        ...     csv_path='irsm/results/brussels/2025-06-01/lanes_detections.csv',
        ...     data_dir='/home/ubuntu/data/uploads/objects/clean',
        ...     date='2025-06-01'
        ... )
    
    Example (pre-loaded data):
        >>> df = pd.read_parquet('/data/clean/2025-06-01/')
        >>> plot_all_pairs_from_csv(csv_path='irsm/data/brussels/2025-06-01/lanes.csv', data_df=df)
    """
    print(f"\n{'='*60}")
    print(f"IRSM Batch Plotting")
    print(f"{'='*60}")
    print(f"Reading pairs from: {csv_path}")
    
    # Read CSV
    detections_df = pd.read_csv(csv_path)
    
    # Extract unique pair_ids
    pair_ids = detections_df['pair_id'].unique()
    print(f"Found {len(pair_ids)} unique pairs to plot")
    
    # Load data efficiently if not provided
    if data_df is None:
        if data_dir is None or date is None:
            raise ValueError("Must provide either data_df OR (data_dir and date)")
        data_df = load_data_for_pairs(data_dir, date, pair_ids)
    
    # Determine output directory
    if output_dir is None:
        csv_dir = os.path.dirname(csv_path)
        output_dir = os.path.join(csv_dir, 'plots')
    
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")
    
    # Track statistics
    successful = 0
    failed = 0
    failed_pairs = []
    
    print(f"\n{'='*60}")
    print(f"Generating plots for {len(pair_ids)} pairs...")
    print(f"{'='*60}\n")
    
    # Process each pair
    for pair_id in tqdm(pair_ids, desc="Processing pairs", unit="pair"):
        try:
            plot_pair_analysis(
                df=data_df,
                pair_id=pair_id,
                output_dir=output_dir,
                show_plot=show_plots
            )
            successful += 1
        except Exception as e:
            failed += 1
            failed_pairs.append((pair_id, str(e)))
            print(f"\n✗ Failed for pair {pair_id}: {e}\n")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Batch Plotting Summary")
    print(f"{'='*60}")
    print(f"✓ Successful: {successful}/{len(pair_ids)}")
    
    if failed > 0:
        print(f"✗ Failed: {failed}/{len(pair_ids)}")
        print(f"\nFailed pairs:")
        for pair_id, error in failed_pairs:
            print(f"  - {pair_id}: {error}")
    
    print(f"\nAll plots saved to: {output_dir}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    """
    Generate plots for IRSM detections (anomalies only).
    """
    import yaml
    from utils.paths import brussels_data_dir
    
    # Load config
    with (REPO_ROOT / 'irsm' / 'irsm_config.yaml').open('r') as f:
        config = yaml.safe_load(f)
    
    region = config['region']
    date = config['date']
    output_base = Path(config['data']['output_base'])
    if not output_base.is_absolute():
        output_base = REPO_ROOT / output_base
    
    # Paths - using DETECTIONS (anomalies)
    csv_path = output_base / 'results' / region / date / 'lanes_detections.csv'
    data_dir = str(brussels_data_dir())
    output_dir = output_base / 'results' / region / date / 'plots'
    
    # Generate plots (efficient mode - only loads needed IDs)
    plot_all_pairs_from_csv(
        csv_path=csv_path,
        data_dir=data_dir,
        date=date,
        output_dir=output_dir,
        show_plots=False
    )
