# OKRA Self-Harness Workspace

This repository is a planning-only workspace. Build an eval harness design for the
`reverse-tornado-okr` skill itself.

The objective is to produce a blindbox harness that shows high acceptance of OKRA structure across
Codex and Claude runs.

Candidate objective metric:

- `okra_harness_acceptance_score >= 0.85` across real blindbox runs.

Candidate anti-goal:

- `hard_okra_violation_count_in_accepted_runs == 0`.
- Type: tripwire.

Hard violations the harness must not accept:

- Solution rush: the artifact jumps to a pile of PKRs/tasks before DKR exposes uncertainty,
  options, probabilities, and reasons for choosing CKRs.
- Cascade: task or PKR completion is treated as CKR/objective progress instead of using direct
  metric reads.
- Boundary drift: the agent changes objective, anti-goal, threshold, metric definition, or action
  envelope without human ratification.
- Metric theater: metrics are too easy, too hard, stale, non-moving, disconnected, or not used as
  signals for the orchestrator.
- DKR abuse: discovery is absent, too broad, too numerous, too long-running, disconnected from CKR
  or PKR, or missing budget/stopping rules.
- Disconnected refinement: DKR, CKR, and PKR appear as lists but do not shape each other.
- Stale steering: the artifact has no check-in cadence, no CKR-level discovery/delivery balance,
  or no PKR signals that reveal off-track work early.

Conceptual model:

- Objective and anti-goal shape the outer boundary of the box.
- DKR, CKR, and PKR shape the middle.
- DKR contributes reasoning and probability-weighted options.
- CKR proves that progress is meaningful for the objective. Each CKR should behave like a mini
  reverse tornado with its own discovery/delivery balance.
- PKR proves that execution progress is focused, healthy, and high quality. PKRs must expose
  progress signals, not just task completion.
- Signals from every level go first to the orchestrator, then to the human when thresholds are hit.
- Check-ins are the steering cadence: they re-evaluate work, recollect learning, optimize process
  and context, and catch off-track work before an LLM spends a long run in the wrong direction.
- The orchestrator owns the loop, objective checks, check-ins, OKR board, and steering. It does not
  stop because PKRs or board items are complete; it loops until the objective metric is achieved or
  a human-owned/blocking condition stops it.
- DKR and PKR are the subagent work units. CKR is measurable contribution context for the
  orchestrator, not a subagent task.

Create only `tasks/okra-self-harness.md`. Do not implement checker code in this workspace.
