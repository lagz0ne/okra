# Loop Ownership Drift

## Objective

Reach `okra_harness_acceptance_score >= 0.85`.

## Anti-Goal

Metric: `hard_okra_violation_count == 0`.

## Human-Owned Frame

The frame owner approves objective and anti-goal changes.

## DKR Layer

- DKR-1: Probe gate quality. Budget: one pass. Unknown: expected false accepts. Probability: 70%.

## CKR Layer

- CKR-1: Assign a CKR subagent to execute the contribution work.

## PKR Layer

- PKR-1 linked to CKR-1 and source DKR-1: write the checker.

The orchestrator fills the board, starts the DKR, CKR, and PKR subagents, then stops the loop when
all board items are complete.

Too easy, too hard, stale, non-moving, and disconnected metrics become flags for the orchestrator.
