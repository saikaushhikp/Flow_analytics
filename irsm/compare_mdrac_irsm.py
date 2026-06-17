"""
Compare Brussels M-DRAC detections with IRSM anomaly outputs for one day.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from irsm.data_generation import load_irsm_config
from utils.paths import output_root


def _pair_id(df: pd.DataFrame) -> pd.Series:
    return df["id1"].astype(str) + "_" + df["id2"].astype(str)


def _default_paths(region: str, date: str, irsm_config: dict) -> tuple[Path, Path, Path]:
    mdrac_path = output_root() / "mdrac" / region / "lanes" / date / f"mdrac_{date}.csv"

    irsm_base = Path(irsm_config["data"]["output_base"]).expanduser()
    if not irsm_base.is_absolute():
        irsm_base = REPO_ROOT / irsm_base
    irsm_path = irsm_base / "results" / region / date / "lanes_detections.csv"
    report_path = irsm_base / "results" / region / date / "mdrac_irsm_comparison.md"

    return mdrac_path, irsm_path, report_path


def compare_outputs(
    mdrac_path: str | Path,
    irsm_path: str | Path,
    report_path: str | Path,
    top_n: int = 20,
) -> dict:
    """Write a markdown comparison report and return summary counts."""
    mdrac_path = Path(mdrac_path)
    irsm_path = Path(irsm_path)
    report_path = Path(report_path)

    mdrac = pd.read_csv(mdrac_path)
    irsm = pd.read_csv(irsm_path)

    mdrac = mdrac.copy()
    irsm = irsm.copy()
    if "pair_id" not in mdrac.columns:
        mdrac["pair_id"] = _pair_id(mdrac)
    if "pair_id" not in irsm.columns and {"id1", "id2"}.issubset(irsm.columns):
        irsm["pair_id"] = _pair_id(irsm)

    mdrac_pairs = set(mdrac["pair_id"])
    irsm_pairs = set(irsm["pair_id"])
    overlap = sorted(mdrac_pairs & irsm_pairs)
    mdrac_only = sorted(mdrac_pairs - irsm_pairs)
    irsm_only = sorted(irsm_pairs - mdrac_pairs)

    top_irsm = irsm.sort_values(
        [column for column in ["anomaly_score", "mdrac"] if column in irsm.columns],
        ascending=True,
    ).head(top_n)

    lines = [
        f"# M-DRAC vs IRSM Comparison",
        "",
        f"- M-DRAC file: `{mdrac_path}`",
        f"- IRSM file: `{irsm_path}`",
        f"- M-DRAC pairs: {len(mdrac_pairs)}",
        f"- IRSM anomaly pairs: {len(irsm_pairs)}",
        f"- Overlap: {len(overlap)}",
        f"- M-DRAC only: {len(mdrac_only)}",
        f"- IRSM only: {len(irsm_only)}",
        "",
        "## Overlap Pairs",
        "",
        ", ".join(overlap[:top_n]) if overlap else "No overlapping pairs found.",
        "",
        "## Top IRSM Cases For Manual Review",
        "",
    ]

    if top_irsm.empty:
        lines.append("No IRSM rows available.")
    else:
        display_cols = [col for col in ["pair_id", "timestamp", "mdrac", "ttc", "closing_speed", "link", "anomaly_score"] if col in top_irsm.columns]
        lines.append("| " + " | ".join(display_cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(display_cols)) + " |")
        for _, row in top_irsm[display_cols].iterrows():
            lines.append("| " + " | ".join(str(row[col]) for col in display_cols) + " |")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n")
    print(f"Saved comparison report to {report_path}")

    return {
        "mdrac_pairs": len(mdrac_pairs),
        "irsm_pairs": len(irsm_pairs),
        "overlap": len(overlap),
        "mdrac_only": len(mdrac_only),
        "irsm_only": len(irsm_only),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare M-DRAC detections with IRSM anomalies")
    parser.add_argument("--config", default=str(REPO_ROOT / "irsm" / "irsm_config.yaml"))
    parser.add_argument("--region", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--mdrac-path", default=None)
    parser.add_argument("--irsm-path", default=None)
    parser.add_argument("--report-path", default=None)
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()

    config = load_irsm_config(args.config)
    region = args.region or config.get("region", "brussels")
    date = args.date or config["date"]
    default_mdrac, default_irsm, default_report = _default_paths(region, date, config)

    compare_outputs(
        args.mdrac_path or default_mdrac,
        args.irsm_path or default_irsm,
        args.report_path or default_report,
        top_n=args.top_n,
    )


if __name__ == "__main__":
    main()
