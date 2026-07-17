# Handoff and Current Documentation

Last updated on: 2026-07-17

This folder is the current Brussels-first handoff set for engineers who need to understand, run, and extend the maintained workflows in this repository.

## Current Source-of-Truth Documents

Read these first:

- [current_state.md](current_state.md): current project status, active scope, and results surface
- [known_issues.md](known_issues.md): current technical limitations and open issues
- [operational_runbook.md](operational_runbook.md): step-by-step reproduction and command reference
- [repository_inventory.md](repository_inventory.md): code map and artifact layout
- [accomplishments.md](accomplishments.md): what has already been stabilized and delivered
- [UPDATED_brussels_validation_summary.md](UPDATED_brussels_validation_summary.md): bounded Brussels validation summary

## Supporting Reports

The following files are still useful because they summarize the current tuning and validation surface:

- `mdrac_tuning_report.md`
- `unsupervised_tuning_report.md`
- `supervised_tuning_report.md`
- `UPDATED_brussels_validation_summary.md`

## How To Use This Folder

For a new technical teammate:

1. read `../README.md`
2. read `current_state.md`
3. check `known_issues.md`
4. follow `operational_runbook.md`
5. use the tuning reports when you need model-specific context

## Scope Reminder

The active operational scope of this checkout is Brussels-first:

- Brussels lane M-DRAC
- Brussels crosswalk M-DRAC
- Brussels IRSM lane generation and scoring
- Brussels Bhattacharyya lane detection
- replayable plots, GIFs, comparison reports, and heatmaps

Anything outside that should be treated as historical, deferred, or experimental unless the code and current docs say otherwise.
