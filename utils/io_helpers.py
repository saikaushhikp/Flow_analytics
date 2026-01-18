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
                           format: str = 'csv') -> str:
    """
    Save detection results with consistent directory structure and naming.
    
    Creates directory structure: {output_dir}/{region}/{method}/{date}/
    
    Args:
        conflicts: Detection results DataFrame
        output_dir: Base output directory (e.g., 'results')
        method: Detection method - 'mdrac' or 'spf'
        region: Region name - 'brussels' or 'oulu'
        date: Date string (YYYY-MM-DD or similar)
        format: Output format - 'csv' or 'xlsx'
        
    Returns:
        Full path to saved file
        
    Example:
        >>> path = save_detection_results(mdrac_conflicts, 
        ...     'results', 'mdrac', 'brussels', '2025-06-04')
        '✓ Saved 123 conflicts to results/brussels/mdrac/04/mdrac_04.csv'
    """
    # Create directory structure
    day = date.split('-')[-1]  # Extract day (e.g., '04' from '2025-06-04')
    output_path = Path(output_dir) / region / method / day
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    filename = f"{method}_{day}.{format}"
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
