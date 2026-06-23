# Stale Steering

## Objective

Increase harness acceptance from 0.50 to 0.85.

## Anti-Goal

Metric: `hard_okra_violation_count == 0`.

## Human-Owned Frame

The human owns the frame and approval.

## DKR Layer

- DKR-1: Probe gate quality. Budget: one pass. Unknown: expected false accepts. Probability: 70%.

## CKR Layer

- CKR-1 linked to source DKR-1: reduce false accepts by direct metric read.

## PKR Layer

- PKR-1 linked to CKR-1 and source DKR-1: write gate descriptions.

## No-Cascade Rule

Task completion does not prove objective success. Use direct metric reads.

## Signal Handling

Too easy, too hard, stale, non-moving, and disconnected metrics become flags for the orchestrator.

The artifact has no check-in cadence and does not say how PKR work reports off-track signals before
an agent spends a long run on the wrong work.
