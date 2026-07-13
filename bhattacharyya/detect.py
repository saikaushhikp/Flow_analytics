"""
Bhattacharyya Envelope Near-Miss - Detection Script (Unified)

Loads raw trajectory data directly, generates nearby vehicle pairs in-memory,
computes BC² envelope overlap, applies post-processing filters, and saves
confirmed near-miss detections to:
    results/bhattacharyya/brussels/lanes/<date>/detections.csv
    results/bhattacharyya/brussels/lanes/<date>/summary.yaml

Usage:
    conda run -n flow_env python bhattacharyya/detect.py --date 2025-06-01
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bhattacharyya.envelope import get_envelope_near_misses
from ssm.utils import load_config, find_all_nearby_pairs
from utils import brussels_data_dir, load_data
from utils.irsm_preprocessing import apply_preprocessing_filters


# Label area bounds (min_area_m2, max_area_m2)
LABEL_AREA_BOUNDS = {
    0: (0.0, 999.0),    # unknown
    1: (0.1,  2.0),     # pedestrian
    2: (0.2,  3.0),     # bicycle
    3: (0.3,  4.0),     # motorcycle
    4: (1.5, 16.0),     # car
    5: (0.1,  2.5),     # e-scooter
    6: (4.0, 30.0),     # van
    7: (6.0, 60.0),     # truck
    8: (8.0, 80.0),     # bus
}

LABEL_NAMES = {
    1: "pedestrian", 2: "bicycle", 3: "motorcycle",
    4: "car", 5: "e-scooter", 6: "van", 7: "truck", 8: "bus",
}


def run_detection(
    region: str = "brussels",
    date: str | None = None,
    prob_thresh: float | None = None,
    time_horizon_s: float | None = None,
    time_steps: int | None = None,
    max_hours: int | None = None,
) -> pd.DataFrame:
    
    global_config = load_config()
    bhatt_cfg = global_config.get("bhattacharyya", {})
    post_filters = global_config.get("post_filters", {})
    
    prob_thresh = prob_thresh if prob_thresh is not None else bhatt_cfg.get("env_prob_thresh", 0.25)
    time_horizon_s = time_horizon_s if time_horizon_s is not None else bhatt_cfg.get("env_time_horizon_s", 1.2)
    time_steps = time_steps if time_steps is not None else bhatt_cfg.get("env_time_steps", 6)
    cov_epsilon = bhatt_cfg.get("env_cov_epsilon", 1e-6)
    uncertainty_growth = bhatt_cfg.get("uncertainty_growth", 0.1)

    min_closing_speed = post_filters.get("min_closing_speed", 1.0)
    max_ttc = post_filters.get("max_ttc", 3.0)
    use_ttc_filter = post_filters.get("use_ttc_filter", True)
    use_angle_filter = post_filters.get("use_angle_filter", True)
    parallel_angle_tolerance = post_filters.get("parallel_angle_tolerance", 15.0)

    print("\n" + "=" * 70)
    print(f"BHATTACHARYYA ENVELOPE DETECTION (Unified) - {region.upper()} - {date}")
    print("=" * 70)
    print(f"Threshold (BC²): {prob_thresh}")
    print(f"Time horizon   : {time_horizon_s}s  ({time_steps} steps)")
    if max_hours:
        print(f"Smoke mode     : max_hours={max_hours}")

    input_dir = brussels_data_dir()
    df = load_data(
        input_dir,
        date,
        date,
        dtypes=global_config["data"]["dtypes"],
        max_hours=max_hours,
    )

    if df.empty:
        print("No source data found - writing empty detections.")
        return pd.DataFrame()

    df = df.reset_index(drop=True)

    print(f"\n \N{LONG RIGHTWARDS ARROW} Applying preprocessing filters...")
    df = apply_preprocessing_filters(df, region=region, config=global_config)

    print(f"\n \N{LONG RIGHTWARDS ARROW} Generating nearby pairs in-memory...")
    pair_config = global_config.copy()
    pair_config["filters"] = global_config["filters"].copy()
    
    # We want ALL nearby pairs to run envelope math on, so we bypass SSM TTC/speed cuts during pair generation
    pair_config["filters"]["max_ttc"] = 999.0
    pair_config["filters"]["min_closing_speed"] = -999.0

    base_pairs = find_all_nearby_pairs(df, pair_config)

    if base_pairs.empty:
        print("No pairs found - writing empty detections.")
        return pd.DataFrame()

    print(f"  \N{CHECK MARK} Generated {len(base_pairs):,} nearby pairs")

    rename_map = {}
    for col in base_pairs.columns:
        if col.endswith("1") and not col.endswith("_obj1"):
            rename_map[col] = col[:-1] + "_obj1"
        elif col.endswith("2") and not col.endswith("_obj2"):
            rename_map[col] = col[:-1] + "_obj2"
    pairs = base_pairs.rename(columns=rename_map)

    # Ensure required columns
    required = ["id_obj1", "id_obj2", "timestamp", "pos_x_obj1", "pos_y_obj1",
                "pos_x_obj2", "pos_y_obj2", "vel_x_obj1", "vel_y_obj1",
                "vel_x_obj2", "vel_y_obj2", "size_x_obj1", "size_y_obj1", 
                "size_x_obj2", "size_y_obj2", "yaw_obj1", "yaw_obj2", 
                "label_obj1", "label_obj2"]

    for col in required:
        if col not in pairs.columns:
            if "size" in col:
                pairs[col] = 1.8
            elif "yaw" in col:
                pairs[col] = 0.0
            elif "label" in col:
                pairs[col] = 4
            else:
                pairs[col] = 0.0

    for suffix in ["obj1", "obj2"]:
        if f"vel_{suffix}" not in pairs.columns:
            vel_x = pairs.get(f"vel_x_{suffix}", pd.Series(0.0, index=pairs.index))
            vel_y = pairs.get(f"vel_y_{suffix}", pd.Series(0.0, index=pairs.index))
            pairs[f"vel_{suffix}"] = np.sqrt(vel_x**2 + vel_y**2)

    print(f"\n \N{LONG RIGHTWARDS ARROW} Computing safety envelopes & BC² Overlap Probability...")
    detections = get_envelope_near_misses(
        pairs,
        prob_thresh=prob_thresh,
        time_horizon_s=time_horizon_s,
        time_steps=time_steps,
        uncertainty_growth_per_s=uncertainty_growth,
        cov_epsilon=cov_epsilon,
    )

    if not detections.empty:
        print(f"\n \N{LONG RIGHTWARDS ARROW} Applying post-processing filters (Approach Vector, Size Sanity, Deduplication)...")
        initial_len = len(detections)

        # 1. Approach Vector and TTC Filter
        dx = detections["pos_x_obj2"] - detections["pos_x_obj1"]
        dy = detections["pos_y_obj2"] - detections["pos_y_obj1"]
        dvx = detections["vel_x_obj1"] - detections["vel_x_obj2"]
        dvy = detections["vel_y_obj1"] - detections["vel_y_obj2"]
        dist = np.maximum(detections.get("rel_dist", np.sqrt(dx**2 + dy**2)), 1.0)
        closing_speed = (dvx * dx + dvy * dy) / dist
        
        if use_ttc_filter:
            ttc = dist / np.maximum(closing_speed, 0.01)
            approach_mask = (closing_speed > min_closing_speed) & (ttc < max_ttc)
            detections = detections[approach_mask].copy()
            print(f"  [Approach Vector & TTC Filter] Dropped {initial_len - len(detections)} non-converging artefacts.")
        else:
            approach_mask = closing_speed > 0.0
            detections = detections[approach_mask].copy()
            print(f"  [Approach Vector] Dropped {initial_len - len(detections)} non-converging artefacts.")

        if use_angle_filter and not detections.empty:
            len_before = len(detections)
            angle1 = np.arctan2(detections["vel_y_obj1"], detections["vel_x_obj1"])
            angle2 = np.arctan2(detections["vel_y_obj2"], detections["vel_x_obj2"])
            angle_diff = np.abs(np.degrees(angle1 - angle2))
            angle_diff = np.where(angle_diff > 180, 360 - angle_diff, angle_diff)
            
            is_parallel = (angle_diff < parallel_angle_tolerance) | (angle_diff > 180 - parallel_angle_tolerance)
            detections = detections[~is_parallel].copy()
            print(f"  [Collision Angle] Dropped {len_before - len(detections)} safe parallel vehicles.")
            
        # 2. Size Sanity Filter
        if not detections.empty:
            len_before = len(detections)
            def _ok(label: int, sx: float, sy: float) -> bool:
                lo, hi = LABEL_AREA_BOUNDS.get(int(label), (0.0, 999.0))
                area = float(sx) * float(sy)
                return lo <= area <= hi

            size_mask = detections.apply(
                lambda r: _ok(r["label_obj1"], r["size_x_obj1"], r["size_y_obj1"]) and 
                          _ok(r["label_obj2"], r["size_x_obj2"], r["size_y_obj2"]),
                axis=1
            )
            detections = detections[size_mask].copy()
            print(f"  [Size Sanity] Dropped {len_before - len(detections)} implausible ghost tracks.")

        # 3. Temporal Deduplication (Max BC Score per Pair)
        if not detections.empty:
            len_before = len(detections)
            idx_max = detections.groupby("pair_id")["bc_overlap_prob"].idxmax()
            detections = detections.loc[idx_max].copy()
            print(f"  [Temporal Dedup] Collapsed {len_before} frames into {len(detections)} unique events.")

    print("\n" + "=" * 70)
    print(f"DETECTION RESULTS - {date}")
    print("=" * 70)
    n = len(detections)
    n_unique = detections["pair_id"].nunique() if not detections.empty else 0
    print(f"Total detection rows   : {n:,}")
    print(f"Unique conflicting pairs: {n_unique:,}")

    if not detections.empty:
        print("\nTop 10 Detections (by BC² overlap probability):")
        top = detections.nlargest(10, "bc_overlap_prob")[
            ["pair_id", "id_obj1", "id_obj2", "label_obj1", "label_obj2",
             "rel_dist", "rel_vel", "bc_overlap_prob", "bc_time_horizon", "bc_severity_score"]
        ].copy()
        top["label_obj1"] = top["label_obj1"].map(LABEL_NAMES).fillna(top["label_obj1"])
        top["label_obj2"] = top["label_obj2"].map(LABEL_NAMES).fillna(top["label_obj2"])
        print(top.to_string(index=False))

    output_base = REPO_ROOT / "results"
    results_dir = output_base / "bhattacharyya" / region / "lanes" / date
    results_dir.mkdir(parents=True, exist_ok=True)

    out_csv = results_dir / "detections.csv"
    detections.to_csv(out_csv, index=False)
    print(f"\n \N{CHECK MARK} Saved {n:,} detections → {out_csv}")

    summary = {
        "date": date,
        "region": region,
        "prob_thresh": float(prob_thresh),
        "time_horizon_s": float(time_horizon_s),
        "total_pairs_evaluated": int(len(pairs)),
        "total_detection_rows": int(n),
        "unique_conflicting_pairs": int(n_unique),
    }
    if not detections.empty:
        summary["top_bc_score"] = float(detections["bc_overlap_prob"].max())
        summary["mean_bc_score"] = float(detections["bc_overlap_prob"].mean())

    out_yaml = results_dir / "summary.yaml"
    with out_yaml.open("w") as f:
        yaml.dump(summary, f, default_flow_style=False)
    print(f"\n\N{CHECK MARK} Saved summary → {out_yaml}")

    return detections


def main() -> None:
    parser = argparse.ArgumentParser(description="Bhattacharyya Envelope Near-Miss Detection")
    parser.add_argument("--region", default="brussels")
    parser.add_argument("--date", required=True)
    parser.add_argument("--prob-thresh", type=float, default=None)
    parser.add_argument("--time-horizon", type=float, default=None)
    parser.add_argument("--time-steps", type=int, default=None)
    parser.add_argument("--max-hours", type=int, default=None)
    args = parser.parse_args()

    run_detection(
        region=args.region,
        date=args.date,
        prob_thresh=args.prob_thresh,
        time_horizon_s=args.time_horizon,
        time_steps=args.time_steps,
        max_hours=args.max_hours,
    )

if __name__ == "__main__":
    main()
