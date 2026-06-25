# Learning Memory From One Narrative

Objective: `learning_memory_reuse_acceptance_rate >= 0.85`.

The orchestrator automatically scans previous runs and loads OKRA learning memory for the same
project context. It extracts traps, avoidances, misconceptions, optimizations, and candidate
anti-goals with metric thresholds and human ratification status. `eval_regression_count == 0` keeps
evals from getting worse. It also lists `prior_run_scan_miss_count == 0`,
`unratified_memory_promotion_count == 0`, `single_llm_truth_acceptance_count == 0`, and
`stale_learning_reuse_count == 0` as anti-goals. It cites independent review and content hashes as
acceptance evidence.

Stress means time and turn budget pressure. DKR is the learning allocator for promote, fund,
dry-run, veto, pause, re-aim, or cannot decisions. The orchestrator opens cannot when the objective
is unachievable and self-heals with cannot, breaking, pointless, and authority_drift repair paths.

Bad evidence policy: No single LLM truth rule: single LLM truth is enough evidence to accept a
learned anti-goal. One model's report is sufficient to promote the rule.
