# Unsupervised IRSM Tuning Report

Last updated on: 2026-07-17

This file summarizes the current status of unsupervised IRSM tuning for the Brussels lane workflow.

## Scope

- Isolation Forest
- Gaussian anomaly detection
- lightweight ensemble ranking

## Current Readable Outcome

From the saved tuning artifacts currently present in the repository:

- Validation Precision@10: `0.100`
- Validation Recall@10: `1.000`
- Test Precision@10: `0.100`
- Test Recall@10: `1.000`

## Interpretation

The unsupervised path is still useful, but it is not precise enough to stand alone as the final near-miss ranking layer.

It works best as:

- an anomaly-screening baseline
- a comparison surface against M-DRAC
- an input to later fusion or supervised ranking

## Practical Guidance

Use the unsupervised pipeline when you want to:

- inspect rare-looking interactions in feature space
- generate candidate lists without relying on labels
- build ensemble inputs for later ranking experiments

Do not present unsupervised anomaly scores alone as the clean production shortlist.
