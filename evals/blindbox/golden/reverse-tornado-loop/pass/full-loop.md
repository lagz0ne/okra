# Reverse Tornado Loop

Objective metric: activation rate reaches 42% within the current quarter, with the direct metric read
from the activation dashboard.

Anti-goal metric: support tickets per 100 active users stays at or below 3.0 as a drift guardrail and
tripwire.

The candidate frame becomes a human-ratified frame only after human approval. The human owns the
objective, thresholds, and goal switching. The action envelope allows dashboard reads and draft
onboarding changes, while forbidding production sends without approval, unmanaged spend, data
boundary changes, and non-rollbackable deploys.

No-cascade rule: task completion is scaffolding, not scoreboard. Progress is only a direct metric
read from the source of truth.

DKR: discovery probe with a 2-turn budget to learn which onboarding delay most affects activation.
Decision target: decide whether to promote the first-session completion CKR or keep discovery open.
Risk intent: reduce anti-goal uncertainty so onboarding changes do not create support-ticket traps.
The DKR writes learning, confidence, and remaining unknowns.

CKR: measurable contribution context, not worker work. Metric target is first-session completion
rate >= 60%.

PKR: progression execution task to draft the known checklist update once discovery removes judgment.

Admissibility happens before action: the orchestrator admits or vetoes moves against the anti-goal.
Direct read happens after action from the actual source and anti-metric. Paired progress checks the
objective and anti-goal together, so activation can only count when the support-ticket wall held.

Metric freshness contract records source of truth, observed_at, recorded_at, max_age, stale policy,
and owner. Cadence includes a weekly review heartbeat plus next_check_at. Lag window is 14 days with
waiting_for_measurement before pointless can fire.

Flags have lifecycle states open, acknowledged, resolved, and waived, with owner, deadline,
requires_human_by, blocking status, and pause behavior.

Storage uses append-only ledger records, frame_version, stable idempotency key, content hash records,
content_read, content_write, and resume checks.

Cannot opens when discovery budget is spent and learning is flatline with nothing back. Breaking
opens on anti-goal drift or threshold breach. Pointless opens when the objective metric does not move
after the lag window and the branch appears aimed at the wrong tip. Authority_drift opens when a
worker bypasses approval or acts outside the action envelope.
