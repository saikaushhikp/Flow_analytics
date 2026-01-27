"""
Utility functions for VLM validation and batch processing.
"""

import re
import sys
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Add prem to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def parse_validation_response(response_text: str) -> Dict:
    """
    Parse VLM response into structured format.
    
    Expected format:
        Classification: confirmed_near_miss
        Confidence: 85%
        Reasoning: [detailed explanation]
    
    Args:
        response_text: Raw VLM response
        
    Returns:
        Dictionary with parsed fields:
        - classification: str
        - confidence: int
        - reasoning: str
    """
    result = {
        'classification': 'uncertain',
        'confidence': 50,
        'reasoning': 'Failed to parse response',
    }
    
    # Normalize text
    text = response_text.strip()
    
    # Extract classification
    class_patterns = [
        r'Classification:\s*([^\n]+)',
        r'classification:\s*([^\n]+)',
        r'CLASSIFICATION:\s*([^\n]+)',
    ]
    
    for pattern in class_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            classification = match.group(1).strip().lower()
            # Normalize classification values
            if 'confirm' in classification or 'near' in classification or 'miss' in classification:
                result['classification'] = 'confirmed_near_miss'
            elif 'false' in classification or 'negative' in classification or 'not' in classification:
                result['classification'] = 'false_positive'
            else:
                result['classification'] = 'uncertain'
            break
    
    # Extract confidence
    conf_patterns = [
        r'Confidence:\s*(\d+)',
        r'confidence:\s*(\d+)',
        r'CONFIDENCE:\s*(\d+)',
        r'(\d+)%',
    ]
    
    for pattern in conf_patterns:
        match = re.search(pattern, text)
        if match:
            confidence = int(match.group(1))
            # Clamp to 0-100
            result['confidence'] = max(0, min(100, confidence))
            break
    
    # Extract reasoning
    reasoning_patterns = [
        r'Reasoning:\s*(.+?)(?=\n\n|\Z)',
        r'reasoning:\s*(.+?)(?=\n\n|\Z)',
        r'REASONING:\s*(.+?)(?=\n\n|\Z)',
    ]
    
    for pattern in reasoning_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            reasoning = match.group(1).strip()
            # Clean up reasoning
            reasoning = re.sub(r'\n+', '\n', reasoning)  # Remove multiple newlines
            reasoning = re.sub(r'^\s*-\s*', '', reasoning, flags=re.MULTILINE)  # Remove bullet points
            result['reasoning'] = reasoning
            break
    
    # If no structured format found, try to extract from free text
    if result['reasoning'] == 'Failed to parse response':
        # Use entire response as reasoning
        result['reasoning'] = text
        
        # Try to infer classification from keywords in text
        text_lower = text.lower()
        if any(word in text_lower for word in ['confirmed', 'genuine', 'valid near-miss', 'true near-miss']):
            result['classification'] = 'confirmed_near_miss'
        elif any(word in text_lower for word in ['false positive', 'not a near-miss', 'no collision risk']):
            result['classification'] = 'false_positive'
    
    return result


# =============================================================================
# Batch Processing Helper Functions
# =============================================================================

def load_mdrac_csv(csv_path: str) -> pd.DataFrame:
    """
    Load MDRAC CSV file and return as DataFrame.
    
    Args:
        csv_path: Path to MDRAC detection results CSV
        
    Returns:
        DataFrame with detection data
    """
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    return df


def extract_pair_data(df: pd.DataFrame, id1: int, id2: int) -> Dict:
    """
    Extract event data for a specific pair from MDRAC DataFrame.
    
    Args:
        df: Loaded MDRAC DataFrame
        id1: First vehicle ID
        id2: Second vehicle ID
    
    Returns:
        Dictionary with event data (Brussels MDRAC schema)
        Keys: timestamp, id1, id2, zone, interaction, leader, dist, 
              TTC, MDRAC, closing_speed, speed_diff, yaw_diff, link
    """
    # Try both orderings of IDs
    mask = ((df['id1'] == id1) & (df['id2'] == id2)) | \
           ((df['id1'] == id2) & (df['id2'] == id1))
    
    matching_rows = df[mask]
    
    if len(matching_rows) == 0:
        raise ValueError(f"No event found with pair IDs: {id1}, {id2}")
    
    if len(matching_rows) > 1:
        print(f"  Warning: Found {len(matching_rows)} matching rows for ({id1}, {id2}). Using first.")
    
    row = matching_rows.iloc[0]
    
    # Extract event data with Brussels MDRAC schema
    event_data = {
        'timestamp': str(row['timestamp']),
        'id1': int(row['id1']),
        'id2': int(row['id2']),
        'zone': str(row['zone']),
        'interaction': str(row['interaction']),
        'leader': int(row['leader']),
        'dist': float(row['dist']),
        'TTC': float(row['TTC']),
        'MDRAC': float(row['MDRAC']),
        'closing_speed': float(row['closing_speed']),
        'speed_diff': float(row['speed_diff']),
        'yaw_diff': float(row['yaw_diff']),
        'link': str(row['link']),
    }
    
    return event_data


def save_combined_plot(
    data_df: pd.DataFrame,
    id1: int,
    id2: int, 
    event_data: Dict,
    output_path: str,
    time_window: Optional[float] = None
) -> str:
    """
    Generate and save combined plot using plotter.py functions.
    
    Creates a 2×3 grid of equal-sized plots:
    - Trajectory (2D spatial)
    - Distance over time
    - Closing speed over time
    - Velocity comparison
    - Yaw difference over time
    - (Empty placeholder)
    
    Args:
        data_df: Full trajectory DataFrame
        id1: First vehicle ID
        id2: Second vehicle ID
        event_data: Event metrics from CSV
        output_path: Where to save combined plot
        time_window: Optional time window around conflict (seconds)
    
    Returns:
        Path to saved combined plot image
    """
    from plotter import (
        extract_trajectories,
        calculate_temporal_metrics,
        plot_trajectories,
        plot_distance_over_time,
        plot_closing_speed_over_time,
        plot_velocity_over_time,
        plot_yaw_diff_over_time
    )
    
    # Extract data using plotter.py functions
    traj1, traj2 = extract_trajectories(data_df, id1, id2, time_window)
    metrics = calculate_temporal_metrics(traj1, traj2)
    
    # Create figure with 2×3 grid of EQUAL-SIZED subplots
    fig, axes = plt.subplots(2, 3, figsize=(21, 14))
    fig.subplots_adjust(hspace=0.35, wspace=0.3)
    
    # Flatten axes for easy indexing
    ax1, ax2, ax3, ax4, ax5, ax6 = axes.flatten()
    
    # Generate plots using plotter.py functions (pass axes)
    plot_trajectories(traj1, traj2, id1, id2, ax=ax1)
    plot_distance_over_time(metrics, ax=ax2)
    plot_closing_speed_over_time(metrics, ax=ax3)
    plot_velocity_over_time(metrics, id1, id2, ax=ax4)
    plot_yaw_diff_over_time(metrics, ax=ax5)
    
    # Hide the 6th subplot (not needed)
    ax6.axis('off')
    
    # Overall title
    fig.suptitle(f'Near-Miss Analysis: {id1} vs {id2}',
                 fontsize=18, fontweight='bold', y=0.98)
    
    # Save with high quality
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    
    return output_path
