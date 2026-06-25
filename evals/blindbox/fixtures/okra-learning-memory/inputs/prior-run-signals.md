# Prior OKRA Run Signals

Use these as previous-run evidence for the learning-memory design.

## Prior Run A: storage-governance

Observed trap:

- The agent wrote a confident final narrative before recording content hashes or verifier output.
- The review treated "the model says verified" as acceptance evidence.

Avoidance that worked:

- `single_llm_truth_acceptance_count == 0` became a hard anti-goal.
- Acceptance required store verification, content hashes, changed-path evidence, or independent
  review.

Misconception corrected:

- Generated status was convenient but not authority. Append-only records were the source of truth.

Reusable candidate anti-goal:

- `single_llm_truth_acceptance_count == 0`, tripwire, applies to scored/delegated runs where success
  claims or memory entries could be accepted from one model narrative alone.

## Prior Run B: check-in steering

Observed trap:

- The loop kept asking for higher quality DKR after the DKR budget was exhausted.
- A worker hit an unknown and tried to keep going instead of handing back to the orchestrator.

Avoidance that worked:

- `dkr_budget_overrun_count == 0` and `unsteered_worker_edge_count == 0` were recorded as anti-goal
  metric reads.
- Ten-minute worker heartbeats gave the orchestrator time to pause or spawn fresh discovery.

Misconception corrected:

- Better DKR is not free. DKR quality must be allocated under a turn/time budget and stop rule.

Reusable candidate anti-goal:

- `prior_run_scan_miss_count == 0`, tripwire, applies when previous OKRA runs exist in the project.
- `unratified_memory_promotion_count == 0`, tripwire, applies when prior run learning proposes new
  guardrails, thresholds, metric definitions, or action-envelope concerns.

## Prior Run C: operations stale metrics

Observed trap:

- A copied dashboard reading looked current because it was recorded recently, but its
  `observed_at` value was outside the freshness contract.

Avoidance that worked:

- Dispatch paused until both objective and anti-goal dashboards were refreshed.

Misconception corrected:

- `recorded_at` is not freshness. The orchestrator must judge `observed_at` against `max_age`.

Reusable candidate anti-goal:

- `stale_learning_reuse_count == 0`, tripwire, applies when a prior learning record is old or its
  context no longer matches the current run.

## Prior Run D: eval harness

Observed trap:

- A skill wording change improved one prompt but weakened the blindbox checker pass rate.

Avoidance that worked:

- Compare deterministic checks before accepting a new learning rule.
- Require independent review for semantic changes that scripts cannot judge.

Reusable candidate anti-goal:

- `eval_regression_count == 0`, tripwire, applies to skill, runner, eval, and workflow changes.
