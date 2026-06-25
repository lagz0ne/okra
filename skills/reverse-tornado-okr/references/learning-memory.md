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
- `source_refs`: check-in, flag, worker report, ledger, content hash, eval result, or review path
- `evidence_kind`: deterministic check, metric read, append-only record, changed-path hash, human
  ratification, or independent review
- `context_key`: product, repo, team, workflow, metric family, or risk domain where this learning
  applies
- `confidence`: probability or confidence with reason
- `applies_when` and `does_not_apply_when`
- `candidate_status`: `candidate`, `ratified`, `rejected`, or `superseded`
- `no_regression_evidence`: eval, checker, metric, or review evidence showing the learning did not
  make accepted behavior worse
- `single_llm_truth_acceptance_count`: normally `0`; any nonzero value is a breaking signal

## Storage Shape

Keep authoritative learning in append-only run records. Generate memory views from those records.

Recommended paths:

```text
.okra/
  memory/
    <context-key>/
      learning-index.v1.jsonl        # generated view from source records
      candidate-anti-goals.v1.json   # generated view, not authority
  runs/
    <run-id>/
      ledger.jsonl
      flags.jsonl
      checkins.jsonl
      workers/<worker-id>/progress.jsonl
```

Use `checkins.jsonl` for learning checkpoints and memory extraction records, `flags.jsonl` for
trap/repair lifecycle, `ledger.jsonl` for objective and anti-goal metrics, and worker progress files
for DKR/PKR evidence. A generated memory file is a convenience index; the source of truth remains the
append-only records and content hashes.

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

Do not accept learning memory from a single LLM self-report. Use one or more of:

- deterministic checker or eval output
- metric reads with freshness
- append-only store verification
- content hashes or changed-path hashes
- human ratification
- independent Codex/Claude review

If evidence is missing, store the item as a candidate with lower confidence and a DKR to verify it.
If evals are worse, open `breaking` or `pointless` depending on whether the regression violates an
anti-goal or merely fails to improve the objective.
