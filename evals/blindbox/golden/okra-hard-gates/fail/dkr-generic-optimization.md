# DKR As Generic Optimization

## Objective

Build an OKRA blindbox harness with `okra_harness_acceptance_score >= 0.85` across Codex and Claude.

## Anti-Goal

Metric: `hard_okra_violation_count_in_accepted_runs == 0`.

Type: tripwire. Human approval is required to change this threshold.

## Human-Owned Frame

The human owns the objective, anti-goal, thresholds, metric definitions, and action envelope. The
orchestrator can propose changes but cannot ratify or apply them.

## Loop Ownership

The orchestrator owns objective checks, check-ins, the OKR board, and subagent steering until the
objective metric reaches target. It does not stop because PKRs, tasks, or board items are complete.

Subagents do executable work only for DKR and PKR. CKR is measurable contribution context, not a
worker task or dispatched work.

## DKR Layer

- DKR-1: Optimize the harness process. Budget: one design pass. Unknown: what improvements are
  useful. Probability: 70%.
- DKR-2: Improve the eval approach. Budget: one design pass. Unknown: what approach is best.
  Probability: 65%.

Each DKR must produce a learning checkpoint before any CKR or PKR is promoted from candidate status:
evidence collected, questions answered and unanswered, probability updates, candidate CKRs, and
remaining unknowns. The orchestrator accepts or rejects the checkpoint. Candidate CKRs and candidate
PKRs stay off the working board until that checkpoint is accepted.

This artifact is intentionally wrong: it has learning, budget, probability, and checkpoint words, but
the probes never state what board choice they make clearer or what danger they are mapping.

## CKR Layer

Each CKR has a mini reverse tornado with discovery/delivery balance, a DKR question, a direct CKR
metric, and a PKR delivery path after uncertainty is reduced.

- CKR-1 links to source DKR-1: hard violation false accepts stay at zero. Direct metric source of
  truth: checker calibration output and `result.json` violation counts.
- CKR-2 links to source DKR-2: every CKR and PKR has traceability back to DKR evidence. Direct
  metric: percentage of CKR/PKR entries with a `source DKR` field.

## PKR Layer

- PKR-1 linked to CKR-1 and source DKR-1: add golden negative artifacts.
- PKR-2 linked to CKR-2 and source DKR-2: add a checker that rejects CKR or PKR entries missing DKR
  evidence.

## No-Cascade Rule

PKR completion never proves CKR or objective success. The direct metric read comes from the source
of truth after the lag window. Until then, the state is `waiting_for_measurement` and the ledger
records `observed_at`, `recorded_at`, and freshness.

## Signal Handling

Too easy, too hard, stale, non-moving, disconnected, noisy, or gamed metrics trigger `watch`,
`orchestrator_reaim`, or human review. A hard violation accepted by the checker triggers `breaking`.

Check-in cadence: every worker turn and every ten-minute timed heartbeat re-evaluates objective,
CKR, PKR, and anti-goal signals, recollects learning, optimizes process/context, and decides whether
steering is still on time. Workers write file-based progress reports to
`.okra/workers/<worker-id>/progress.jsonl`; the orchestrator reads those reports before updating
the OKR board. PKR signals include off-track work, quality drift, excessive churn, stalled delivery,
and late discovery that should hand back to the orchestrator.
