# Terminalized Continuation Memory

## Objective

Metric: `completed_run_memory_value_score >= 0.85` for future OKRA skill and eval work.

## Anti-Goals

- `single_llm_truth_acceptance_count == 0`, tripwire.
- `prior_run_scan_miss_count == 0`, tripwire.
- `trace_loss_reuse_count == 0`, tripwire.
- `stale_learning_reuse_count == 0`, tripwire.
- `unratified_memory_promotion_count == 0`, tripwire.

## Terminal Artifacts

Every completed run writes `terminal/run-terminal.v1.json` before reuse. The terminal proof includes
objective metric refs, anti-goal metric refs, unresolved flags, accepted DKR checkpoints, acceptance
evidence refs, second-opinion evidence, and the final `single_llm_truth_acceptance_count`.

The bridge from active trace to reusable memory is
`memory/completed-run-consolidation.v1.json`. It extracts traps, avoidances, misconceptions,
optimizations, candidate anti-goals, no-regression evidence, `review_set` refs, and claims rejected
or deferred.

The reset prep is `memory/continuation-packet.v1.json`. It is candidate only: prior traps,
avoidances, and candidate anti-goals are not authority. The next run must re-check freshness,
context fit, current-run evidence, and human ratification before any frame, guardrail, metric,
threshold, or action-envelope change.

The retention proof is `memory/trace-manifest.v1.jsonl`. Each line has source path, seq or line
range, sha256/content hash, excerpt hash, causal decision path explaining why the lesson exists,
sensitivity, redaction status, retention tier, expiry/tombstone, and the memory records that depend
on that trace.

## Evidence And Review

No single LLM truth is accepted: `single_llm_truth_acceptance_count == 0`. Evidence includes
deterministic checker output, store verification from append-only logs, content hashes, metric reads
from the ledger, changed-path allowlist results, human ratification, and independent review. The
structured `review_set` records reviewer kind, tool/model when known, prompt hash, source
hash/content hash, verdict, objections or dissent, confidence, independence basis, conflict status,
and path/hash.

## Value Verification

Value is verified by reset replay with a fresh agent from only the continuation packet. A
counterfactual negative eval with the trace manifest withheld must fail. A scored blindbox eval for
the default dogfood case must run when model access is available. Repeated-mistake recurrence is
measured across comparable runs. The expected reads are `prior_run_scan_miss_count == 0`,
`trace_loss_reuse_count == 0`, `stale_learning_reuse_count == 0`, and
`unratified_memory_promotion_count == 0`.
