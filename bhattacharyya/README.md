# Bhattacharyya Envelope Near-Miss Detection

Last updated on: 2026-07-17

This module implements a Bhattacharyya-coefficient-based near-miss detector for Brussels lane interactions.

The method models each object as a Gaussian safety envelope derived from:

- object size
- motion heading
- velocity magnitude
- object class

It then computes the analytical Bhattacharyya Coefficient (BC) overlap between two envelopes. The detector uses `BC^2` as the overlap probability proxy and flags pairs whose maximum projected overlap exceeds a threshold.

## What This Method Is

Relative to the other active methods in this repository:

- `M-DRAC` is a rule-based kinetic near-miss detector
- `IRSM` is a feature-space ranking pipeline
- `Bhattacharyya` is an envelope-overlap collision-probability style detector

The Bhattacharyya path is best understood as a geometry-and-uncertainty-driven alternative lane detector rather than a replacement for all M-DRAC or IRSM workflows.

## Main Entry Point

Run detection for a Brussels day:

```bash
conda run -n flow_env python bhattacharyya/detect.py --date 2025-06-01
```

Useful overrides:

```bash
conda run -n flow_env python bhattacharyya/detect.py \
  --date 2025-06-01 \
  --prob-thresh 0.50 \
  --time-horizon 1.2 \
  --time-steps 6 \
  --max-hours 22
```

CLI surface:

- `--region`
- `--date` (required)
- `--prob-thresh`
- `--time-horizon`
- `--time-steps`
- `--max-hours`

## Pipeline Summary

`bhattacharyya/detect.py` does the following:

1. loads Brussels trajectory data through the shared repository loader
2. applies the shared Brussels preprocessing chain
3. generates nearby in-memory pairs
4. computes per-object safety envelopes
5. projects those envelopes through a short future horizon
6. computes `BC^2` overlap scores
7. applies post-filters for approach direction, TTC, collision angle, size sanity, and temporal deduplication
8. writes detections and a summary file

## Outputs

Outputs are written to:

```text
results/bhattacharyya/brussels/lanes/{date}/detections.csv
results/bhattacharyya/brussels/lanes/{date}/summary.yaml
```

The detector currently operates on Brussels lane interactions.

## Important Configuration

There are two configuration surfaces involved:

1. `config.yaml`
   - shared data-loading and preprocessing settings
   - `bhattacharyya` parameters used by `detect.py`
   - post-filters such as TTC and angle screening

2. `bhattacharyya/bhattacharyya_config.yaml`
   - repository-local method configuration reference
   - useful for documenting expected parameters and defaults

The runtime code currently reads the shared `config.yaml` path through `load_config()`, so treat that as the active source during execution.

## Core Files

- `bhattacharyya/detect.py`
  - day-level runner
  - shared preprocessing + pair generation + output writing

- `bhattacharyya/envelope.py`
  - safety envelope construction
  - vectorized Bhattacharyya overlap computation
  - future-horizon scoring and final near-miss extraction

- `bhattacharyya/bhattacharyya_config.yaml`
  - method-specific config reference

## Method Notes

- envelope size expands with speed and object type
- vulnerable road users and two-wheelers receive different envelope scaling
- pairs are projected through a future horizon before selecting the maximum overlap
- temporal deduplication keeps the strongest BC event per pair

## Current Position In The Repository

This method is present as an active alternative detector in the codebase, alongside M-DRAC and IRSM. It is Brussels-focused and lane-focused in its current form, and it should be documented and discussed as part of the repository’s current near-miss-method set.
