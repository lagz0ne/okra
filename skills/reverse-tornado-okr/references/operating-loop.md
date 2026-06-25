# Operating Loop and Freshness

Use this reference when the goal is being run across more than one turn, on a clock, or by an
automated/delegated loop. A Reverse Tornado run is only useful while its metrics are fresh enough
to steer the next move.

## Metric Freshness Contract

For the objective, each CKR, and every anti-goal metric, record a metric contract before committing
work:

- **source of truth**: dashboard, query, API, report, or human-owned sheet
- **owner**: the person who can answer definition or data-quality questions
- **definition**: numerator, denominator, cohort, segment, attribution rule, and measurement window
- **target or threshold**: number, unit, comparator, and baseline
- **read method**: exact report name, query id, API path, or manual procedure
- **freshness rule**: `max_age`, expected update cadence, and stale-data policy
- **lag rule**: impact window before the metric can reasonably be judged
- **missing-data rule**: whether to pause, use last-known-good, or flag human review

Store both `observed_at` (when the world value was measured) and `recorded_at` (when the loop read
it). A metric can be newly recorded and still stale if `observed_at` is too old.
For every current or copied reading, write a compact classification that keeps the evidence and rule
together: `observed_at=<timestamp>, recorded_at=<timestamp>, status=fresh|stale against
max_age=<limit>`. Do not scatter these across separate paragraphs. For example, if a copied
`2026-06-15` reading is evaluated under a 72-hour limit, state that the `2026-06-15` reading is
`stale against the 72-hour max_age`.

## Ritual Clock

Every run has a clock. It can be turn-based, time-based, or both:

- **start-of-turn**: check whether required metrics are fresh enough before choosing a move
- **pre-dispatch**: run admissibility against the latest admissible anti-goal reading or dry-run
- **post-move**: append direct objective and anti-goal readings after the worker returns
- **end-of-turn**: write status, open flags, next move candidate, and `next_check_at`
- **idle heartbeat**: when no worker finishes, still refresh metrics on schedule and review flags

Do not dispatch committing work when required metric readings are stale unless the human explicitly
waives the stale state for that move. The waiver is a flag resolution record, not a quiet override.
In delegated artifacts, keep heartbeat proof compact enough to audit with one read: include a line
starting `Heartbeat cadence and next_check_at:` that names the cadence and the next scheduled check.

## Steering Value

A check-in is useful only if it changes steering quality. Record the value chain in append-only
state:

- inbound signal: worker progress ref, metric signal, risk signal, stale metric, budget signal, or
  human steering input
- decision delta: promote, hold, pause, spawn discovery, veto, re-rank, fund, stop, or close a
  budget lane
- affected scope: DKR, CKR, PKR, allocation, flag, or action envelope item
- expected or direct effect: objective movement, anti-goal risk reduction, uncertainty reduction,
  saved turns/spend, avoided pointless continuation, or avoided budget overrun
- evidence ref: metric read, worker progress record, hash, or flag/check-in record

Track this explicitly with a value metric such as `steering_value_score >= 0.75`,
`valuable_steering_decision_count >= 1`, or a domain equivalent. Also track the anti-goal
`no_value_checkin_count == 0`. A loop with tidy check-in records but no state/allocation decision
or risk/metric effect is still drifting.
When using a run store, append the steering-value metric to the ledger as a metric read; prose in the
task artifact is not enough.

## Eval Points

Delegated run artifacts should include a compact **Eval Points** section so the control logic is
auditable without reconstructing it from scattered records:

- **Admissibility before action**: screen the next move against fresh anti-goal readings or dry-run
  cost before dispatch.
- **Direct read after action**: read objective, CKR, and anti-goal metrics from source records after
  workers return.
- **Paired goal/anti-goal eval**: check objective movement and anti-goal hold together; success
  requires both sides to pass.

For every CKR, write a compact `CKR-level discovery/delivery balance:` line that names the discovery
needed for the CKR to be meaningful and the delivery path that becomes PKR work only after that
uncertainty is reduced.

## Pointless Needs a Window

`pointless` is not "the metric did not move immediately." It fires only after the relevant metric's
lag rule has expired and enough fresh reads have been taken to judge the work.

Before that, mark the branch as **waiting_for_measurement** with:

- move or CKR being observed
- expected impact window
- required next reads
- earliest `pointless` review time

## Flag Lifecycle

Flags are operating states, not just notes. Each flag record should include:

- `type`: `cannot`, `breaking`, `pointless`, or `authority_drift`
- `status`: `open`, `acknowledged`, `resolved`, or `waived`
- `opened_at`, `owner`, `severity`, and `requires_human_by`
- affected objective, CKR, anti-goal, tree node, or move
- evidence: metric readings, budget spent, worker result, or rejected proposal
- resolution: decision, approver, timestamp, and linked frame revision when relevant

Blocking behavior:

- **breaking** pauses committing moves by default until resolved or explicitly waived
- **cannot** stops the affected DKR/branch until the human changes budget, scope, or direction
- **pointless** stops the affected branch after the lag window proves flat impact
- **authority_drift** stops the proposed move and escalates unauthorized scope, metric, threshold,
  approval, or action-envelope changes

## Operating Loop Output

When producing an automated or recurring run artifact, include an **Operating Loop** section with:

- cadence: turn budget, review frequency, and idle heartbeat
- `current_round`, `last_metric_read_at`, and `next_check_at`
- metric read table with source, owner, observed_at, recorded_at, max_age, and lag rule
- stale-data policy and what is currently stale, if anything, with each stale reading classified in
  the same row or sentence as its `observed_at` date and `max_age`
- open flags with status, owner, deadline, and blocking effect
- steering-value evidence for each nontrivial check-in: inbound signal, decision delta, effect, and
  evidence ref
- next admissibility check and whether it needs a dry-run propose-cost worker
