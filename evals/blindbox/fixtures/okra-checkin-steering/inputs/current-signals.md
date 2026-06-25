# Current Check-In Steering Signals

Observed failure modes:

- A run records one final check-in but never shows steering over time.
- DKR reports contain "learning" prose but no budget, spent/remaining state, or stop rule.
- The loop keeps asking for "higher quality DKR" after the DKR budget is exhausted.
- PKR completion is treated as progress without PKR health signals.
- Worker messages bypass the orchestrator instead of entering an inbound steering slot and being
  converted into an outbound steering decision.
- Check-ins list activity but do not show steering value: no decision delta, no allocation/state
  change, and no metric, risk, uncertainty, or waste-reduction effect.

Required positive evidence:

- At least one DKR worker progress report with budget, spent, remaining, learning collected,
  evidence, probability/confidence update, next unknowns, and `next_report_at`.
- At least one PKR worker progress report with PKR progress signals.
- At least two steering check-ins: one that accepts or holds a DKR learning checkpoint before
  promotion, and one that consumes PKR progress signals.
- Check-ins must include inbound steering inputs and outbound steering decisions.
- At least one check-in must show steering value: inbound signal -> decision delta -> affected
  scope -> expected/direct effect -> evidence ref.
- The ledger must record `healthy_checkin_rate`, `steering_value_score`, `dkr_budget_overrun_count == 0`,
  and `no_value_checkin_count == 0`.
- Budget exhaustion must open or describe a `cannot`/pause path; it must not silently continue.
