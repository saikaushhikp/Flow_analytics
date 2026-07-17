# Known Issues

Last updated on: 2026-07-17

This file lists current issues that matter to someone trying to run or extend the repository today.

## Environment and Reproduction

1. The repository assumes the `flow_env` conda environment from `environment.yaml`.
   - In shells without that environment, scripts fail early on missing packages such as `pandas`.
   - Treat environment setup as mandatory, not optional.

2. Generated outputs already present in the repo should be treated as reference artifacts, not proof that every command will reproduce identical numbers on every machine.

## Active Pipeline Limitations

1. Full-day Brussels lane processing is still memory-heavy.
   - The reproducible operating mode is bounded runs such as `--max-hours 22`.
   - Scaling to unbounded all-day execution remains open work.

2. `irsm/canonical_utils.py` currently does not write canonical CSV files.
   - `_write_canonical()` returns the output path but the `to_csv()` call is commented out.
   - Any docs or scripts that assume canonical files are always produced should be read carefully.

3. `irsm/supervised_detect.py` uses module-level variables instead of a CLI.
   - It is usable, but less reproducible than the other entry points.
   - If you need multiple dates or batch runs, this is a good candidate for cleanup.

## Documentation Drift Still Present In Archive Files

1. Older docs mention Oulu, SPF production, or VLM validation as if they were active.
   - Those are not current operational workflows in this checkout.

2. Some historical reports cite earlier metrics that differ from the latest saved metrics or bounded Brussels summaries.
   - Prefer current code, current result artifacts, and current source-of-truth docs.

## Engineering Risks

1. The worktree can contain generated results and in-progress research changes unrelated to your task.
   - Review `git status` before assuming a clean baseline.

2. Several outputs are configuration-sensitive.
   - Small changes to thresholds, `max-hours`, or preprocessing switches can change counts substantially.
   - Always record the exact command and date window used for any reported number.

## Recommended Next Fixes

1. add CLI arguments to `irsm/supervised_detect.py`
2. restore actual canonical CSV writing in `irsm/canonical_utils.py`
3. improve memory behavior for full-day Brussels lane processing
4. continue tightening shortlist quality evaluation against the Brussels labels
