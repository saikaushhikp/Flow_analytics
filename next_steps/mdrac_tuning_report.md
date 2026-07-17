# M-DRAC Tuning Report

Last updated on: 2026-07-17

This file summarizes the current M-DRAC tuning posture for the Brussels-first workflow.

## Scope

- region: Brussels
- active surfaces: lanes and crosswalks
- reference benchmark: `brussels_june_in.csv`
- practical objective: improve top-k near-miss shortlist quality while keeping detections explainable and reviewable

## Current Status

The repository does not currently carry one final “best tuned” M-DRAC parameter sheet beyond:

- the active runtime settings in `config.yaml`
- the detector logic in `ssm/m_drac.py`
- the bounded validation outputs under `results/mdrac/brussels/`

What has already improved relative to earlier baselines:

- separate lane and crosswalk handling
- crosswalk-specific averaging behavior
- follower-response logic strengthened with direct braking-response evidence
- stable bounded execution for Brussels smoke validation

## Where Tuning Lives

- `config.yaml`
- `ssm/m_drac.py`
- `ssm/utils.py`
- `irsm/tune_mdrac.py`

## Recommended Tuning Workflow

1. run bounded Brussels smoke windows
2. compare detection counts and top-ranked conflicts
3. inspect replay links for false-positive patterns
4. change one parameter group at a time
5. regenerate `next_steps/UPDATED_brussels_validation_summary.md`

## Current Limitation

Lane tuning across large windows remains memory-sensitive. Use bounded windows unless you are explicitly working on scaling or orchestration.
