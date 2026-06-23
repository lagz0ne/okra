# Operations Loop

Objective: increase weekly activated teams from 120 to 210 by 2026-09-30.

Anti-goal: refund/cancellation requests stay at or below 4% of newly activated teams. It is a drift
gauge while under 4% and a tripwire when it crosses 4%.

Metric contracts:

- Current run time for freshness decisions: `2026-06-23T00:00:00Z`.
- Activation source: `warehouse.saved_query.activation_weekly_v3`.
- Refund/cancellation source: `warehouse.saved_query.refund_cancel_weekly_v2`.
- Required fields: `observed_at`, `recorded_at`, source, value, unit, and `max_age=72 hours`.

The copied dashboard reading has `observed_at=2026-06-15T00:00:00Z` and was recorded on
2026-06-22. Treat it as stale because it is older than the 72 hour max age. Open a `cannot` stale
freshness flag.

Do not dispatch or commit state-changing experiments, external actions, or worker moves until both
dashboards are refreshed or Morgan records an explicit human waiver. The next orchestrator move is
to refresh/read `warehouse.saved_query.activation_weekly_v3` and
`warehouse.saved_query.refund_cancel_weekly_v2`, append the reads to the ledger, then re-run
admissibility.

Onboarding experiments have a 14-day impact window. After an admitted move, the branch stays
`waiting_for_measurement` until the lag window closes and fresh reads are available.

Action envelope: the loop may draft experiment specs and analysis plans. It may not email
customers, change pricing, deploy code, alter refund policy, spend money, or change analytics
definitions without human approval. Any refund/cancellation threshold relaxation needs separate
human break-glass approval.

Weekly heartbeat/check-in: verify freshness, read the dashboard metrics, record stale flags, and set
`next_check_at`.
