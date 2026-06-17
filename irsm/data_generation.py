"""
IRSM lane risk-vector data generation.

Active scope: Brussels lane interactions. Oulu and crosswalk variants are
intentionally deferred in the current implementation plan.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from irsm.risk_vector import extract_risk_vectors, get_feature_names
from regions.brussels.zones import get_lane_zones
from ssm.utils import assign_zones_to_vehicles, filter_same_lane, find_all_nearby_pairs, load_config
from utils import brussels_data_dir, load_data
from utils.irsm_preprocessing import apply_preprocessing_filters
from utils.paths import default_config_path


IRSM_OUTPUT_COLUMNS = ["pair_id", "timestamp", "label1", "label2", "link", "same_zone"] + get_feature_names()


def load_irsm_config(config_path: str | Path | None = None) -> dict:
    """Load IRSM YAML config."""
    path = Path(config_path) if config_path else REPO_ROOT / "irsm" / "irsm_config.yaml"
    with path.open("r") as f:
        return yaml.safe_load(f)


def _resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def _pair_config(main_config: dict, irsm_config: dict) -> dict:
    """Derive SSM pair-generation config from the broader IRSM thresholds."""
    config = main_config.copy()
    config["filters"] = main_config["filters"].copy()
    pair_cfg = irsm_config["pair_generation"]

    config["filters"]["max_distance"] = pair_cfg["max_distance"]
    config["filters"]["max_lateral_distance"] = pair_cfg["max_lateral"]
    config["filters"]["max_ttc"] = pair_cfg["max_ttc"]
    config["filters"]["min_closing_speed"] = pair_cfg["min_closing_speed"]

    return config


def generate_risk_vectors(
    region: str = "brussels",
    date: str | None = None,
    input_dir: str | Path | None = None,
    output_base: str | Path | None = None,
    irsm_config: dict | None = None,
    main_config: dict | None = None,
    skip_preprocessing: bool = False,
    max_hours: int | None = None,
    sample_limit: int | None = None,
) -> pd.DataFrame:
    """Generate and save Brussels lane risk vectors."""
    irsm_config = irsm_config or load_irsm_config()
    main_config = main_config or load_config(str(default_config_path()))

    region = region or irsm_config.get("region", "brussels")
    if region != "brussels":
        raise NotImplementedError("IRSM data generation is currently enabled only for Brussels.")

    date = date or irsm_config["date"]
    input_dir = input_dir or irsm_config["data"].get("input_dir") or brussels_data_dir()
    output_base = output_base or irsm_config["data"].get("output_base", "irsm")
    output_base = _resolve_repo_path(output_base)

    print("\n" + "=" * 70)
    print(f"IRSM DATA GENERATION - {region.upper()} - {date}")
    print("=" * 70)
    print(f"Input: {input_dir}")
    print(f"Output base: {output_base}")
    if max_hours:
        print(f"Smoke mode: max_hours={max_hours}")
    if sample_limit:
        print(f"Smoke mode: sample_limit={sample_limit}")

    df = load_data(
        input_dir,
        date,
        date,
        dtypes=main_config["data"]["dtypes"],
        max_hours=max_hours,
        sample_limit=sample_limit,
    )
    if df.empty:
        print("No source data loaded; writing an empty lanes.csv.")
        risk_vectors = pd.DataFrame(columns=IRSM_OUTPUT_COLUMNS)
    else:
        df = df.reset_index(drop=True)
        if not skip_preprocessing:
            df = apply_preprocessing_filters(df, region=region, config=main_config)

        print("\nAssigning Brussels lane zones...")
        df = assign_zones_to_vehicles(df, get_lane_zones())
        df_lanes = df[df["zone"] != "unknown"].copy()
        print(f"Lane rows: {len(df_lanes):,}")

        if df_lanes.empty:
            risk_vectors = pd.DataFrame(columns=IRSM_OUTPUT_COLUMNS)
        else:
            pair_config = _pair_config(main_config, irsm_config)
            print("\nGenerating IRSM base pairs...")
            base_pairs = find_all_nearby_pairs(df_lanes, pair_config)

            if base_pairs.empty:
                risk_vectors = pd.DataFrame(columns=IRSM_OUTPUT_COLUMNS)
            else:
                print("\nApplying same-lane IRSM filter...")
                same_lane_pairs = filter_same_lane(
                    base_pairs,
                    irsm_config["pair_generation"]["max_lateral"],
                )
                risk_vectors = extract_risk_vectors(same_lane_pairs, region=region, config=irsm_config, traj_df=df_lanes)
                if risk_vectors.empty:
                    risk_vectors = pd.DataFrame(columns=IRSM_OUTPUT_COLUMNS)

    output_dir = output_base / "data" / region / date
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "lanes.csv"
    risk_vectors.to_csv(output_file, index=False)
    print(f"\nSaved {len(risk_vectors):,} IRSM risk vectors to {output_file}")

    return risk_vectors


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Brussels IRSM lane risk vectors")
    parser.add_argument("--config", default=str(REPO_ROOT / "irsm" / "irsm_config.yaml"))
    parser.add_argument("--main-config", default=str(default_config_path()))
    parser.add_argument("--region", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--input-dir", default=None)
    parser.add_argument("--output-base", default=None)
    parser.add_argument("--skip-preprocessing", action="store_true")
    parser.add_argument("--max-hours", type=int, default=None)
    parser.add_argument("--sample-limit", type=int, default=None)
    args = parser.parse_args()

    irsm_config = load_irsm_config(args.config)
    main_config = load_config(args.main_config)
    generate_risk_vectors(
        region=args.region or irsm_config.get("region", "brussels"),
        date=args.date or irsm_config.get("date"),
        input_dir=args.input_dir,
        output_base=args.output_base,
        irsm_config=irsm_config,
        main_config=main_config,
        skip_preprocessing=args.skip_preprocessing,
        max_hours=args.max_hours,
        sample_limit=args.sample_limit,
    )


if __name__ == "__main__":
    main()
