# OKRA Learning Memory Loop

## Objective

Metric: `learning_memory_reuse_acceptance_rate >= 0.85` across scored OKRA runs.

## Anti-Goals

- `prior_run_scan_miss_count == 0`, tripwire.
- `unratified_memory_promotion_count == 0`, tripwire.
- `eval_regression_count == 0`, tripwire: evals must not be worse before accepting a learning rule.
- `single_llm_truth_acceptance_count == 0`, tripwire.
- `stale_learning_reuse_count == 0`, tripwire.

The human owns the frame and ratifies any guardrail or threshold addition.

## Prior-Run Auto Input

At run start the orchestrator automatically scans and loads previous runs for this same project
context key. Prior runs are automatic inputs, not automatic authority. Each memory stays candidate
only until current-run evidence supports it and the human ratifies any frame or anti-goal change.
Learning memory must not auto-promote candidate anti-goals into guardrails, and it must not promote
guardrails automatically into the action envelope. Single LLM truth is not enough evidence for
acceptance.

## OKRA-Specific Memory

This is OKRA learning memory, not generic assistant memory. The generated context memory extracts
traps, avoidances, misconceptions, optimizations, and reusable candidate anti-goals.

- Trap: single-model final narratives were treated as proof.
- Avoidance: require hashes, append-only ledger/check-in records, deterministic checker output, or
  independent review.
- Misconception: `recorded_at` freshness was confused with `observed_at` freshness.
- Optimization: run the freshness check before dispatch and give DKR a stop rule.
- Candidate anti-goal: `single_llm_truth_acceptance_count == 0`, metric threshold `== 0`, tripwire,
  source run `storage-governance`, confidence 0.9, ratification status `candidate`.

Each record has `source_refs`, `sha256` or ledger refs, `context_key`, `applies_when`,
`does_not_apply_when`, confidence, and no-regression evidence.

## Stress Allocation

Stress means time, turn, DKR budget, and attention pressure while objective progress must not violate
anti-goals. The orchestrator allocates under stress by ranking DKR probes, funding or holding
candidate CKRs/PKRs, vetoing high anti-goal-cost moves, and pausing when evidence says the objective
is unachievable within the current frame. The clear cannot signal is opened when DKR budget is spent
and the objective cannot be reached without changing a human-owned boundary.

DKR is the learning allocator. Each DKR has budget, probability/confidence output, and a steering
decision: promote, fund, dry-run, veto, pause, re-aim, or raise cannot. CKR remains measurable
contribution context. PKR is progress work with signals.

## Self-Healing

The loop repairs itself through flags. `cannot` pauses exhausted discovery and asks the human for a
budget or direction decision. `breaking` blocks committing moves when anti-goal evidence trips.
`pointless` stops a branch when the objective metric stays flat after the lag window. `authority_drift`
rejects unratified memory promotion and escalates to the human.

## Evidence Gate

No learning record is accepted from single LLM truth. Acceptance needs deterministic eval output,
metric reads, append-only store verification, content hashes, changed-path evidence, human
ratification, or independent review. The no-regression check records `eval_regression_count == 0`
before a learned optimization changes current-run behavior.
