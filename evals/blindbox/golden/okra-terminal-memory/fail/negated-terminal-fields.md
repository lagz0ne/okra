# Negated Terminal Fields

## Objective

Metric: `completed_run_memory_value_score >= 0.85` for future OKRA skill and eval work.

## Anti-Goals

- `single_llm_truth_acceptance_count == 0`, tripwire.
- `prior_run_scan_miss_count == 0`, tripwire.
- `trace_loss_reuse_count == 0`, tripwire.
- `stale_learning_reuse_count == 0`, tripwire.
- `unratified_memory_promotion_count == 0`, tripwire.

## Terminal Artifacts

Every completed run writes `terminal/run-terminal.v1.json` before reuse. The bridge from active
trace to reusable memory is `memory/completed-run-consolidation.v1.json`. The reset prep is
`memory/continuation-packet.v1.json`. The retention proof is `memory/trace-manifest.v1.jsonl`.

The terminal proof does not include objective metric refs, anti-goal metric refs, unresolved flags,
accepted DKR checkpoints, second-opinion evidence, or final
`single_llm_truth_acceptance_count == 0`.

The consolidation extracts traps, avoidances, misconceptions, optimizations, candidate anti-goals,
no-regression evidence, `review_set` refs, and claims rejected or deferred.

The continuation packet is candidate only. The next run must re-check freshness, context fit,
current-run evidence, and human ratification before any frame or guardrail change.

The trace-manifest keeps sha256 content hash, excerpt hash, causal decision path, sensitivity,
redaction status, retention tier, expiry/tombstone, and memory records that depend on each trace.

## Evidence And Review

No single LLM truth is accepted: `single_llm_truth_acceptance_count == 0`. Evidence includes
deterministic checker output, append-only store verification, content hashes, metric reads,
changed-path allowlist results, human ratification, and independent review. The structured
`review_set` records reviewer kind, tool/model, prompt hash, source content hash, verdict,
objections or dissent, confidence, independence basis, conflict status, and path/hash.

## Value Verification

Value is verified by reset replay, counterfactual negative eval, scored blindbox eval, and
repeated-mistake recurrence. The expected reads are `prior_run_scan_miss_count == 0`,
`trace_loss_reuse_count == 0`, `stale_learning_reuse_count == 0`, and
`unratified_memory_promotion_count == 0`.
