# OKRA Handoff Contract Artifact

Objective: `handoff_contract_acceptance_rate >= 0.90` while anti-goals
`single_llm_truth_acceptance_count == 0`, `unratified_memory_promotion_count == 0`, and
`eval_regression_count == 0` hold.

## Worker Prompt Packet

Every next-prompt packet is a dispatch packet, not a raw chat continuation. It includes:

- Frame fields: objective, anti-goals, action envelope, and human-ratified boundaries.
- Current state fields: current round, fresh/stale metric reads, open flags, active CKR and active
  PKR status, and remaining budget.
- Previous checkpoint fields: previous DKR learning checkpoint, accepted checkpoint status, source
  DKR checkpoint, and evidence hashes.
- Assignment fields: worker type, exact scope, allowed actions, forbidden actions, budget, stop
  rule, hand-back rule, and output schema.
- Output schema: write back to progress.jsonl or a learning checkpoint with changed paths, commands
  run, next unknowns, and evidence refs.

## In-Progress Influence

Only governed in-progress records influence the next dispatch: worker progress in progress.jsonl,
check-ins, metric reads in the ledger, flags, and accepted checkpoints. A freeform narrative, worker
narrative, vibes, chat continuation, self-report, or model narrative must not influence the next
prompt unless it points to those records.

## DKR-To-DKR Handoff

Previous DKR learning checkpoint `dkr-storage-signal` has decision target: decide whether to promote
PKR-write-governance-checker. Evidence refs include source refs, evidence hashes, trace refs, and a
prompt hash. Answered questions: read-governance detection works. Unanswered questions and next
unknowns: generated memory views may be confused with append-only source records. Confidence update:
before 0.55, after 0.82. Risk or anti-goal implications: the evidence reduces
`eval_regression_count` risk but leaves `unratified_memory_promotion_count` uncertainty open.
Orchestrator decision: checkpoint accepted for read detection, held for write detection, needs
follow-up for generated-view/source-record distinction.

Next DKR is scoped by prior evidence only: reduce uncertainty about generated-view/source-record
distinction before the orchestrator funds or vetoes the PKR.

## CKR To PKR Traceability

CKRs are measurable contribution context, not a worker, not a subagent, not a task, and not
dispatched. CKR `ckr-write-governance-signal` defines the measurable contribution metric
`write_governance_detection_rate >= 0.90` and the direct CKR metric.

Each PKR carries linked_ckr, source_dkr_checkpoint, contribution_metric, done check, acceptance
check, changed paths, commands run, and progress signals. PKR progress signals include off-track
work, quality drift, churn, late discovery, stale metrics, scope concern, and authority concern.
PKRs hand back on unknown discovery: if a progression worker hits unresolved uncertainty, it must
stop and report unknown; the orchestrator decides whether to spawn a DKR.

## Accumulated Anti-Goals

The accumulated anti-goal layer is a candidate guardrail library, represented as
candidate-anti-goals.v1.json. Each record includes metric_id, metric, threshold, tripwire or drift
type, applies_when, does_not_apply_when, invalidates_when, recertify_by or valid_until,
candidate_status, no_regression_evidence, trace_manifest_ref, source refs, and evidence hashes.

Previous-run anti-goals are candidate-only and not automatic authority. Human ratification is
required before a candidate anti-goal changes the frame, thresholds, metrics, guardrails, or action
envelope. The reusable anti-goal `unratified_memory_promotion_count == 0` guards this boundary.
