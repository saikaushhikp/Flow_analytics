"""
Trajectory data loading utilities.
"""

from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from typing import Mapping

import pandas as pd
from tqdm import tqdm


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _parse_start_time(value: str) -> time:
    """Parse either HH or HH:MM into a time object."""
    formats = ("%H", "%H:%M")
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError("start_time must be in HH or HH:MM format")


def _folder_datetime(folder_name: str) -> datetime | None:
    """Parse a folder name like YYYY-MM-DD-HH into a datetime."""
    try:
        folder_date = _parse_date(folder_name[:10]).date()
        folder_hour = int(folder_name[11:13])
    except ValueError:
        return None
    return datetime.combine(folder_date, time(hour=folder_hour))


def _folder_in_range(
    folder_name: str,
    start_date: str,
    end_date: str,
    start_time: str,
) -> bool:
    """Return True when a folder timestamp falls within the requested range."""
    folder_dt = _folder_datetime(folder_name)
    if folder_dt is None:
        return False

    start_dt = datetime.combine(_parse_date(start_date).date(), _parse_start_time(start_time))
    end_dt = datetime.combine(_parse_date(end_date).date(), time(23, 59, 59, 999999))
    return start_dt <= folder_dt <= end_dt


def _read_parquet_folder(path: Path) -> pd.DataFrame:
    """Read one parquet folder or file."""
    return pd.read_parquet(path)


def load_data(
    data_dir: str | Path,
    start_date: str,
    end_date: str,
    start_time: str = "00",
    dtypes: Mapping[str, str] | None = None,
    max_hours: int | None = None,
    sample_limit: int | None = None,
) -> pd.DataFrame:
    """
    Load trajectory parquet folders for an inclusive date range.

    The expected structure is one parquet file or parquet directory per hour,
    with folder names beginning with YYYY-MM-DD-HH.
    """
    data_path = Path(data_dir).expanduser()
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory does not exist: {data_path}")

    folders = [
        child
        for child in sorted(data_path.iterdir())
        if child.is_dir() and _folder_in_range(child.name, start_date, end_date, start_time)
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
