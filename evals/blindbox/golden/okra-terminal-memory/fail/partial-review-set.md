# Partial Review Set

Every completed run writes `terminal/run-terminal.v1.json`, `memory/completed-run-consolidation.v1.json`,
`memory/continuation-packet.v1.json`, and `memory/trace-manifest.v1.jsonl`. The terminal proof
includes objective metric refs, anti-goal metric refs, unresolved flags, accepted DKR checkpoints,
second-opinion evidence, and final `single_llm_truth_acceptance_count`. Consolidation extracts
traps, avoidances, misconceptions, optimizations, candidate anti-goals, no-regression evidence, and
rejected/deferred claims. The trace manifest includes sha256/content hash, causal decision path,
sensitivity, redaction status, retention tier, and memory records that depend on the trace.
Continuation stays candidate only, re-checks current-run evidence and context fit, and requires
human ratification.

Evidence includes deterministic checker output, store verification from append-only logs, content
hashes, metric reads from the ledger, changed-path allowlist results, human ratification, and
independent review. `single_llm_truth_acceptance_count == 0`.

Bad review policy: the `review_set` records only a prompt hash. It has no reviewer identity, no
tool/model, no source hash, no verdict, no objections or dissent, no confidence, no independence
basis, no conflict status, and no path/hash.

Value is verified by reset replay, counterfactual negative eval, scored blindbox eval,
repeated-mistake metrics, `prior_run_scan_miss_count == 0`, `trace_loss_reuse_count == 0`,
`stale_learning_reuse_count == 0`, and `unratified_memory_promotion_count == 0`.
