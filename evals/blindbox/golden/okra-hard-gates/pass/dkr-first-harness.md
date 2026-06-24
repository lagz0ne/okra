# DKR-First Harness Artifact

## Objective

Build an OKRA blindbox harness with `okra_harness_acceptance_score >= 0.85` across Codex and Claude
while preserving prompt, model, hash, checker, and changed-path evidence.

## Anti-Goal

Metric: `hard_okra_violation_count_in_accepted_runs == 0`.

Type: tripwire. Human approval is required to change this threshold.

## Human-Owned Frame

The human owns the objective, anti-goal, thresholds, metric definitions, and action envelope. The
orchestrator can propose changes but cannot ratify or apply them.

## Loop Ownership

The orchestrator owns objective checks, check-ins, the OKR board, and subagent steering. It keeps
checking, steering, and dispatching until the objective metric reaches target, a human changes the
frame, or a blocking flag requires human resolution. It does not stop just because PKRs, tasks, or
board items are complete.

Subagents do executable work only for DKR and PKR: discovery workers run budgeted DKR probes, and
progression workers execute PKR tasks. CKR is measurable contribution context for the orchestrator:
it holds the metric and contribution hypothesis, but it is not a worker, not a subagent task, and
not dispatched as executable work.

## DKR Layer

- DKR-1: Probe which anti-patterns are deterministically observable. Budget: one design pass and
  one golden-fixture pass. Decision target: decide whether to hard-gate solution-rush and cascade
  or leave them to rubric review. Unknown: which signals are reliable from markdown alone. Risk if
  skipped: the harness may chase the objective score while accepting anti-goal traps. Probability:
  70% of solution-rush and cascade can be hard-gated; 30% needs rubric review.
- DKR-2: Probe DKR-to-CKR-to-PKR traceability. Budget: one design pass. Decision target: decide
  whether CKR/PKR candidates can be promoted onto the working board. Unknown: how much causal
  evidence is enough. Anti-goal uncertainty: traceability gaps may let vague progress hide unsafe
  or pointless work. Probability: 65% deterministic when source DKR links are explicit.
- DKR-3: Probe metric signal semantics. Budget: one design pass. Decision target: decide whether to
  continue, pause, or re-aim when a metric looks too easy, too hard, stale, non-moving, disconnected,
  noisy, or gamed. Risk if skipped: the orchestrator may keep moving through the maze without seeing
  traps. Probability: 55% deterministic, 45% rubric.

Each DKR must produce a learning checkpoint before any CKR or PKR is promoted from candidate status:
decision target, evidence collected, questions answered and unanswered, probability updates, risk or
anti-goal implications, candidate CKRs, and remaining unknowns. The orchestrator accepts or rejects
the checkpoint. Candidate CKRs and candidate PKRs stay off the working board until that checkpoint is
accepted.

## CKR Layer

Each CKR runs a mini reverse tornado: it has a DKR question for what makes the CKR meaningful, a
direct CKR metric, and a PKR delivery path only after the CKR-level uncertainty is reduced. This
keeps discovery and delivery balanced inside the CKR context instead of turning CKR into a static
metric or worker task.

- CKR-1 links to source DKR-1: hard violation false accepts stay at zero. Direct metric source of
  truth: checker calibration output and `result.json` violation counts.
- CKR-2 links to source DKR-2: every CKR and PKR has traceability back to DKR evidence. Direct
  metric: percentage of CKR/PKR entries with a `source DKR` field.
- CKR-3 links to source DKR-3: signal handling is present for too easy, too hard, stale,
  non-moving, disconnected, noisy, and gamed metrics. Direct metric: signal table coverage.

## PKR Layer

- PKR-1 linked to CKR-1 and source DKR-1: add golden negative artifacts for solution rush, cascade,
  boundary drift, metric theater, DKR abuse, and disconnected refinement.
- PKR-2 linked to CKR-2 and source DKR-2: add a checker that rejects CKR or PKR entries missing DKR
  evidence.
- PKR-3 linked to CKR-3 and source DKR-3: add a signal table and require orchestrator or human
  review when a metric is stale, too easy, too hard, non-moving, or disconnected.

## No-Cascade Rule

PKR completion never proves CKR or objective success. The direct metric read comes from the source
of truth after the lag window. Until then, the state is `waiting_for_measurement` and the ledger
records `observed_at`, `recorded_at`, and freshness.

## Signal Handling

Every abnormal signal goes to the orchestrator first. Too easy, too hard, stale, non-moving,
disconnected, noisy, or gamed metrics trigger `watch`, `orchestrator_reaim`, or human review. A
hard violation accepted by the checker triggers `breaking`.

Check-in cadence: every worker turn and every ten-minute timed heartbeat re-evaluates objective,
CKR, PKR, and anti-goal signals, recollects learning, optimizes process/context, and decides whether
steering is still on time. Workers write file-based progress reports to
`.okra/workers/<worker-id>/progress.jsonl`; the orchestrator reads those reports before updating
the OKR board. PKR signals include off-track work, quality drift, excessive churn, stalled delivery,
and late discovery that should hand back to the orchestrator.
