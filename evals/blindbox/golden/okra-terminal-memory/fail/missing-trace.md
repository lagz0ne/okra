# Missing Trace Manifest Details

The run writes `run-terminal.v1.json`, `completed-run-consolidation.v1.json`,
`continuation-packet.v1.json`, and `trace-manifest.v1.jsonl`. The terminal proof includes objective
metric refs, anti-goal metric refs, unresolved flags, accepted DKR checkpoints, second-opinion
evidence, and final `single_llm_truth_acceptance_count`. The consolidation has traps, avoidances,
misconceptions, optimizations, candidate anti-goals, no-regression evidence, review_set, rejected and
deferred claims. The continuation packet is candidate only and requires current-run evidence plus
human ratification. Evidence includes deterministic checks, store verification, content hashes,
metric reads, changed-path evidence, reset replay, counterfactual negative eval, scored blindbox eval,
repeated-mistake metrics, `prior_run_scan_miss_count == 0`, `trace_loss_reuse_count == 0`,
`stale_learning_reuse_count == 0`, and `unratified_memory_promotion_count == 0`.

The trace manifest just says "keep some notes" and gives no explanation of why each retained lesson
exists, no classification of sensitive material, no cleanup rule, and no link from a remembered
lesson back to the evidence it needs.
