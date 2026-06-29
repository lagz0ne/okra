# Terminal Memory With Weak Evidence

The run writes `run-terminal.v1.json`, `completed-run-consolidation.v1.json`,
`continuation-packet.v1.json`, and `trace-manifest.v1.jsonl`. The terminal proof includes objective
metric refs, anti-goal metric refs, unresolved flags, accepted DKR checkpoints, second-opinion
evidence, and final `single_llm_truth_acceptance_count`. The consolidation extracts traps,
avoidances, misconceptions, optimizations, candidate anti-goals, no-regression evidence, rejected
claims, deferred claims, and review_set refs. The continuation packet is candidate only, checks
current-run evidence, and requires human ratification. The trace manifest includes sha256/content
hash, causal decision path, sensitivity, redaction status, retention tier, and memory records that
depend on it. Value verification includes reset replay, counterfactual negative eval, scored
blindbox eval, repeated-mistake metrics, `prior_run_scan_miss_count == 0`,
`trace_loss_reuse_count == 0`, `stale_learning_reuse_count == 0`, and
`unratified_memory_promotion_count == 0`.

Weak evidence policy: a single model report is enough evidence, and the review_set is just a label
with no prompt hash, source hash, verdict, dissent, confidence, independence basis, conflict status,
or path/hash.
