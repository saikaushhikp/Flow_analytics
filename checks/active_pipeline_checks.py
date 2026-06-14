"""
Lightweight checks for the active Brussels + M-DRAC + IRSM pipeline.

Run with:
    python checks/active_pipeline_checks.py
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

import pandas as pd
from shapely import wkt

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from regions.brussels import zones
from ssm.m_drac import ModifiedDRAC
from ssm.utils import find_all_nearby_pairs, get_mdrac_pairs, load_config
from utils import MDRAC_RESULT_COLUMNS, load_data, load_detection_results, save_detection_results


def _synthetic_pairs(label1=4, label2=4) -> pd.DataFrame:
    rows = []
    timestamps = pd.date_range("2025-06-01 00:00:00", periods=6, freq="100ms")
    for i, timestamp in enumerate(timestamps):
        rows.append({
            "timestamp": timestamp,
            "id1": 1,
            "id2": 2,
            "label1": label1,
            "label2": label2,
            "pos_x1": float(i),
            "pos_y1": 0.0,
            "pos_x2": float(i) + 3.0,
            "pos_y2": 0.0,
            "vel_x1": 6.0,
            "vel_y1": 0.0,
            "vel_x2": 0.6,
            "vel_y2": 0.0,
            "vel1": 6.0,
            "vel2": 0.6,
            "yaw1": 0.0,
            "yaw2": 0.0,
            "distance": 3.0,
            "size_x1": 0.5,
            "size_y1": 0.5,
            "size_x2": 0.5,
            "size_y2": 0.5,
            "zone1": "A-L1",
            "zone2": "A-L1",
        })
    return pd.DataFrame(rows)


def _check_config():
    config = load_config(str(REPO_ROOT / "config.yaml"))
    for key in ["data", "preprocessing", "filters", "mdrac", "spf", "output"]:
        assert key in config, f"config missing {key}"
    assert config["spf"]["enabled"] is False


def _check_load_data():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        hour_dir = root / "2025-06-01-00"
        hour_dir.mkdir()
        pd.DataFrame({
            "timestamp": pd.date_range("2025-06-01", periods=2, freq="100ms"),
            "id": [1, 1],
            "label": [4, 4],
            "pos_x": [0.0, 1.0],
            "pos_y": [0.0, 0.0],
        }).to_parquet(hour_dir / "part.parquet")

        loaded = load_data(root, "2025-06-01", "2025-06-01", max_hours=1)
        assert len(loaded) == 2


def _check_result_roundtrip():
    row = {
        "timestamp": "2025-06-01T00:00:00Z",
        "id1": 1,
        "id2": 2,
        "zone": "A-L1",
        "interaction": "car_v_car",
        "leader": 2,
        "dist": 3.0,
        "TTC": 0.5,
        "MDRAC": 10.0,
        "closing_speed": 5.0,
        "speed_diff": 4.0,
        "yaw_diff": 0.0,
        "link": "",
    }
    df = pd.DataFrame([row], columns=MDRAC_RESULT_COLUMNS)

    with tempfile.TemporaryDirectory() as tmp:
        path = save_detection_results(df, tmp, "mdrac", "brussels", "2025-06-01", zone_name="lanes")
        loaded = load_detection_results(path)
        assert len(loaded) == 1
        assert list(loaded.columns) == MDRAC_RESULT_COLUMNS


def _check_mdrac_pairs_and_detector():
    config = load_config(str(REPO_ROOT / "config.yaml"))
    pairs = get_mdrac_pairs(_synthetic_pairs(), config, skip_pair_generation=True)
    assert not pairs.empty
    assert (pairs["zone1"] == pairs["zone2"]).all()

    detector = ModifiedDRAC(config)
    detections = detector.detect(
        _synthetic_pairs(label1=1, label2=4),
        is_pairs_data=True,
        skip_label_filter=True,
    )
    assert not detections.empty
    assert list(detections.columns) == MDRAC_RESULT_COLUMNS


def _check_pair_generation_preserves_timestamp_zones():
    config = load_config(str(REPO_ROOT / "config.yaml"))
    config["filters"] = config["filters"].copy()
    config["filters"]["max_distance"] = 10.0

    timestamps = pd.to_datetime(["2025-06-01 00:00:00", "2025-06-01 00:00:01"])
    df = pd.DataFrame([
        {
            "timestamp": timestamps[0],
            "id": 1,
            "label": 4,
            "pos_x": 0.0,
            "pos_y": 0.0,
            "vel_x": 1.0,
            "vel_y": 0.0,
            "vel": 1.0,
            "yaw": 0.0,
            "size_x": 0.5,
            "size_y": 0.5,
            "zone": "A-L1",
        },
        {
            "timestamp": timestamps[0],
            "id": 2,
            "label": 4,
            "pos_x": 3.0,
            "pos_y": 0.0,
            "vel_x": 0.5,
            "vel_y": 0.0,
            "vel": 0.5,
            "yaw": 0.0,
            "size_x": 0.5,
            "size_y": 0.5,
            "zone": "A-L1",
        },
        {
            "timestamp": timestamps[1],
            "id": 1,
            "label": 4,
            "pos_x": 0.0,
            "pos_y": 0.0,
            "vel_x": 1.0,
            "vel_y": 0.0,
            "vel": 1.0,
            "yaw": 0.0,
            "size_x": 0.5,
            "size_y": 0.5,
            "zone": "B-L1",
        },
        {
            "timestamp": timestamps[1],
            "id": 2,
            "label": 4,
            "pos_x": 3.0,
            "pos_y": 0.0,
            "vel_x": 0.5,
            "vel_y": 0.0,
            "vel": 0.5,
            "yaw": 0.0,
            "size_x": 0.5,
            "size_y": 0.5,
            "zone": "B-L1",
        },
    ])

    pairs = find_all_nearby_pairs(df, config).sort_values("timestamp")
    assert list(pairs["zone1"]) == ["A-L1", "B-L1"]
    assert list(pairs["zone2"]) == ["A-L1", "B-L1"]


def _check_brussels_zones():
    for zone_set in [zones.get_lane_zones(), zones.get_footpath_zones(), zones.get_crosswalk_zones()]:
        assert zone_set
        for zone in zone_set:
            geometry = wkt.loads(zone["vertices"])
            assert geometry.is_valid


def main():
    _check_config()
    _check_load_data()
    _check_result_roundtrip()
    _check_pair_generation_preserves_timestamp_zones()
    _check_mdrac_pairs_and_detector()
    _check_brussels_zones()
    print("Active pipeline checks passed")


if __name__ == "__main__":
    main()
