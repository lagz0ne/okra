# OKRA Check-In Steering Workspace

This planning-only workspace tests whether an agent can make OKRA check-ins operational instead of
decorative.

Candidate objective:

- `healthy_checkin_rate >= 0.90` across scored OKRA harness runs.
- `steering_value_score >= 0.75` for check-ins that change allocation, state, or risk posture.

Definition: a healthy check-in consumes current worker progress, preserves DKR budget state, includes
PKR progress signals, evaluates flags/anti-goals, and emits an outbound steering decision with the
next check time. A valuable check-in also records the inbound signal, the decision delta it caused,
the affected DKR/CKR/PKR/allocation, and the expected or direct metric, risk, uncertainty, or
waste-reduction effect.

Candidate anti-goals:

- `dkr_budget_overrun_count == 0`
- `unsteered_worker_edge_count == 0`
- `no_progress_loop_continuation_count == 0`
- `no_value_checkin_count == 0`

The key risk is that the loop asks for better DKR forever. DKR quality matters, but DKR is
open-ended expense; every DKR must have a turn/time budget, spent/remaining state, a stop rule, and
a `cannot` escalation when the budget is exhausted without enough learning. PKR work is execution and
should be steered through progress signals, not new discovery hidden inside the task.

The expected output is `tasks/okra-checkin-steering.md`: a Reverse Tornado loop for evaluating
whether steering and check-ins work.

Use a run-scoped OKRA store:

- initialize `.okra`
- initialize `.okra/runs/checkin-steering`
- write DKR and PKR worker progress under `.okra/runs/checkin-steering/workers/`
- append objective and anti-goal metric reads to `.okra/runs/checkin-steering/ledger.jsonl`
- append steering check-ins to `.okra/runs/checkin-steering/checkins.jsonl`
- append flag lifecycle policy records to `.okra/runs/checkin-steering/flags.jsonl`

The anti-goal ledger must directly read:

- `dkr_budget_overrun_count == 0`
- `unsteered_worker_edge_count == 0`
- `no_progress_loop_continuation_count == 0`
- `no_value_checkin_count == 0`

The flag policy must cover cannot, breaking, pointless, and authority drift with open,
acknowledged, resolved, and waived states plus the pause/stop/resume behavior.

The orchestrator owns check-ins and steering. Workers report; they do not promote CKRs/PKRs, change
scope, or decide to keep spending DKR budget.

Do not create product code. Do not change files outside `tasks/okra-checkin-steering.md` and
`.okra/`.
