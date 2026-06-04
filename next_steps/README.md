# PREM Handoff: Next Steps

Review date: 2026-05-21  
Repository reviewed: `/home/kaushik/Kezual/Flow_analytics`

This folder is a practical handoff for taking over the PREM near-miss detection repository. It summarizes what the former employee built, what currently works conceptually, what is broken or stale in the checkout, and the recommended order for continuing the work.

## Documents

- [repository_inventory.md](repository_inventory.md): repository layout, important files, notebooks, generated outputs, and where each subsystem lives.
- [current_state.md](current_state.md): what has been accomplished, current pipeline design, and available generated results.
- [known_issues.md](known_issues.md): blockers, code/documentation drift, and likely runtime failures found during review.
- [implementation_plan.md](implementation_plan.md): prioritized plan to make the project runnable, validated, and ready for scale-up.
- [operational_runbook.md](operational_runbook.md): setup and run commands once the blockers are fixed.

## Short Version

The core business direction is clear: PREM analyzes traffic object trajectories and detects near-miss events using M-DRAC, with additional experimental work around IRSM, SPF, VLM validation, and heatmaps.

The strongest completed path is rule-based M-DRAC for lane and crosswalk detections. There are already result CSVs and plots for Brussels and Oulu under `results/`.

The repository is not currently cleanly runnable from this checkout without fixes. The main blockers are missing `utils/data_loader.py`, missing `flow_env` in the local conda installation, hardcoded `/home/ubuntu/prem` paths, a config mismatch that breaks SPF, VLM code referencing removed variables/import paths, IRSM docs pointing to missing scripts, and Oulu crosswalk code that still contains duplicated old workaround logic.

Recommended immediate focus:

1. Repair imports/environment/path configuration.
2. Smoke-test one Brussels lane day and one Brussels crosswalk day.
3. Port the clean Brussels crosswalk `skip_label_filter` flow to Oulu crosswalk.
4. Restore or rewrite the missing IRSM data-generation scripts.
5. Add focused tests around pair generation, M-DRAC output schema, VLM validation parsing, and result saving/loading.

