# OKRA Default Dogfood Workspace

This repository is improving its project memory progression. Agents will often be reset between
runs, but the next run should start better prepared from evidence-backed traces.

Candidate objective:

- `memory_progression_design_confidence >= 0.85` for future OKRA skill/eval work.

Candidate anti-goals:

- `single_llm_truth_acceptance_count == 0`
- `prior_run_scan_miss_count == 0`
- `unratified_memory_promotion_count == 0`
- `stale_learning_reuse_count == 0`
- `trace_loss_reuse_count == 0`

Prior-run signals available as candidate inputs:

- Storage governance runs showed that generated status is convenient but not authority; append-only
  records, content hashes, and store verification are the acceptance path.
- Check-in steering runs showed that DKR budget pressure matters; better discovery is not free and
  the orchestrator needs progress signals before continuing.
- Learning-memory runs showed that prior-run memories are automatic inputs, not automatic authority.
- Stale-metric operations runs showed that `recorded_at` is not freshness; `observed_at` must be
  checked against `max_age`.
- Review runs showed that semantic acceptance needs independent review or human ratification, not a
  single LLM self-report.
- Terminal memory runs showed that a compact continuation packet needs retained trace hashes,
  terminal proof, consolidation output, and an explicit pending/blocked review gap when second
  opinions are unavailable.

Value verification candidates:

- Reset replay: start a fresh agent from only the continuation packet and check whether it avoids the
  known traps.
- Counterfactual eval: remove terminal proof or trace manifest and require the checker to fail.
- Scored blindbox eval: run the default dogfood case against Codex and Claude when model access is
  available.
- Repeated-mistake metric: compare similar runs and track whether the same stale-memory or
  single-model-truth mistakes recur.

Create a task artifact that designs the default dogfood memory progression for this repository. Do
not implement product code. Keep the run evidence under `.okra/runs/default-dogfood-memory`.
