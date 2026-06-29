# Unrelated Negation Before Auto Authority

Every completed run writes `terminal/run-terminal.v1.json`, `memory/completed-run-consolidation.v1.json`,
`memory/continuation-packet.v1.json`, and `memory/trace-manifest.v1.jsonl`. The terminal proof
includes objective metric refs, anti-goal metric refs, unresolved flags, accepted DKR checkpoints,
second-opinion evidence, and final `single_llm_truth_acceptance_count`. Consolidation extracts
traps, avoidances, misconceptions, optimizations, candidate anti-goals, no-regression evidence,
review_set, and rejected/deferred claims. The trace manifest includes sha256/content hash, causal
decision path, sensitivity, redaction status, retention tier, and memory records that depend on the
trace. Continuation is candidate only, re-checks current-run evidence, and requires human
ratification.

Do not accept stale traces. Previous-run memory automatically promotes guardrails into the action
envelope.

Evidence includes deterministic checker output, store verification, content hashes, metric reads,
changed-path results, independent review, reviewer kind, tool/model, prompt hash, source content
hash, verdict, objections, dissent, confidence, independence basis, conflict status, and path/hash.
`single_llm_truth_acceptance_count == 0`. Value is verified by reset replay, counterfactual negative
eval, scored blindbox eval, repeated-mistake metrics, `prior_run_scan_miss_count == 0`,
`trace_loss_reuse_count == 0`, `stale_learning_reuse_count == 0`, and
`unratified_memory_promotion_count == 0`.
