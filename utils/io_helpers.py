"""
I/O helper utilities for saving and loading detection results.
"""

import pandas as pd
from pathlib import Path
from typing import Optional


def save_detection_results(conflicts: pd.DataFrame,
                           output_dir: str,
                           method: str,
                           region: str,
                           date: str,
                           zone_name: str = None,
                           format: str = 'csv') -> str:
    """
    Save detection results with zone-specific directory structure.
    
    Creates: {output_dir}/{region}/{zone_name}/{date}/mdrac_{date}.csv
    OR: {output_dir}/{region}/{method}/{date}/ if zone_name not specified (backward compat)
    
    Args:
        conflicts: Detection results DataFrame
        output_dir: Base output directory (e.g., '/home/ubuntu/results/prem/mdrac')
        method: Detection method - 'mdrac' or 'spf'  
        region: Region name - 'brussels' or 'oulu'
        date: Date string (YYYY-MM-DD)
        zone_name: Zone name - 'lanes', 'crosswalks', etc. (optional)
        format: Output format - 'csv' or 'xlsx'
        
    Returns:
        Full path to saved file
        
    Example:
        >>> save_detection_results(conflicts, '/home/ubuntu/results/prem/mdrac',
        ...     'mdrac', 'brussels', '2025-06-01', zone_name='lanes')
        '/home/ubuntu/results/prem/mdrac/brussels/lanes/2025-06-01/mdrac_2025-06-01.csv'
    """
    # Create directory structure
    if zone_name:
        # New structure: {output_dir}/{region}/{zone}/{date}/
        output_path = Path(output_dir) / region / zone_name / date
        filename = f"mdrac_{date}.{format}"
    else:
        # Old structure for backward compatibility
        day = date.split('-')[-1]
        output_path = Path(output_dir) / region / method / day
        filename = f"{method}_{day}.{format}"
    
    output_path.mkdir(parents=True, exist_ok=True)
    filepath = output_path / filename
    
    # Save based on format
    if format == 'csv':
        conflicts.to_csv(filepath, index=False)
    elif format == 'xlsx':
        conflicts.to_excel(filepath, index=False, engine='openpyxl')
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'csv' or 'xlsx'")
    
    print(f"✓ Saved {len(conflicts)} conflicts to {filepath}")
    return str(filepath)


def load_detection_results(filepath: str) -> pd.DataFrame:
    """
    Load previously saved detection results.
    
    Args:
        filepath: Path to saved results file (.csv or .xlsx)
        
    Returns:
        DataFrame with detection results
        
    Example:
        >>> df = load_detection_results('results/brussels/mdrac/04/mdrac_04.csv')
        Loaded 123 conflicts
    """
    filepath = Path(filepath)
    
    if filepath.suffix == '.csv':
        df = pd.read_parquet(filepath)
    elif filepath.suffix in ['.xlsx', '.xls']:
        df = pd.read_excel(filepath)
    else:
        raise ValueError(f"Unsupported format: {filepath.suffix}")
    
    print(f"Loaded {len(df)} conflicts from {filepath.name}")
    return df
