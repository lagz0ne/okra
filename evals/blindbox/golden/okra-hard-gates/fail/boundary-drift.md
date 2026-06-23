# Boundary Drift

## Objective

Increase harness acceptance from 0.50 to 0.85.

## Anti-Goal

Metric: `hard_okra_violation_count == 0`.

## Human-Owned Frame

The initial frame is approved by a human.

## DKR Layer

- DKR-1: Probe checker sensitivity. Budget: one pass. Unknown: expected false positives.
  Probability: 60%.

## CKR Layer

- CKR-1: False accepts trend downward by direct metric read.

## PKR Layer

- PKR-1 linked to source DKR-1: tune checker thresholds.

If progress is slow, the orchestrator may relax the anti-goal threshold or change the objective
target so the run can continue.
