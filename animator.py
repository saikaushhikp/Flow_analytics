"""2D trajectory animator producing GIF files from parquet trajectory data.

The animator streams parquet files and produces combined or individual GIF
animations showing the 2D trajectories (pos_x vs pos_y) of one or more objects
over time. Each object is color-coded, and a legend is placed in the top-right.

Example usage:
    # Single object
    python3 animator.py 11791470 --data-dir data --out-dir animations

    # Multiple objects in a single combined GIF
    python3 animator.py 11791470 12345678 --data-dir data --out-dir animations

    # With max animation duration of 30 seconds
    python3 animator.py 11791470 --max-time 30 --data-dir data --out-dir animations

Dependencies: matplotlib, pandas, pyarrow, pillow
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import matplotlib.animation as manimation
import numpy as np
import pandas as pd

try:
    import pyarrow.parquet as pq
except Exception:
    pq = None


DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "animations"
DEFAULT_FPS = 10
DEFAULT_TRAIL_SECONDS = 5
DEFAULT_DPI = 100
DEFAULT_CMAP = "rainbow"


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


def read_trajectory_columns(filepath: Path) -> pd.DataFrame:
    """Read only timestamp, id, pos_x, pos_y columns from a parquet file."""
    columns = ["timestamp", "id", "pos_x", "pos_y"]
    try:
        if pq is not None:
            return pq.read_table(filepath, columns=columns).to_pandas()
        return pd.read_parquet(filepath, columns=columns)
    except Exception as exc:
        raise RuntimeError(f"Failed to read {filepath}: {exc}") from exc


def load_trajectories(
    object_ids: Union[int, Sequence[int]],
    data_dir: Path = DEFAULT_DATA_DIR,
    resample_ms: int | None = None,
) -> dict[int, pd.DataFrame]:
    """Load trajectory data for specified object ids, streaming from parquet files.
    
    Returns a dict mapping object_id -> DataFrame with columns [timestamp, pos_x, pos_y]
    sorted by timestamp.
    """
    target_ids = set(normalize_object_ids(object_ids))
    if not target_ids:
        return {}

    parquet_files = discover_parquet_files(data_dir)
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found under {data_dir}")

    trajectories: dict[int, list] = {oid: [] for oid in target_ids}

    for filepath in parquet_files:
        frame = read_trajectory_columns(filepath)
        frame = frame[frame["id"].isin(target_ids)]
        
        if frame.empty:
            continue

        for object_id, rows in frame.groupby("id", sort=False):
            # Keep only required columns and append as a list for efficiency
            traj_data = rows[["timestamp", "pos_x", "pos_y"]].values.tolist()
            trajectories[object_id].extend(traj_data)

    # Convert lists to DataFrames and sort by timestamp
    result = {}
    for object_id, points in trajectories.items():
        if not points:
            continue
        
        df = pd.DataFrame(points, columns=["timestamp", "pos_x", "pos_y"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        # Optionally resample
        if resample_ms is not None and len(df) > 1:
            df = resample_trajectory(df, resample_ms)
        
        result[object_id] = df

    return result


def resample_trajectory(df: pd.DataFrame, resample_ms: int) -> pd.DataFrame:
    """Resample trajectory to uniform time intervals (resample_ms milliseconds apart)."""
    if df.empty or len(df) < 2:
        return df

    df = df.set_index("timestamp")
    resampled = df.resample(f"{resample_ms}ms").interpolate(method="index")
    resampled = resampled.dropna()
    resampled = resampled.reset_index()
    return resampled


def compute_bounds(trajectories: dict[int, pd.DataFrame]) -> Tuple[float, float, float, float]:
    """Compute global x,y bounds from all trajectories."""
    all_x = []
    all_y = []
    
    for df in trajectories.values():
        all_x.extend(df["pos_x"].values)
        all_y.extend(df["pos_y"].values)
    
    if not all_x or not all_y:
        return 0, 100, 0, 100
    
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)
    
    # Add 10% padding
    x_pad = (x_max - x_min) * 0.1 if x_max != x_min else 5
    y_pad = (y_max - y_min) * 0.1 if y_max != y_min else 5
    
    return x_min - x_pad, x_max + x_pad, y_min - y_pad, y_max + y_pad


def get_frame_times(
    trajectories: dict[int, pd.DataFrame],
    fps: int = DEFAULT_FPS,
    max_time_seconds: float | None = None,
) -> np.ndarray:
    """Generate uniformly spaced frame times."""
    if not trajectories:
        return np.array([])
    
    min_time = min(df["timestamp"].min() for df in trajectories.values())
    max_time = max(df["timestamp"].max() for df in trajectories.values())
    
    # If max_time_seconds is set, cap the animation duration
    if max_time_seconds is not None:
        max_time = min_time + pd.Timedelta(seconds=max_time_seconds)
    
    frame_interval = pd.Timedelta(seconds=1.0 / fps)
    times = []
    current_time = min_time
    
    while current_time <= max_time:
        times.append(current_time)
        current_time += frame_interval
    
    return np.array(times)


def get_trajectory_up_to_time(
    df: pd.DataFrame,
    current_time: pd.Timestamp,
    trail_seconds: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Get trajectory points up to current_time.
    
    Returns: (x_coords, y_coords)
    Points within the trail_seconds window are returned.
    """
    subset = df[df["timestamp"] <= current_time].copy()
    
    if subset.empty:
        return np.array([]), np.array([])
    
    # Filter to trail window if specified
    if trail_seconds > 0:
        trail_start_time = current_time - pd.Timedelta(seconds=trail_seconds)
        subset = subset[subset["timestamp"] >= trail_start_time]
    
    if subset.empty:
        return np.array([]), np.array([])
    
    x = subset["pos_x"].values
    y = subset["pos_y"].values
    
    return x, y


def create_animation(
    trajectories: dict[int, pd.DataFrame],
    frame_times: np.ndarray,
    fps: int = DEFAULT_FPS,
    trail_seconds: float = DEFAULT_TRAIL_SECONDS,
    dpi: int = DEFAULT_DPI,
    cmap: str = DEFAULT_CMAP,
) -> Tuple[plt.Figure, manimation.FuncAnimation]:
    """Create a matplotlib animation of the trajectories."""
    
    fig, ax = plt.subplots(figsize=(10, 8), dpi=dpi)
    x_min, x_max, y_min, y_max = compute_bounds(trajectories)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("Position X")
    ax.set_ylabel("Position Y")
    ax.set_title("2D Trajectory Animation")
    ax.set_aspect("equal", adjustable="box")
    
    # Set up color map
    object_ids = sorted(trajectories.keys())
    cmap_obj = plt.get_cmap(cmap)
    n_objects = len(object_ids)
    colors = [cmap_obj(i % cmap_obj.N) for i in np.linspace(0, 1, n_objects)]
    id_to_color = {oid: colors[i] for i, oid in enumerate(object_ids)}
    
    # Storage for lines and scatter points
    lines = {}
    scatter_points = {}
    
    for object_id in object_ids:
        line, = ax.plot([], [], lw=2, alpha=0.7, color=id_to_color[object_id])
        lines[object_id] = line
        scatter, = ax.plot([], [], 'o', markersize=8, color=id_to_color[object_id])
        scatter_points[object_id] = scatter
    
    # Add legend at top-right
    legend_lines = [plt.Line2D([0], [0], color=id_to_color[oid], lw=2, label=f"ID: {oid}")
                    for oid in object_ids]
    ax.legend(handles=legend_lines, loc="upper right", fontsize=9)
    
    # Time display text
    time_text = ax.text(0.02, 0.98, "", transform=ax.transAxes, verticalalignment="top",
                       fontsize=10, bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
    
    def animate(frame_idx):
        if frame_idx >= len(frame_times):
            return []
        
        current_time = frame_times[frame_idx]
        time_text.set_text(f"Time: {pd.Timestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}")
        
        artists = []
        for object_id in object_ids:
            df = trajectories[object_id]
            x, y = get_trajectory_up_to_time(df, current_time, trail_seconds)
            
            if len(x) > 0:
                # Plot trajectory line
                lines[object_id].set_data(x, y)
                artists.append(lines[object_id])
                
                # Current position (most recent point)
                scatter_points[object_id].set_data([x[-1]], [y[-1]])
                artists.append(scatter_points[object_id])
            else:
                lines[object_id].set_data([], [])
                scatter_points[object_id].set_data([], [])
                artists.append(lines[object_id])
                artists.append(scatter_points[object_id])
        
        artists.append(time_text)
        return artists
    
    anim = manimation.FuncAnimation(
        fig, animate, frames=len(frame_times), interval=1000/fps, blit=True, repeat=True
    )
    
    return fig, anim


def save_animation_gif(
    anim: manimation.FuncAnimation,
    output_path: Path,
    fps: int = DEFAULT_FPS,
) -> None:
    """Save animation as a GIF using PillowWriter."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Saving ...")
    writer = manimation.PillowWriter(fps=fps)
    anim.save(str(output_path), writer=writer)
    print(f"\N{CHECK MARK} Animation saved to {output_path}")
    return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Animate 2D trajectories from parquet files as GIF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single object
  python3 animator.py 11791470 --data-dir data --out-dir animations
  
  # Multiple objects in combined GIF
  python3 animator.py 11791470 12345678 --data-dir data --out-dir animations
  
  # With 30-second max duration
  python3 animator.py 11791470 --max-time 30 --data-dir data --out-dir animations
        """,
    )
    
    parser.add_argument(
        "object_ids",
        nargs="+",
        help="One or more object IDs to animate.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Path to the parquet data directory.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory for the GIF file.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        help="Frames per second for the animation.",
    )
    parser.add_argument(
        "--trail-seconds",
        type=float,
        default=DEFAULT_TRAIL_SECONDS,
        help="Duration (seconds) to show trail effect behind objects.",
    )
    parser.add_argument(
        "--resample-ms",
        type=int,
        default=None,
        help="Resample trajectory to this interval (milliseconds). Default: no resampling.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help="DPI for figure resolution.",
    )
    parser.add_argument(
        "--cmap",
        type=str,
        default=DEFAULT_CMAP,
        help="Matplotlib colormap name for object colors.",
    )
    parser.add_argument(
        "--max-time",
        type=float,
        default=90,
        help="Maximum animation duration in seconds from start.",
    )
    parser.add_argument(
        "--separate",
        action="store_true",
        help="Also produce individual GIFs for each object.",
    )
    
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    object_ids = [int(oid) for oid in args.object_ids]
    
    print(f"Loading trajectories for {len(object_ids)} object(s)...")
    trajectories = load_trajectories(
        object_ids=object_ids,
        data_dir=args.data_dir,
        resample_ms=args.resample_ms,
    )
    
    if not trajectories:
        print("No trajectory data found for the specified object IDs.")
        return
    
    print(f"\N{CHECK MARK} Loaded {len(trajectories)} object(s)")
    for oid, df in trajectories.items():
        print(f"  - ID {oid}: {len(df)} points")
    
    # Generate frame times
    frame_times = get_frame_times(trajectories, fps=args.fps, max_time_seconds=args.max_time)
    print(f"\N{CHECK MARK} Generated {len(frame_times)} frames at {args.fps} FPS")
    
    # Create combined animation
    print("Creating animation...")
    fig, anim = create_animation(
        trajectories=trajectories,
        frame_times=frame_times,
        fps=args.fps,
        trail_seconds=args.trail_seconds,
        dpi=args.dpi,
        cmap=args.cmap,
    )
    
    # Save combined GIF
    combined_filename = "_".join(str(oid) for oid in sorted(object_ids)) + ".gif"
    combined_path = args.out_dir / combined_filename
    save_animation_gif(anim, combined_path, fps=args.fps)
    plt.close(fig)
    
    # Optionally save individual GIFs
    if args.separate:
        print(f"\N{CHECK MARK} Creating individual animations...")
        for object_id in sorted(object_ids):
            single_traj = {object_id: trajectories[object_id]}
            frame_times_single = get_frame_times(
                single_traj, fps=args.fps, max_time_seconds=args.max_time
            )
            fig_single, anim_single = create_animation(
                trajectories=single_traj,
                frame_times=frame_times_single,
                fps=args.fps,
                trail_seconds=args.trail_seconds,
                dpi=args.dpi,
                cmap=args.cmap,
            )
            
            single_filename = f"{object_id}.gif"
            single_path = args.out_dir / single_filename
            save_animation_gif(anim_single, single_path, fps=args.fps)
            plt.close(fig_single)
    
    print(f"\N{CHECK MARK} Animation creation complete!")
    return 


if __name__ == "__main__":
    main()
