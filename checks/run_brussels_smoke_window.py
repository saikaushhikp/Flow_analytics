"""
Run bounded Brussels M-DRAC smoke windows for multiple dates.

This keeps the operational validation reproducible without loading a full day
into memory. Logs are written under results/mdrac/brussels/smoke_logs by default.

Example:
    python checks/run_brussels_smoke_window.py --start-date 2025-06-01 --end-date 2025-06-07 --max-hours 1
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils import brussels_data_dir, output_root


def _date_range(start_date: str, end_date: str):
    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


def _run_pipeline(
    pipeline: str,
    date: str,
    start_time: str,
    data_dir: Path,
    output_dir: Path,
    max_hours: int,
    log_dir: Path,
) -> Path:
    script = REPO_ROOT / "regions" / "brussels" / f"{pipeline}_main.py"
    log_path = log_dir / f"{pipeline}_{date}_h{max_hours}.log"
    command = [
        sys.executable,
        str(script),
        "--start-date",
        date,
        "--start-time",
        start_time,
        "--end-date",
        date,
        "--data-dir",
        str(data_dir),
        "--output-dir",
        str(output_dir),
        "--max-hours",
        str(max_hours),
    ]

    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write("$ " + " ".join(command) + "\n\n")
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

    if result.returncode != 0:
        raise RuntimeError(f"{pipeline} smoke run failed for {date}; see {log_path}")
    return log_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded Brussels M-DRAC smoke windows")
    parser.add_argument("--start-date", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date, YYYY-MM-DD")
    parser.add_argument("--start-time", default="00", help="Start hour on the start date (HH or HH:MM)")
    parser.add_argument("--max-hours", type=int, default=1, help="Hourly folders per day to process")
    parser.add_argument("--data-dir", type=Path, default=brussels_data_dir(), help="Brussels parquet root")
    parser.add_argument("--output-dir", type=Path, default=output_root() / "mdrac", help="M-DRAC output root")
    parser.add_argument(
        "--pipelines",
        nargs="+",
        choices=["lane", "crosswalk"],
        default=["lane", "crosswalk"],
        help="Pipelines to run",
    )
    args = parser.parse_args()

    if args.max_hours < 1:
        raise ValueError("--max-hours must be >= 1")

    log_dir = args.output_dir / "brussels" / "smoke_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    for date in _date_range(args.start_date, args.end_date):
        for pipeline in args.pipelines:
            log_path = _run_pipeline(
                pipeline=pipeline,
                date=date,
                start_time=args.start_time,
                data_dir=args.data_dir,
                output_dir=args.output_dir,
                max_hours=args.max_hours,
                log_dir=log_dir,
            )
            print(f"{pipeline} {date}: ok ({log_path})")


if __name__ == "__main__":
    main()
