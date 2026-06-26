import os
import pandas as pd
import numpy as np
from pathlib import Path

CANONICAL_COLUMNS = [
    'date',
    'pair_id',
    'timestamp',
    'zone',
    'source_family',
    'score_raw',
    'score_calibrated',
    'binary_prediction',
    'rank_within_day',
    'threshold_version',
    'label_gold',
    'is_lidar_artifact',
    'link'
]

def save_canonical_predictions(
    df: pd.DataFrame,
    region: str,
    date: str,
    source_family: str,
    score_col: str,
    binary_pred_col: str,
    zone: str = 'lanes',
    score_calibrated_col: str = None,
    threshold_version: str = 'v1',
    link_col: str = 'link',
    timestamp_col: str = 'timestamp',
    id1_col: str = 'id1',
    id2_col: str = 'id2',
    pair_id_col: str = 'pair_id',
    output_dir: str = None
) -> str:
    """
    Format and save detection results to a canonical CSV file.
    """
    if len(df) == 0:
        empty_df = pd.DataFrame(columns=CANONICAL_COLUMNS)
        return _write_canonical(empty_df, region, date, source_family, output_dir)
        
    df = df.copy()
    
    # Standardize pair_id
    if pair_id_col in df.columns:
        # If it's already pair_id, ensure order-independence: min_id_max_id
        def std_pair_id(pid):
            parts = str(pid).split('_')
            if len(parts) == 2:
                try:
                    i1, i2 = int(parts[0]), int(parts[1])
                    return f"{min(i1, i2)}_{max(i1, i2)}"
                except ValueError:
                    return f"{min(parts[0], parts[1])}_{max(parts[0], parts[1])}"
            return str(pid)
        df['canonical_pair_id'] = df[pair_id_col].apply(std_pair_id)
    elif id1_col in df.columns and id2_col in df.columns:
        # Create canonical pair_id from individual IDs
        df['canonical_pair_id'] = df.apply(
            lambda r: f"{min(int(r[id1_col]), int(r[id2_col]))}_{max(int(r[id1_col]), int(r[id2_col]))}",
            axis=1
        )
    else:
        # Fallback to index if no pair columns
        df['canonical_pair_id'] = [f"unknown_{i}" for i in range(len(df))]
        
    # Get values
    dates = [date] * len(df)
    timestamps = df[timestamp_col].astype(str).values if timestamp_col in df.columns else ['unknown'] * len(df)
    zones = df['zone'].astype(str).values if 'zone' in df.columns else [zone] * len(df)
    score_raw = df[score_col].astype(float).values
    
    if score_calibrated_col in df.columns:
        score_calibrated = df[score_calibrated_col].astype(float).values
    elif score_calibrated_col is not None and isinstance(score_calibrated_col, (int, float)):
        score_calibrated = np.full(len(df), float(score_calibrated_col))
    else:
        score_calibrated = score_raw  # Default to raw score if calibration is not available
        
    binary_prediction = df[binary_pred_col].astype(int).values
    links = df[link_col].astype(str).values if link_col in df.columns else [''] * len(df)
    
    # Create canonical df
    canonical_df = pd.DataFrame({
        'date': dates,
        'pair_id': df['canonical_pair_id'].values,
        'timestamp': timestamps,
        'zone': zones,
        'source_family': [source_family] * len(df),
        'score_raw': score_raw,
        'score_calibrated': score_calibrated,
        'binary_prediction': binary_prediction,
        'threshold_version': [threshold_version] * len(df),
        'label_gold': [np.nan] * len(df),
        'is_lidar_artifact': [np.nan] * len(df),
        'link': links
    })
    
    # Sort and rank within day
    canonical_df = canonical_df.sort_values(by='score_raw', ascending=False).reset_index(drop=True)
    canonical_df['rank_within_day'] = np.arange(1, len(canonical_df) + 1)
    
    # Reorder columns
    canonical_df = canonical_df[CANONICAL_COLUMNS]
    
    return _write_canonical(canonical_df, region, date, source_family, output_dir)

def _write_canonical(df: pd.DataFrame, region: str, date: str, source_family: str, output_dir: str = None) -> str:
    if output_dir is None:
        # Default to irsm/results/{region}/{date}/canonical/
        repo_root = Path(__file__).resolve().parents[1]
        output_dir = repo_root / 'irsm' / 'results' / region / date / 'canonical'
    else:
        output_dir = Path(output_dir)
        
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{source_family}.csv"
    # temporarily commenting the below saving script to avoid overwriting the canonical files
    # df.to_csv(file_path, index=False)
    return str(file_path)
