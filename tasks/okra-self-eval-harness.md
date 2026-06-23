# OKRA Self-Eval Harness

This is a candidate Reverse Tornado frame for building the OKRA eval harness with OKRA itself.
It should be ratified before turning the harness into implementation work.

## Candidate Frame

### Objective

Build a blindbox eval harness that demonstrates the `reverse-tornado-okr` skill expresses OKRA's
core concept, not just OKR vocabulary.

Candidate target metric:

- `okra_harness_acceptance_score >= 0.85` across real Codex and Claude blindbox runs.
- Every accepted run must satisfy all hard OKRA gates.
- Scored runs must preserve prompt packets, model identity, hashes, checker output, and changed-path
  evidence.

### Anti-Goal

Do not accept artifacts that violate OKRA's core operating constraints.

Candidate anti-metric:

- `hard_okra_violation_count_in_accepted_runs == 0`

Type: tripwire. Any accepted artifact with a hard violation fails the harness, regardless of its
rubric score.

Hard violations:

- Solution rush: the artifact jumps to a large PKR/task list before DKR has surfaced uncertainty,
  options, probabilities, a learning checkpoint, and reasons for choosing CKRs.
- Cascade: the artifact treats lower-level task completion as progress toward CKR/objective success
  instead of using direct metric reads.
- Boundary drift: the artifact changes the objective, anti-goal, thresholds, metric definitions, or
  action envelope without human ratification.
- Metric theater: metrics are too easy, impossible, non-moving, disconnected from the stated goal,
  or not used as signals.
- DKR abuse: discovery is absent, disconnected from CKR/PKR design, too broad, too numerous, too
  long-running, missing budget/stopping rules, or missing an orchestrator-accepted learning
  checkpoint before CKR/PKR promotion.
- Disconnected refinement: DKR findings do not shape CKR metrics, or CKRs do not shape focused PKR
  progress.
- Stale steering: the artifact has no check-in cadence, no CKR-level mini reverse tornado, or no
  PKR signals that expose off-track work before a long run is wasted.

## Model To Test

The harness should evaluate OKRA as a bounded box:

- Objective and anti-goal define the outer boundary.
- DKR, CKR, and PKR shape the middle.
- DKR contributes reasoning and probability-weighted options.
- CKR proves that progress is meaningful for the objective. Each CKR has its own mini reverse
  tornado: a discovery layer to test whether the CKR matters, a direct metric, and a delivery path
  only after the uncertainty is reduced.
- PKR proves that execution progress is focused, healthy, and high quality. PKR does not prove
  objective movement; it emits progress, quality, churn, off-track, and late-discovery signals.
- Check-ins are the steering cadence. They re-evaluate the work, recollect learning, optimize
  process/context, and make sure steering happens before an LLM spends a long run in the wrong
  direction. Long-running subagents report through file-based progress logs, with a ten-minute
  heartbeat as the default live cadence.
- Signals from every level go first to the orchestrator, then to the human when thresholds are hit.
- The orchestrator owns the loop, objective checks, check-ins, the OKR board, and subagent steering.
  It does not stop because PKRs or board items are complete; it keeps checking and steering until
  the objective metric is achieved, the human changes/stops the frame, or a blocking flag requires
  human resolution.
- DKR and PKR are the executable subagent work. CKR is measurable contribution context for the
  orchestrator, not a subagent task.
- CKR/PKR entries stay candidate-only until the orchestrator accepts a DKR learning checkpoint with
  evidence, probability/confidence updates, and remaining unknowns.

The harness should reject outputs that only fill the middle with plausible tasks.

## DKR-First Harness Probes

These probes are the first work. They should run before committing to checker implementation.

### DKR-1: Observable Anti-Patterns

Question: Which OKRA anti-patterns can be detected deterministically from an artifact, and which
need rubric judgment?

Budget: one design pass plus one handcrafted positive/negative fixture pass.

Expected output:

- A hard-gate list with deterministic signals.
- A scored-rubric list for softer quality signals.
- Known false-positive and false-negative risks.
- DKR learning checkpoint schema and candidate-promotion rule.

Probability output:

- `P(deterministic_gate_sufficient)` for each hard violation.
- `P(rubric_needed)` for each softer signal.

### DKR-2: DKR-To-CKR-To-PKR Traceability

Question: What evidence proves that discovery shaped CKR and PKR design?

Budget: one design pass.

Expected output:

- A traceability contract linking each CKR to DKR evidence.
- A traceability contract linking each PKR/task group to a CKR and the DKR evidence that made it
  likely to matter.
- Rules for empty DKR results, uncertainty, probabilities, and confidence changes.

### DKR-3: Signal Semantics

Question: Which metric behaviors should trigger orchestrator attention or human escalation?

Budget: one design pass.

Expected output:

- Signal table for too-easy, too-hard, stale, non-moving, lagged, disconnected, noisy, or gamed
  metrics.
- DKR signal table for absent, excessive, stalled, disconnected, or unbudgeted discovery.
- PKR signal table for off-track work, quality drift, excessive churn, late discovery, and stalled
  delivery.
- Escalation table mapping each signal to `watch`, `orchestrator_reaim`, or `human_review`.
- Check-in cadence for re-evaluating all active DKR/CKR/PKR work and optimizing process/context.

### DKR-4: Fixture Pressure

Question: Which blindbox fixtures force the model to use OKRA instead of generic planning?

Budget: one fixture design pass.

Expected output:

- Positive cases where a good artifact needs DKR first.
- Negative/golden bad artifacts that must fail.
- Real-agent cases for Codex and Claude after the golden cases pass.

## Candidate CKRs

### CKR-1: Concept Coverage

Metric: `core_concept_coverage >= 0.95`

Definition: rubric dimensions cover objective/anti-goal boundaries, DKR reasoning, probability,
CKR meaningfulness, PKR focus, no-cascade direct measurement, signal handling, orchestrator/human
escalation, and blindbox artifact preservation.

Each accepted CKR should have a CKR-level mini reverse tornado: a DKR question about what makes the
CKR meaningful, a direct CKR metric, PKR admission rules, and check-in signals.

### CKR-2: False Acceptance Control

Metric: `accepted_hard_violation_count == 0`

Definition: no artifact with a hard OKRA violation can pass, even if it has strong vocabulary or a
high soft rubric score.

### CKR-3: Agent Acceptance Under Blindbox

Metric: `real_agent_pass_rate >= 0.85` with `hard_violation_count == 0`

Definition: Codex and Claude runs create artifacts that meet the structure and hard gates in
isolated blindbox workspaces.

### CKR-4: Eval Evidence Quality

Metric: `run_evidence_completeness == 1.0`

Definition: every scored run archives prompt, command, final artifact, changed paths, checker
output, input hashes, model identity, and review output when applicable.

## PKR Admission Rules

Do not start with a pile of PKRs. A PKR becomes admissible only when it links to a DKR finding and a
CKR metric.

Minimum PKR admission record:

- source DKR
- accepted DKR learning checkpoint
- probability or rationale from the DKR
- CKR it improves
- expected checker/rubric effect
- anti-goal risk
- rollback or rejection criterion

Candidate PKRs after DKR ratification:

- Add a case-specific OKRA semantic checker for hard gates.
- Add handcrafted positive and negative artifacts for checker calibration.
- Add blindbox fixtures that force DKR-first behavior.
- Extend result JSON to report hard violations and rubric dimension scores.
- Run Codex and Claude blindbox smoke after golden fixtures pass.

## Hard Gates

The harness should fail an artifact immediately when any hard gate is present.

### Gate A: Solution Rush

Fail when the first-turn artifact contains many PKRs/tasks but has no DKR inventory, no discovery
budget, no uncertainty, and no probability-weighted route to CKRs.

Candidate observable signals:

- PKR/task count is high before DKR count is nonzero.
- CKRs appear without DKR evidence or probability.
- The artifact says "implement/build/launch" before it defines what is unknown.

### Gate B: Cascade

Fail when lower-level completion is treated as objective or CKR progress.

Candidate observable signals:

- "If tasks are done, CKR is done."
- "PKR completion rolls up to objective success."
- No direct metric read, lag rule, or waiting-for-measurement state.

### Gate C: Boundary Drift

Fail when the artifact lets the agent change the objective, anti-goal, thresholds, metric
definitions, or action envelope without human ratification.

Candidate observable signals:

- "Adjust the target if progress is slow."
- "Relax the guardrail if needed."
- Missing human-owned frame.

### Gate D: Metric Theater

Fail when metrics cannot steer the loop.

Candidate observable signals:

- Metrics are impossible, trivial, stale, disconnected, or missing source/owner/freshness rules.
- Non-moving metrics do not trigger pointless/re-aim behavior after lag closes.
- Too-easy or too-hard metrics are not treated as signals.

### Gate E: DKR Abuse

Fail when discovery is absent or uncontrolled.

Candidate observable signals:

- No DKR before CKR/PKR.
- DKR has no scope, budget, stopping rule, or expected output.
- DKR has no learning checkpoint with evidence, probability/confidence update, and remaining
  unknowns.
- CKR/PKR candidates are promoted before the orchestrator accepts the checkpoint.
- Many DKRs run without prioritization or probability.
- Long-running DKR never returns signal to the orchestrator.

### Gate F: Disconnected Refinement

Fail when DKR, CKR, and PKR are listed but not causally connected.

Candidate observable signals:

- CKRs are generic metrics not justified by discovery.
- PKRs are generic tasks not attached to a CKR.
- DKR findings do not change the CKR/PKR plan.

### Gate G: Stale Steering

Fail when the artifact lacks check-ins frequent enough to keep steering on time.

Candidate observable signals:

- No check-in cadence, heartbeat, or `next_check_at`.
- No ten-minute heartbeat or equivalent time-based check-in for long-running subagents.
- No file-based worker progress report such as `.okra/workers/<worker-id>/progress.jsonl`.
- CKRs do not contain a mini reverse tornado balancing discovery and delivery.

### Gate H: Loop Ownership Drift

Fail when the artifact lets the loop stop because board work is complete or treats CKR as
subagent-executed work.

Candidate observable signals:

- The orchestrator does not own objective checks, check-ins, OKR board management, and subagent
  steering.
- The loop declares done when PKRs/tasks/board items are complete rather than when the objective
  metric reaches target.
- A CKR is dispatched to a worker/subagent as work instead of used as measurable context.
- PKRs report only completion, not progress health, off-track work, quality drift, churn, stalled
  delivery, or late discovery.
- Check-ins do not recollect learning, re-evaluate objective/CKR/PKR/anti-goal signals, or optimize
  process/context.

## Soft Rubric

Use soft scoring only after all hard gates pass.

Candidate dimensions:

- Objective and anti-goal boundary quality.
- DKR quality: scoped, plural when useful, budgeted, uncertainty-aware, probability-producing.
- CKR quality: measurable, meaningful, tied to objective movement, direct metric source.
- PKR quality: focused, high quality, do-and-check, linked to CKR.
- No-cascade discipline: progress reads from direct metrics, not task rollups.
- Signal handling: bad metrics, stale metrics, excessive discovery, stalled discovery, and
  disconnected layers trigger orchestrator/human attention.
- Check-in discipline: active DKR/CKR/PKR work is re-evaluated frequently enough to catch off-track
  work before long wasted runs.
- Operating loop readiness: cadence, heartbeat, lag windows, freshness, flags, idempotent storage.
- Evidence quality: prompt/run/check artifacts are inspectable and repeatable.

## Candidate Eval Cases

### Golden Positive Cases

- Sparse product goal where correct output must start with DKR probes before CKR/PKR.
- Real-life recurring operation with stale metrics, lag windows, and authority boundaries.
- Self-harness design case using OKRA to build the OKRA harness.

### Golden Negative Cases

- `solution-rush`: many PKRs, no DKR, no uncertainty, no probability.
- `dkr-learning-cycle`: DKR heading exists, but no learning checkpoint or promotion gate.
- `cascade-scoreboard`: task completion is treated as objective progress.
- `metric-theater`: easy or impossible metrics pass without signal handling.
- `over-discovery`: too many DKRs, no budget, no convergence rule.
- `disconnected-layers`: DKR, CKR, and PKR exist but do not influence each other.
- `boundary-drift`: the agent changes target/threshold/action authority without human ratification.
- `stale-steering`: no check-in cadence, no CKR-level mini reverse tornado, or no PKR health
  signals; no time-based heartbeat or worker progress file for long-running subagents.

### Real-Agent Cases

Run only after golden fixtures pass:

- Codex on smoke case.
- Claude on smoke case.
- Codex on real-life operations.
- Claude on real-life operations.
- Codex on self-harness case.
- Claude on self-harness case.

## Three Anti-Goal Eval Points

### 1. Admissibility

Before accepting a checker/rubric change, ask whether it can falsely accept a hard violation.
If yes, keep it in DKR or build a negative fixture first.

### 2. Direct Read

After a blindbox run, read the actual artifact and checker output. Do not trust the agent's summary
that it followed OKRA.

### 3. Paired With Objective

The harness only succeeds when rubric acceptance is high and hard violations remain zero. A high
score with one accepted hard violation is a failed harness.

## Signals And Flags

- `cannot`: anti-pattern cannot be observed reliably by deterministic checks and needs rubric or
  human review.
- `breaking`: a checker accepts a known hard violation.
- `pointless`: agents pass the harness but generated artifacts do not show OKRA-specific behavior.
- `authority_drift`: the harness lets agents rewrite the skill's frame, targets, or anti-goals while
  claiming success.
- `overfit`: agents pass only because the prompt mirrors the rubric too closely.
- `underfit`: good artifacts fail because the checker over-constrains wording instead of behavior.
- `stale_steering`: PKR work can run too long before the orchestrator re-evaluates learning,
  context, process, and anti-goal risk.

## Operating Loop

Cadence:

- Start with DKR probes and golden fixture calibration.
- Run real Codex/Claude blindbox only after golden positives and negatives behave correctly.
- Re-run golden fixtures whenever the skill, rubric, checker, runner, or prompt changes.
- Every check-in re-evaluates DKR/CKR/PKR work, recollects learning, optimizes process/context, and
  decides whether steering is still on time.
- Every long-running worker writes `.okra/workers/<worker-id>/progress.jsonl` on completion, unknown
  discovery, flag-worthy risk, and the ten-minute heartbeat.

Freshness:

- Current status is candidate frame.
- Human ratification needed before treating thresholds as final.
- `next_check_at`: after DKR-1 through DKR-4 are completed or deliberately narrowed.

Ledger:

- Record every real blindbox run under `.runs/blindbox/`.
- Preserve prompt packets, input hashes, checker versions, and review artifacts.

Blocking rules:

- `breaking` blocks all acceptance claims.
- `boundary_drift` blocks the run until human ratification.
- `overfit` requires prompt/rubric separation before more model calls.
- `underfit` requires golden fixture review before tightening checks.

## Next Move

The next admissible move is DKR-1: map the anti-patterns above into deterministic hard gates versus
soft rubric dimensions, then create the first negative/golden artifacts to test whether the checker
can reject OKRA-looking but invalid output.
