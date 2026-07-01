# OKRA Learning Memory

Use this reference when a project will run more than one OKRA loop, when the same loop continues
across many turns, or when prior runs should shape the next candidate frame. The goal is not broad
assistant memory. The goal is context-specific memory for running OKRs better under stress.

## Purpose

An OKRA learning memory lets the orchestrator self-learn, self-heal, and self-optimize without
taking frame authority from the human.

- **Self-learning**: prior DKR checkpoints, flags, vetoes, metric misses, and worker unknowns seed
  the next run's candidate anti-goals, DKR probes, and allocation choices.
- **Self-healing**: a current run converts `cannot`, `breaking`, `pointless`, and `authority_drift`
  evidence into repair moves, pauses, dry-runs, or human escalations.
- **Self-optimization**: repeated traps and avoidances become reusable steering rules, but only
  when they improve the objective/anti-goal tradeoff without worsening evals or integrity.
- **Under stress**: time, turn, budget, and attention limits are treated as real constraints. DKR is
  allocated where it retires the most steering uncertainty per budget spent.

The orchestrator may allocate, re-rank, fund, hold, pause, or stop candidate work inside the
ratified frame. It cannot change the objective, target, anti-goals, thresholds, metric contracts, or
action envelope. Reject any attempted frame, guardrail, metric, threshold, or action-envelope change
unless the human ratifies it.

## What To Extract

At every check-in and end-of-run, extract learning records from append-only evidence:

- `trap`: a failure mode hit or nearly hit, such as budget overrun, stale metrics, wrong-tip
  convergence, authority drift, or single-LLM-truth acceptance.
- `avoidance`: a veto, dry-run, pause, check-in, or anti-goal screen that prevented a bad move.
- `misconception`: an assumption corrected by DKR evidence, a flat metric after lag, or review.
- `optimization`: a reusable steering improvement, such as a better DKR budget rule, earlier
  freshness check, stronger PKR progress signal, or clearer escalation threshold.
- `candidate_anti_goal`: a reusable guardrail proposed for later runs, with a metric, threshold,
  type, source evidence, and context where it applies.

Every record should include:

- `source_run_id`
- `source_refs`: check-in, flag, worker report, ledger, content hash, eval result, review path,
  terminal record, or trace manifest reference
- `evidence_kind`: deterministic check, metric read, append-only record, changed-path hash, human
  ratification, or independent review
- `context_key`: product, repo, team, workflow, metric family, or risk domain where this learning
  applies
- `learned_at`, `source_observed_at`, `valid_until` or `recertify_by`, and `invalidates_when`
- `confidence`: probability or confidence with reason
- `applies_when` and `does_not_apply_when`
- `candidate_status`: `candidate`, `ratified`, `rejected`, or `superseded`
- `no_regression_evidence`: eval, checker, metric, or review evidence showing the learning did not
  make accepted behavior worse
- `trace_manifest_ref`: a retained trace proving why this record exists
- `review_set`: second-opinion evidence when the record depends on judgement instead of a
  deterministic check
- `sensitivity`, `redaction_status`, and retention tier for any verbatim source excerpt
- `single_llm_truth_acceptance_count`: normally `0`; any nonzero value is a breaking signal

## Full Memory Cycle

Treat OKRA memory as a reset-and-prepare loop, not as a generic summary. A completed run does not
need to keep every transient detail forever, but it must keep enough trace evidence that a future
orchestrator can avoid the same mistake and verify why the learning exists.

1. **Load**: at run start, scan prior memory candidates for the current `context_key`.
2. **Prepare**: convert relevant candidates into candidate anti-goals, DKR probes, PKR progress
   signals, or action-envelope concerns. They remain candidate-only.
3. **Run**: keep full active traces in `.okra/runs/<run-id>/`: frame, tree, ledger, flags,
   check-ins, worker progress, move results, and content hashes.
4. **Terminalize**: before marking a run complete, write a terminal record with objective and
   anti-goal metric refs, unresolved flags, accepted DKR checkpoints, acceptance evidence, and
   whether the run reached target, stopped, or needs human action.
5. **Consolidate**: distill run evidence into learning records, trace manifests, candidate
   anti-goals, and a continuation packet for the next run.
6. **Retain or shed**: preserve source records and critical excerpts by hash; redact or expire bulky
   or sensitive detail only after the trace manifest can still reconstruct the causal lesson.
7. **Continue**: the next run starts from the continuation packet, then re-checks freshness,
   context fit, no-regression evidence, and human ratification boundaries.

Recommended generated records:

```text
.okra/
  memory/
    <context-key>/
      learning-index.v1.jsonl
      candidate-anti-goals.v1.json
      continuation-packet.v1.json
      trace-manifest.v1.jsonl
  runs/
    <run-id>/
      terminal/run-terminal.v1.json
      memory/completed-run-consolidation.v1.json
```

`run-terminal.v1.json` is the terminal proof for one run. It should include `run_id`,
`terminal_state` (`target_reached`, `stopped_by_human`, `blocked`, `cannot`, `breaking`,
`pointless`, or `authority_drift`), objective metric refs, anti-goal metric refs, open/unresolved
flags, accepted DKR checkpoint refs, promoted CKR/PKR refs, acceptance evidence refs, memory
extraction refs, and the final `single_llm_truth_acceptance_count`.

`completed-run-consolidation.v1.json` is the bridge from active trace to reusable memory. It should
include source run hash, terminal record hash, extracted traps, avoidances, misconceptions,
optimizations, candidate anti-goals, trace manifest refs, redaction decisions, no-regression
evidence, review set refs, and items explicitly rejected or deferred.

`continuation-packet.v1.json` is the compact next-run prep packet. It should include only
candidate inputs: relevant prior traps, avoidances that worked, stale or rejected learnings to avoid,
candidate anti-goals with metrics, suggested DKR probes with budgets and steering decisions,
context-fit notes, freshness/recertification deadlines, and evidence hashes. It must not rewrite the
current frame or promote guardrails without current-run evidence and human ratification.

`candidate-anti-goals.v1.json` is the accumulated guardrail library for a context. It should include
only reusable candidate anti-goals, not active frame defaults. Each entry should include `metric_id`,
threshold, type (`drift` or `tripwire`), `source_run_id`, `source_refs`, `trace_manifest_ref`,
`applies_when`, `does_not_apply_when`, `invalidates_when`, `valid_until` or `recertify_by`,
confidence, `candidate_status`, `no_regression_evidence`, review-set refs when needed, and
ratification status. A future run may load this file as input, but promotion still requires
current-context evidence and human ratification for any frame or guardrail change.

`trace-manifest.v1.jsonl` is the retention proof. Each line should include source log path, sequence
or line range, content hash, excerpt hash, causal decision path, sensitivity, redaction status,
retention tier, expiry or tombstone, and the memory records that depend on it. If a memory item loses
its trace, fail closed: keep it candidate-only and spawn a DKR to re-verify or discard it.

## Storage Shape

Keep authoritative learning in append-only run records. Generate memory views from those records.

Recommended paths:

```text
.okra/
  memory/
    <context-key>/
      learning-index.v1.jsonl        # generated view from source records
      candidate-anti-goals.v1.json   # generated view, not authority
      continuation-packet.v1.json    # generated next-run prep packet, not authority
      trace-manifest.v1.jsonl        # retained evidence map for learned records
  runs/
    <run-id>/
      terminal/run-terminal.v1.json
      memory/completed-run-consolidation.v1.json
      ledger.jsonl
      flags.jsonl
      checkins.jsonl
      workers/<worker-id>/progress.jsonl
```

Use `checkins.jsonl` for learning checkpoints and memory extraction records, `flags.jsonl` for
trap/repair lifecycle, `ledger.jsonl` for objective and anti-goal metrics, worker progress files for
DKR/PKR evidence, and `terminal/run-terminal.v1.json` for the completion claim. A generated memory
file is a convenience index; the source of truth remains the append-only records, terminal proof,
trace manifests, review evidence, and content hashes.

## Reuse Gate

At the start of a related run:

1. Load previous learning-memory candidates for the current `context_key`.
2. Reject stale or mismatched entries whose `applies_when` no longer fits the current frame.
3. Convert relevant entries into candidate anti-goals, DKR probes, PKR progress signals, or action
   envelope concerns.
4. Keep all candidates unpromoted until the orchestrator accepts current-run evidence and the human
   ratifies any frame or guardrail addition.
5. Record a no-regression check before accepting a learned rule into the run's working behavior.

Previous-run memory is automatic input, not automatic authority. A good reuse record says "this
prior trap suggests a candidate anti-goal", not "the prior run changed the current frame."

## Value Verification

Do not count memory as valuable just because it exists. Verify that it improves the next reset while
preserving the anti-goals:

- **Reset replay**: start a fresh agent from only the continuation packet and retained trace refs;
  check whether it scans prior memory, avoids rejected claims, keeps candidates unpromoted, and
  preserves `single_llm_truth_acceptance_count == 0`.
- **Counterfactual eval**: remove terminal proof, trace manifest, or review-set evidence from a
  fixture and require the checker to fail.
- **Scored blindbox eval**: run the same case against independent agent/model paths when model
  access is available.
- **Repeated-mistake metric**: compare related runs and track whether stale-memory, trace-loss,
  unratified-promotion, or single-model-truth mistakes recur.

Useful value metrics: `prior_run_scan_miss_count == 0`, `trace_loss_reuse_count == 0`,
`stale_learning_reuse_count == 0`, `unratified_memory_promotion_count == 0`, and a decreasing
`repeated_mistake_recurrence_count` across comparable runs.

## Anti-Goals For Learning Memory

Use these when the run depends on prior learning:

- `prior_run_scan_miss_count == 0`: the orchestrator scanned available previous-run learning before
  proposing the current frame or DKR allocation.
- `unratified_memory_promotion_count == 0`: no previous-run memory changed the frame, guardrails,
  thresholds, metrics, or action envelope without human ratification.
- `eval_regression_count == 0`: accepted learning did not make deterministic evals, checkers, or
  acceptance metrics worse than the baseline.
- `single_llm_truth_acceptance_count == 0`: no learning record or success claim was accepted from
  one model narrative alone.
- `stale_learning_reuse_count == 0`: no outdated or context-mismatched learning was promoted.

## DKR Allocation Under Stress

When time or turn budget is tight, DKR should not expand into general research. Rank DKR candidates
by steering value:

- How much objective uncertainty does this probe retire?
- How much anti-goal uncertainty does it retire?
- Which allocation decision will it unlock: promote, fund, dry-run, veto, pause, re-aim, or escalate?
- What is the budget, stop rule, and next checkpoint?
- What happens if the result is empty?

Empty DKR is valid when it tells the orchestrator not to fund a path or when it surfaces `cannot`.
Budget exhaustion without useful learning opens `cannot`; it does not justify unbounded discovery.

## Acceptance Evidence

Do not accept learning memory from a single LLM self-report. Evidence requirements depend on the
claim class:

- deterministic claims need deterministic checker/eval output, metric reads, store verification,
  content hashes, changed-path hashes, or equivalent source evidence
- semantic or judgement-heavy claims need human ratification or at least two independent review
  artifacts in addition to source evidence
- frame, guardrail, threshold, metric, or action-envelope changes always need human ratification

Represent second opinions as structured `review_set` evidence, not a bare phrase. A review record
should include reviewer kind, tool/model when known, prompt hash, source content hashes, verdict,
objections or dissent, confidence, independence basis, conflict status, and path/hash of the review
artifact. Preserve dissent; disagreement is a DKR input, not a reason to silently average the
answers.

If evidence is missing, store the item as a candidate with lower confidence and a DKR to verify it.
If evals are worse, open `breaking` or `pointless` depending on whether the regression violates an
anti-goal or merely fails to improve the objective.
