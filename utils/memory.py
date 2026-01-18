"""
Memory monitoring utilities for tracking resource usage during processing.
"""

import psutil
import pandas as pd


def log_memory(label: str = "") -> float:
    """
    Log current process memory usage.
    
    Args:
        label: Description label for the log
        
    Returns:
        Memory usage in MB
        
    Example:
        >>> mem = log_memory("After loading data")
        [MEMORY] After loading data: 1234.5 MB
    """
    process = psutil.Process()
    mem_mb = process.memory_info().rss / 1024 / 1024
    print(f"[MEMORY] {label}: {mem_mb:.1f} MB")
    return mem_mb


def log_df_memory(df: pd.DataFrame, name: str = "DataFrame") -> float:
    """
    Log DataFrame memory usage with row count.
    
    Args:
        df: pandas DataFrame to analyze
        name: DataFrame description
        
    Returns:
        Memory usage in MB
        
    Example:
        >>> mem = log_df_memory(df, "Vehicle data")
        [DF MEMORY] Vehicle data: 234.5 MB (1,234,567 rows)
    """
    mem_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
    print(f"[DF MEMORY] {name}: {mem_mb:.1f} MB ({len(df):,} rows)")
    return mem_mb
