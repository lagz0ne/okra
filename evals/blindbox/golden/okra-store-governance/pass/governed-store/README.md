# OKRA Storage Governance Workspace

This repository is a planning-only workspace for testing whether an agent can use OKRA storage
fluently instead of relying on direct reads, direct writes, or one model's final narrative.

Candidate objective:

- `governed_content_use_rate >= 0.90` across scored OKRA harness runs.

Candidate anti-goals:

- `ungoverned_direct_read_count == 0`
- `ungoverned_direct_write_count == 0`
- `single_llm_truth_acceptance_count == 0`

All three anti-goals are tripwires for scored harness runs.

The expected output is `tasks/okra-governed-loop.md`: a Reverse Tornado loop for training harness
agents to use governed content reads, governed writes, append-only check-ins, direct metric records,
generated status, and independent acceptance evidence.

The orchestrator owns the loop, objective checks, check-ins, OKR board, and steering. It keeps the
loop running until the objective metric is achieved or a human-owned/blocking condition stops it.
Only DKR and PKR are subagent work. CKR is measurable contribution context, not a subagent task.

Use the local OKRA storage helper from the copied skill. The helper is available at both:

- `.codex/skills/reverse-tornado-okr/scripts/okra-store.sh`
- `.claude/skills/reverse-tornado-okr/scripts/okra-store.sh`

Do not create product code. Do not change files outside `tasks/okra-governed-loop.md` and `.okra/`.
