"""
Trajectory data loading utilities.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Mapping

import pandas as pd
from tqdm import tqdm


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _folder_in_range(folder_name: str, start_date: str, end_date: str) -> bool:
    """Return True when a folder starts with a YYYY-MM-DD date in range."""
    try:
        folder_date = _parse_date(folder_name[:10])
    except ValueError:
        return False

    return _parse_date(start_date) <= folder_date <= _parse_date(end_date)


def _read_parquet_folder(path: Path) -> pd.DataFrame:
    """Read one parquet folder or file."""
    return pd.read_parquet(path)


def load_data(
    data_dir: str | Path,
    start_date: str,
    end_date: str,
    dtypes: Mapping[str, str] | None = None,
    max_hours: int | None = None,
    sample_limit: int | None = None,
) -> pd.DataFrame:
    """
    Load trajectory parquet folders for an inclusive date range.

    The expected structure is one parquet file or parquet directory per hour,
    with folder names beginning with YYYY-MM-DD.
    """
    data_path = Path(data_dir).expanduser()
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory does not exist: {data_path}")

    folders = [
        child
        for child in sorted(data_path.iterdir())
        if child.is_dir() and _folder_in_range(child.name, start_date, end_date)
    ]

    if max_hours is not None:
        if max_hours < 1:
            raise ValueError("max_hours must be >= 1")
        folders = folders[:max_hours]

    frames = []
    for folder in tqdm(folders, desc="Loading data"):
        chunk = _read_parquet_folder(folder)

        if dtypes:
            for col, dtype in dtypes.items():
                if col in chunk.columns:
                    chunk[col] = chunk[col].astype(dtype)

        frames.append(chunk)

        if sample_limit is not None and sum(len(frame) for frame in frames) >= sample_limit:
            break

    if not frames:
        print("No data found for given date range.")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    if sample_limit is not None:
        if sample_limit < 1:
            raise ValueError("sample_limit must be >= 1")
        df = df.head(sample_limit).copy()

    return df
