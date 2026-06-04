"""
IRSM Risk Space Visualization

Visualizes the 3D risk vector space (MDRAC, TTC, Closing Speed) to validate
the assumption that near-misses are separable from normal interactions.

Usage:
    python irsm/visualize_risk.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import yaml


def load_irsm_config(config_path='irsm/irsm_config.yaml'):
    """Load IRSM configuration"""
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = REPO_ROOT / config_file
    with config_file.open('r') as f:
        return yaml.safe_load(f)


def resolve_repo_path(path_value):
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def visualize_risk_space(data_path, detections_path, output_dir, config):
    """
    Create 3D visualization of risk vector space.
    
    Args:
        data_path: Path to lanes.csv (all pairs)
        detections_path: Path to lanes_detections.csv (anomalies)
        output_dir: Directory to save visualization
        config: IRSM configuration
    """
    # Load data
    print("Loading data...")
    all_pairs = pd.read_csv(data_path)
    detections = pd.read_csv(detections_path)
    
    print(f"Total pairs: {len(all_pairs)}")
    print(f"Detected anomalies: {len(detections)}")
    
    # Identify normal vs anomalous pairs
    detection_pair_ids = set(detections['pair_id'].values)
    all_pairs['is_anomaly'] = all_pairs['pair_id'].isin(detection_pair_ids)
    
    normal_pairs = all_pairs[~all_pairs['is_anomaly']]
    anomaly_pairs = all_pairs[all_pairs['is_anomaly']]
    
    print(f"Normal pairs: {len(normal_pairs)}")
    print(f"Anomaly pairs: {len(anomaly_pairs)}")
    
    # Create 3D scatter plot
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection='3d')
    
    # Plot normal pairs (blue)
    ax.scatter(
        normal_pairs['mdrac'],
        normal_pairs['ttc'],
        normal_pairs['closing_speed'],
        c='cornflowerblue',
        marker='o',
        s=50,
        alpha=0.6,
        label=f'Normal ({len(normal_pairs)})',
        edgecolors='navy',
        linewidth=0.5
    )
    
    # Plot detected anomalies (red)
    ax.scatter(
        anomaly_pairs['mdrac'],
        anomaly_pairs['ttc'],
        anomaly_pairs['closing_speed'],
        c='crimson',
        marker='^',
        s=100,
        alpha=0.9,
        label=f'Near-Miss ({len(anomaly_pairs)})',
        edgecolors='darkred',
        linewidth=1
    )
    
    # Labels and title
    ax.set_xlabel('MDRAC (m/s²)', fontsize=11, fontweight='bold')
    ax.set_ylabel('TTC (seconds)', fontsize=11, fontweight='bold')
    ax.set_zlabel('Closing Speed (m/s)', fontsize=11, fontweight='bold')
    
    ax.set_title(
        f'IRSM Risk Vector Space Visualization\n'
        f'Brussels 2025-06-01 | {len(all_pairs)} pairs | '
        f'{len(anomaly_pairs)} anomalies ({len(anomaly_pairs)/len(all_pairs)*100:.1f}%)',
        fontsize=13,
        fontweight='bold',
        pad=20
    )
    
    # Legend
    ax.legend(loc='upper right', fontsize=10, framealpha=0.9)
    
    # Grid
    ax.grid(True, alpha=0.3)
    
    # Improve viewing angle
    ax.view_init(elev=20, azim=45)
    
    # Save figure
    output_path = Path(output_dir) / 'risk_space_3d.png'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✓ Saved: {output_path}")
    
    # Create additional 2D projections
    create_2d_projections(normal_pairs, anomaly_pairs, output_dir)
    
    # Print statistics
    print_statistics(normal_pairs, anomaly_pairs)
    
    plt.show()


def create_2d_projections(normal_pairs, anomaly_pairs, output_dir):
    """Create 2D projection plots for each pair of dimensions"""
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    # MDRAC vs TTC
    axes[0].scatter(normal_pairs['mdrac'], normal_pairs['ttc'], 
                    c='cornflowerblue', alpha=0.6, s=50, label='Normal', edgecolors='navy', linewidth=0.5)
    axes[0].scatter(anomaly_pairs['mdrac'], anomaly_pairs['ttc'], 
                    c='crimson', alpha=0.9, s=100, marker='^', label='Near-Miss', edgecolors='darkred', linewidth=1)
    axes[0].set_xlabel('MDRAC (m/s²)', fontweight='bold')
    axes[0].set_ylabel('TTC (seconds)', fontweight='bold')
    axes[0].set_title('MDRAC vs TTC', fontweight='bold', fontsize=12)
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # MDRAC vs Closing Speed
    axes[1].scatter(normal_pairs['mdrac'], normal_pairs['closing_speed'], 
                    c='cornflowerblue', alpha=0.6, s=50, label='Normal', edgecolors='navy', linewidth=0.5)
    axes[1].scatter(anomaly_pairs['mdrac'], anomaly_pairs['closing_speed'], 
                    c='crimson', alpha=0.9, s=100, marker='^', label='Near-Miss', edgecolors='darkred', linewidth=1)
    axes[1].set_xlabel('MDRAC (m/s²)', fontweight='bold')
    axes[1].set_ylabel('Closing Speed (m/s)', fontweight='bold')
    axes[1].set_title('MDRAC vs Closing Speed', fontweight='bold', fontsize=12)
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    # TTC vs Closing Speed
    axes[2].scatter(normal_pairs['ttc'], normal_pairs['closing_speed'], 
                    c='cornflowerblue', alpha=0.6, s=50, label='Normal', edgecolors='navy', linewidth=0.5)
    axes[2].scatter(anomaly_pairs['ttc'], anomaly_pairs['closing_speed'], 
                    c='crimson', alpha=0.9, s=100, marker='^', label='Near-Miss', edgecolors='darkred', linewidth=1)
    axes[2].set_xlabel('TTC (seconds)', fontweight='bold')
    axes[2].set_ylabel('Closing Speed (m/s)', fontweight='bold')
    axes[2].set_title('TTC vs Closing Speed', fontweight='bold', fontsize=12)
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    
    plt.suptitle('IRSM 2D Projections of Risk Vector Space', 
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    output_path = Path(output_dir) / 'risk_space_2d_projections.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")


def print_statistics(normal_pairs, anomaly_pairs):
    """Print statistical comparison between normal and anomaly pairs"""
    
    print("\n" + "="*70)
    print("RISK VECTOR STATISTICS")
    print("="*70)
    
    metrics = ['mdrac', 'ttc', 'closing_speed', 'distance']
    
    for metric in metrics:
        print(f"\n{metric.upper()}:")
        print(f"  Normal pairs:")
        print(f"    Mean: {normal_pairs[metric].mean():.2f}")
        print(f"    Std:  {normal_pairs[metric].std():.2f}")
        print(f"    Min:  {normal_pairs[metric].min():.2f}")
        print(f"    Max:  {normal_pairs[metric].max():.2f}")
        
        print(f"  Anomaly pairs:")
        print(f"    Mean: {anomaly_pairs[metric].mean():.2f}")
        print(f"    Std:  {anomaly_pairs[metric].std():.2f}")
        print(f"    Min:  {anomaly_pairs[metric].min():.2f}")
        print(f"    Max:  {anomaly_pairs[metric].max():.2f}")
        
        # Calculate separation
        normal_mean = normal_pairs[metric].mean()
        anomaly_mean = anomaly_pairs[metric].mean()
        pooled_std = np.sqrt((normal_pairs[metric].std()**2 + anomaly_pairs[metric].std()**2) / 2)
        effect_size = abs(anomaly_mean - normal_mean) / pooled_std if pooled_std > 0 else 0
        
        print(f"  Effect size (Cohen's d): {effect_size:.2f}")


if __name__ == '__main__':
    # Load config
    config = load_irsm_config()
    
    region = config['region']
    date = config['date']
    output_base = resolve_repo_path(config['data']['output_base'])
    
    # Paths
    data_path = output_base / 'data' / region / date / 'lanes.csv'
    detections_path = output_base / 'results' / region / date / 'lanes_detections.csv'
    output_dir = output_base / 'results' / region / date / 'visualizations'
    
    print(f"\n{'='*70}")
    print(f"IRSM RISK SPACE VISUALIZATION - {region.upper()} - {date}")
    print(f"{'='*70}\n")
    
    # Create visualization
    visualize_risk_space(data_path, detections_path, output_dir, config)
    
    print(f"\n{'='*70}")
    print("VISUALIZATION COMPLETE")
    print(f"{'='*70}\n")
