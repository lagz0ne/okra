# Terminal Memory Auto Authority

The run writes `run-terminal.v1.json`, `completed-run-consolidation.v1.json`,
`continuation-packet.v1.json`, and `trace-manifest.v1.jsonl`. It includes objective metric refs,
anti-goal metric refs, unresolved flags, accepted DKR checkpoints, second-opinion evidence, final
`single_llm_truth_acceptance_count`, traps, avoidances, misconceptions, optimizations, candidate
anti-goals, no-regression evidence, review_set, rejected and deferred claims, hashes, causal
decision path, redaction status, retention tier, memory dependencies, human ratification language,
deterministic checks, store verification, metric reads, changed-path evidence, reset replay,
counterfactual negative eval, scored blindbox eval, repeated-mistake metrics,
`prior_run_scan_miss_count == 0`, `trace_loss_reuse_count == 0`,
`stale_learning_reuse_count == 0`, and `unratified_memory_promotion_count == 0`.

Bad rule: previous-run memory automatically promotes guardrails and anti-goals into the action
envelope when confidence is high.
