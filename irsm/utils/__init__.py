"""
IRSM Utility Functions

Helper functions for data processing and validation.
"""

import pandas as pd
import numpy as np
from typing import Tuple


def split_pair_id(pair_id: str) -> Tuple[int, int]:
    """
    Split pair_id string into individual IDs.
    
    Args:
        pair_id: String in format "{id1}_{id2}"
        
    Returns:
        Tuple of (id1, id2)
        
    Example:
        >>> id1, id2 = split_pair_id("10520140_10520195")
        >>> print(id1, id2)
        10520140 10520195
    """
    id1_str, id2_str = pair_id.split('_')
    return int(id1_str), int(id2_str)


def create_pair_id(id1: int, id2: int) -> str:
    """
    Create pair_id string from individual IDs.
    
    Args:
        id1: First vehicle ID
        id2: Second vehicle ID
        
    Returns:
        String in format "{id1}_{id2}"
        
    Example:
        >>> pair_id = create_pair_id(10520140, 10520195)
        >>> print(pair_id)
        10520140_10520195
    """
    return f"{id1}_{id2}"


def validate_risk_vector_csv(csv_path: str) -> bool:
    """
    Validate that a risk vector CSV has correct schema.
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        True if valid, raises ValueError otherwise
    """
    df = pd.read_csv(csv_path, nrows=5)
    
    # Check required columns
    required = ['pair_id', 'timestamp', 'link']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Check pair_id format
    sample_pair_id = df['pair_id'].iloc[0]
    if '_' not in sample_pair_id:
        raise ValueError(f"Invalid pair_id format: {sample_pair_id}")
    
    # Check feature columns (should have numeric features after metadata)
    feature_cols = df.columns[3:]
    if len(feature_cols) == 0:
        raise ValueError("No feature columns found")
    
    return True


def print_dataset_summary(csv_path: str):
    """
    Print summary statistics for a risk vector dataset.
    
    Args:
        csv_path: Path to risk vector CSV
    """
    df = pd.read_csv(csv_path)
    
    print(f"\n{'='*70}")
    print(f"DATASET SUMMARY: {csv_path}")
    print(f"{'='*70}")
    print(f"Total pairs:     {len(df):,}")
    print(f"Total features:  {len(df.columns) - 3}")  # Exclude metadata
    
    # Feature statistics
    feature_cols = df.columns[3:]
    print(f"\nFeature ranges:")
    for col in feature_cols[:5]:  # Show first 5 features
        print(f"  {col:20s}: [{df[col].min():.3f}, {df[col].max():.3f}]")
    if len(feature_cols) > 5:
        print(f"  ... and {len(feature_cols) - 5} more features")
    
    print(f"{'='*70}\n")
