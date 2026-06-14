"""Stream object appearance intervals from parquet trajectory files.

The tracker reads each parquet file independently and only loads the
`timestamp` and `id` columns. That keeps the memory footprint much lower than
loading the full dataset at once.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Sequence, Union

import pandas as pd

try:
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover - fallback when pyarrow is unavailable
    pq = None


DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_GAP_TOLERANCE = pd.Timedelta(seconds=1)


def discover_parquet_files(data_dir: Path) -> List[Path]:
    """Return all parquet files under the dataset directory in sorted order."""

    return sorted(data_dir.rglob("*.parquet"))


def normalize_object_ids(object_ids: Union[int, Sequence[int]]) -> List[int]:
    """Normalize a single id or a sequence of ids into a unique list of ints."""

    if isinstance(object_ids, int):
        return [object_ids]

    normalized: List[int] = []
    seen = set()
    for object_id in object_ids:
        value = int(object_id)
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized


def read_id_timestamp_columns(filepath: Path) -> pd.DataFrame:
    """Read only the object id and timestamp columns from a parquet file."""

    columns = ["timestamp", "id"]
    if pq is not None:
        return pq.read_table(filepath, columns=columns).to_pandas()

    return pd.read_parquet(filepath, columns=columns)


def split_into_contiguous_intervals(
    rows: pd.DataFrame,
    gap_tolerance: pd.Timedelta,
) -> List[dict]:
    """Split a single object's rows into contiguous timestamp intervals."""

    if rows.empty:
        return []

    ordered = rows.sort_values("timestamp", kind="mergesort")
    timestamps = ordered["timestamp"].tolist()

    intervals: List[dict] = []
    interval_start = timestamps[0]
    interval_end = timestamps[0]
    frame_count = 1

    for timestamp in timestamps[1:]:
        if timestamp - interval_end <= gap_tolerance:
            interval_end = timestamp
            frame_count += 1
        else:
            intervals.append(
                {
                    "start": interval_start,
                    "end": interval_end,
                    "frames": frame_count,
                }
            )
            interval_start = timestamp
            interval_end = timestamp
            frame_count = 1

    intervals.append(
        {
            "start": interval_start,
            "end": interval_end,
            "frames": frame_count,
        }
    )
    return intervals


def finalize_interval(object_id: int, interval: dict) -> dict:
    """Convert the internal interval representation into a report row."""

    return {
        "object_id": object_id,
        "appearance_start": interval["start"],
        "appearance_end": interval["end"],
        "frame_count": interval["frames"],
        "file_count": len(interval["files"]),
        "source_files": ", ".join(sorted(interval["files"])),
    }


def track_object_appearances(
    object_ids: Union[int, Sequence[int]],
    data_dir: Path = DEFAULT_DATA_DIR,
    gap_tolerance: pd.Timedelta = DEFAULT_GAP_TOLERANCE,
) -> pd.DataFrame:
    """Find appearance intervals for one or more object ids.

    The function streams through each parquet file independently, keeping only
    the `timestamp` and `id` columns in memory.
    """

    target_ids = set(normalize_object_ids(object_ids))
    if not target_ids:
        return pd.DataFrame(
            columns=[
                "object_id",
                "appearance_start",
                "appearance_end",
                "frame_count",
                "file_count",
                "source_files",
            ]
        )

    parquet_files = discover_parquet_files(data_dir)
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found under {data_dir}")

    active_intervals: dict[int, dict] = {}
    completed_rows: List[dict] = []

    for filepath in parquet_files:
        try:
            frame = read_id_timestamp_columns(filepath)
        except Exception as exc:  # pragma: no cover - surfaced to caller
            raise RuntimeError(f"Failed to read {filepath}: {exc}") from exc

        if frame.empty:
            continue

        frame = frame[frame["id"].isin(target_ids)]
        if frame.empty:
            continue

        for object_id, object_rows in frame.groupby("id", sort=False):
            intervals = split_into_contiguous_intervals(object_rows, gap_tolerance)
            for interval in intervals:
                interval["files"] = {filepath.name}
                active = active_intervals.get(object_id)

                if active is not None and interval["start"] - active["end"] <= gap_tolerance:
                    active["end"] = max(active["end"], interval["end"])
                    active["frames"] += interval["frames"]
                    active["files"].add(filepath.name)
                else:
                    if active is not None:
                        completed_rows.append(finalize_interval(object_id, active))

                    active_intervals[object_id] = {
                        "start": interval["start"],
                        "end": interval["end"],
                        "frames": interval["frames"],
                        "files": set(interval["files"]),
                    }

    for object_id, interval in active_intervals.items():
        completed_rows.append(finalize_interval(object_id, interval))

    result = pd.DataFrame(completed_rows)
    if result.empty:
        return pd.DataFrame(
            columns=[
                "object_id",
                "appearance_start",
                "appearance_end",
                "frame_count",
                "file_count",
                "source_files",
            ]
        )

    return result.sort_values(["object_id", "appearance_start"]).reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track object appearance intervals across parquet files."
    )
    parser.add_argument(
        "object_ids",
        nargs="+",
        help="One object id or a space-separated list of object ids.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Path to the parquet data directory.",
    )
    parser.add_argument(
        "--gap-seconds",
        type=float,
        default=1.0,
        help="Maximum allowed gap between rows before a new interval starts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    object_ids = [int(value) for value in args.object_ids]
    gap_tolerance = pd.Timedelta(seconds=args.gap_seconds)

    result = track_object_appearances(
        object_ids=object_ids,
        data_dir=args.data_dir,
        gap_tolerance=gap_tolerance,
    )

    if result.empty:
        print("No matching object appearances were found.")
        return

    with pd.option_context("display.max_rows", None, "display.max_colwidth", None):
        print(result.to_string(index=False))


if __name__ == "__main__":
    main()