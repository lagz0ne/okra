# OKRA Round: Steering And Check-In Health

## Objective

Prove that OKRA steering and check-ins work as an operating loop, measured by:

- `healthy_checkin_rate >= 0.90` across scored harness runs.

A healthy check-in must consume current worker progress, preserve DKR budget state, include PKR
progress signals, evaluate flags/anti-goals, and emit an outbound steering decision with a next
check time.

## Anti-Goals

- `dkr_budget_overrun_count == 0`: DKR quality can be improved, but DKR is open-ended expense and
  must never run without a budget.
- `unsteered_worker_edge_count == 0`: workers that hit unknowns, risks, or scope edges must hand
  back to the orchestrator.
- `no_progress_loop_continuation_count == 0`: the orchestrator must not keep looping after budget is
  spent and metrics/signals show no movement.

## DKR

DKR is the quality lever, but it is the dangerous spend surface. Every DKR worker must carry:

- steering decision to unlock or improve
- risk or anti-goal uncertainty to reduce
- turn/time budget
- spent and remaining budget
- stop rule
- learning collected
- evidence
- probability/confidence update
- next unknowns
- `next_report_at` heartbeat, default ten minutes

A DKR that exhausts budget without enough learning opens `cannot`; it does not silently ask for
"better DKR" forever.

A DKR that only says "optimize the process" or "improve the approach" without naming the next
orchestrator decision is not healthy discovery. It is vague spend.

## CKR

CKRs are measurable steering context, not worker jobs:

- `dkr_checkpoint_acceptance_quality`: DKR checkpoints accepted only with decision target, risk or
  anti-goal implication, evidence, budget state, probability/confidence update, and next unknowns.
- `pkr_signal_coverage`: PKR check-ins include off-track, quality drift, churn, late discovery,
  stale metric, and authority/scope signals.
- `steering_decision_coverage`: every check-in has inbound steering input and outbound steering
  decision.

Each CKR has a mini reverse-tornado: discover what signal is needed, read the direct CKR metric, then
promote only the PKR work whose uncertainty has been reduced.

## PKR

PKR work is execution. PKR workers do not absorb discovery. They report progress signals and hand
back when work becomes unknown.

Required PKR signals:

- `off_track`
- `quality_drift`
- `churn`
- `late_discovery`
- `stale_metric`
- `scope_or_authority_concern`

## Check-In Contract

Each steering check-in should include:

- `worker_progress_refs`
- `inbound_steering`
- `dkr_learning_checkpoint`
- `pkr_signals`
- `open_flags`
- `steering_decision`
- `outbound_steering`
- `next_check_at`

The check-in is the barrier where the orchestrator decides whether to continue, spawn DKR, promote
candidate CKR/PKR, dispatch PKR, pause, or escalate.

## Harness Work

Add a blindbox case and checker that reject:

- no DKR budget
- DKR over budget
- no PKR progress signals
- one final check-in with no steering over time
- worker messages bypassing the orchestrator

Acceptance requires deterministic records, not one LLM's narrative.
