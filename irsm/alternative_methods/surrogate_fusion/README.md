# Surrogate Fusion

Last updated on: 2026-07-17

This experiment keeps M-DRAC as the front-end detector, then filters candidates with additional behavioral evidence.

## Rule Idea

Baseline candidate:

- `mdrac >= 3.0`

Filtered candidate:

- `mdrac >= 3.0`
- and at least one of:
  - strong follower braking
  - critical TTC

The point of this method is to cut obvious false positives where M-DRAC is high but the rest of the interaction does not look behaviorally urgent.

## Run

```bash
python irsm/alternative_methods/surrogate_fusion/surrogate_fusion.py
```

## Current Result

From `results/evaluation_metrics.json`:

- validation false positives: `45 -> 35`
- test false positives: `40 -> 32`
- test precision: `0.130 -> 0.135`
- test recall: `0.857 -> 0.714`

## Interpretation

This method is useful when the operational goal is false-positive reduction rather than raw recall. It is a practical post-filtering idea, but the current gain is modest and comes with recall loss.
