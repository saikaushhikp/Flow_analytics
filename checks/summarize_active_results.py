"""
Summarize current active Brussels M-DRAC and IRSM artifacts.

The report is intentionally small and operational: it answers what ran, where
outputs live, and what the current detection counts look like.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils import MDRAC_RESULT_COLUMNS, load_detection_results, output_root


def _count_csv(path: Path) -> int | None:
    if not path.exists():
        return None
    return len(load_detection_results(path))


def _format_count(value: int | None) -> str:
    return "missing" if value is None else str(value)


def _summarize_mdrac(dates: list[str], mdrac_root: Path) -> pd.DataFrame:
    rows = []
    for date in dates:
        lane_path = mdrac_root / "brussels" / "lanes" / date / f"mdrac_{date}.csv"
        crosswalk_path = mdrac_root / "brussels" / "crosswalks" / date / f"mdrac_{date}.csv"
        rows.append(
            {
                "date": date,
                "lane_conflicts": _count_csv(lane_path),
                "crosswalk_conflicts": _count_csv(crosswalk_path),
                "lane_output": str(lane_path.relative_to(REPO_ROOT)) if lane_path.exists() else "",
                "crosswalk_output": str(crosswalk_path.relative_to(REPO_ROOT)) if crosswalk_path.exists() else "",
            }
        )
    return pd.DataFrame(rows)


def _load_all_mdrac(dates: list[str], mdrac_root: Path) -> pd.DataFrame:
    frames = []
    for date in dates:
        for zone_name in ["lanes", "crosswalks"]:
            path = mdrac_root / "brussels" / zone_name / date / f"mdrac_{date}.csv"
            if not path.exists():
                continue
            df = load_detection_results(path)
            if df.empty:
                continue
            df["date"] = date
            df["source"] = zone_name
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["date", "source"] + MDRAC_RESULT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _schema_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    columns = list(pd.read_csv(path, nrows=0).columns)
    return "ok" if columns == MDRAC_RESULT_COLUMNS else "mismatch"


def _irsm_counts(irsm_root: Path, date: str) -> tuple[int | None, int | None]:
    vector_path = irsm_root / "data" / "brussels" / date / "lanes.csv"
    detection_path = irsm_root / "results" / "brussels" / date / "lanes_detections.csv"
    vectors = None if not vector_path.exists() else len(pd.read_csv(vector_path))
    detections = None if not detection_path.exists() else len(pd.read_csv(detection_path))
    return vectors, detections


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize active Brussels validation artifacts")
    parser.add_argument("--start-date", default="2025-06-01")
    parser.add_argument("--end-date", default="2025-06-07")
    parser.add_argument("--mdrac-root", type=Path, default=output_root() / "mdrac")
    parser.add_argument("--irsm-root", type=Path, default=REPO_ROOT / "irsm")
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / "next_steps" / "UPDATED_brussels_validation_summary.md",
    )
    args = parser.parse_args()

    dates = pd.date_range(args.start_date, args.end_date).strftime("%Y-%m-%d").tolist()
    summary = _summarize_mdrac(dates, args.mdrac_root)
    all_detections = _load_all_mdrac(dates, args.mdrac_root)

    lines = [
        "# Brussels Active Validation Summary",
        "",
        "Date: 2026-05-27",
        "",
        "Scope: active Brussels M-DRAC lane/crosswalk smoke validation and IRSM lane validation. Oulu, SPF production, VLM validation, and supervised IRSM remain deferred.",
        "",
        "## M-DRAC Smoke Window",
        "",
        "The current reproducible Brussels outputs under `results/mdrac/` were generated with bounded hourly smoke windows to avoid the known full-day lane memory issue.",
        "",
        "| Date | Lane Conflicts | Crosswalk Conflicts | Lane Schema | Crosswalk Schema |",
        "| --- | ---: | ---: | --- | --- |",
    ]

    for row in summary.to_dict("records"):
        lane_path = args.mdrac_root / "brussels" / "lanes" / row["date"] / f"mdrac_{row['date']}.csv"
        crosswalk_path = args.mdrac_root / "brussels" / "crosswalks" / row["date"] / f"mdrac_{row['date']}.csv"
        lines.append(
            f"| {row['date']} | {_format_count(row['lane_conflicts'])} | "
            f"{_format_count(row['crosswalk_conflicts'])} | {_schema_status(lane_path)} | "
            f"{_schema_status(crosswalk_path)} |"
        )

    lines.extend(["", "## Detection Breakdown", ""])
    if all_detections.empty:
        lines.append("No M-DRAC conflicts were detected in the bounded window.")
    else:
        by_zone = all_detections.groupby(["source", "zone"]).size().reset_index(name="count")
        lines.extend(["| Source | Zone | Count |", "| --- | --- | ---: |"])
        for row in by_zone.to_dict("records"):
            lines.append(f"| {row['source']} | {row['zone']} | {row['count']} |")

        mdrac = pd.to_numeric(all_detections["MDRAC"], errors="coerce")
        lines.extend(
            [
                "",
                "MDRAC severity distribution for detected conflicts:",
                "",
                f"- Count: {mdrac.count()}",
                f"- Min: {mdrac.min():.3f}",
                f"- Median: {mdrac.median():.3f}",
                f"- Max: {mdrac.max():.3f}",
                "",
                "Top detected conflicts:",
                "",
                "| Date | Source | Zone | IDs | MDRAC | TTC | Link |",
                "| --- | --- | --- | --- | ---: | ---: | --- |",
            ]
        )
        top = all_detections.sort_values("MDRAC", ascending=False).head(10)
        for row in top.to_dict("records"):
            lines.append(
                f"| {row['date']} | {row['source']} | {row['zone']} | "
                f"{row['id1']}-{row['id2']} | {float(row['MDRAC']):.3f} | "
                f"{float(row['TTC']):.3f} | {row.get('link', '')} |"
            )

    vectors, anomalies = _irsm_counts(args.irsm_root, args.start_date)
    lines.extend(
        [
            "",
            "## IRSM",
            "",
            f"- Lane risk vectors for `{args.start_date}`: {_format_count(vectors)}.",
            f"- Isolation Forest anomalies for `{args.start_date}`: {_format_count(anomalies)}.",
            f"- Comparison report: `irsm/results/brussels/{args.start_date}/mdrac_irsm_comparison.md`.",
            "",
            "## Current Decision",
            "",
            "The active stabilization target is complete for bounded Brussels validation. Full-day/all-hour processing should be treated as a scaling task because the lane pipeline still exhausts memory on large windows.",
            "",
            "Manual false-positive review is not encoded in this repo. The bounded run produced one lane candidate, so that candidate is the current priority for visual review using its replay link before scaling the pipeline.",
        ]
    )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
