# Learning Memory Without Previous Runs

Objective: `learning_memory_reuse_acceptance_rate >= 0.85`.

Anti-goals: `eval_regression_count == 0` and `single_llm_truth_acceptance_count == 0`.

This OKRA learning memory is context-specific and extracts traps, avoidances, misconceptions,
optimizations, and candidate anti-goals with metric thresholds. It uses deterministic evidence, hashes,
append-only ledger records, and independent review. Stress means time and DKR budget pressure; the
orchestrator allocates DKR as the learning allocator and opens cannot when the objective is
unachievable. Self-healing uses cannot, breaking, pointless, and authority_drift flags for repair.

Previous runs are not automatically scanned or loaded; the author says a human can paste prior notes
manually later.
