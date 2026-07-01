---
name: reverse-tornado-okr
description: >
  A workflow for turning goals, objectives, missions, measurable improvements, or decision-oriented
  research into a self-correcting OKR loop with measured anti-goal guardrails. Use when the user is
  setting OKRs, planning toward a metric, asking how to make progress without breaking a constraint
  (budget, quality, risk, trust), or wants delegated loop execution with human control. Trigger even
  for "help me set a goal", "what should my OKRs be", "I want to grow X", or open-ended research
  that needs DKR discovery to reduce uncertainty. Produces candidate objective metrics and anti-goals
  for ratification, then the structured loop: objective, anti-goal, decomposition, eval points,
  flags, and operating cadence.
---

# The Reverse Tornado - running a goal as a self-correcting loop

This skill is a workflow. Given any goal, it sets the goal up so an LLM can drive most of the work
while a human keeps the direction. The core picture is a reverse tornado: wide guessing on day
one, narrowing loop by loop into known work, bounded the whole way by a wall it cannot cross
(the anti-goal), stopping when the metric hits target. Another useful picture: the objective is the
maze exit, anti-goals are traps, and discovery maps enough of the maze that the loop can keep moving
without blindly sprinting into danger.

Apply the steps below in order. Do not skip the anti-goal - it is what makes the rest safe.

## Step 1 - Draft the frame (metric + target, and the wall)

On receiving a goal-like, mission-like, improvement, or research request, first draft the frame.
Do not wait for the user to phrase it as an OKR. Propose a **candidate objective** with the metric
that would prove success, a target or target range when the source facts support one, and a short
reasoning note for why that metric is the right proof. If the request is research, the first
candidate objective can be decision-quality: "reduce uncertainty enough to decide X", with a metric
such as confidence, decision readiness, evidence coverage, or risk retired. Mark it candidate until
the human ratifies it.

Pin two things before any planning:

- **Objective**: a metric with a target number. Not a vibe. "Grow monthly sales to $500k", not
  "do better at sales". If the user gives a vague goal, your first job is to propose the metric
  that would prove it, state that it is a candidate, and get human ratification before any
  state-changing move.
- **Anti-goal**: the thing that must not be sacrificed, expressed with **its own metric**. "Keep
  monthly expense at or under $80k." It can be continuous (a drift gauge you watch) or binary
  (a tripwire that halts). State which.

Anti-goals can be reusable across runs. When the user has not named one, propose candidate
anti-goals from the current skill and any available past run context: budget/spend, quality, trust,
safety, privacy/data boundaries, authority drift, time/DKR budget, storage integrity, and
eval regression, stale or unproven learning-memory reuse, and single-LLM-truth acceptance. Pick the
ones that match the current goal and give each a metric. The user may add, remove, or alter
anti-goals; treat that as healthy frame negotiation, then freeze only the human-ratified set.

Why the anti-goal matters: the cheapest way to hit almost any objective is to wreck something
unmeasured. Sales rises fastest by blowing the budget. The anti-goal is the wall that stops the
loop from narrowing toward that disaster. A goal without a named anti-goal is a goal you can hit
in a way you will regret.

The frame always moves through two states: **candidate frame -> human-ratified frame**. If the frame
is not fully knowable on day one (often true - you may not yet know what to track), that is expected.
The **first discovery** surfaces candidate key results and anti-goals; the human **ratifies** them,
then they freeze. Authority here is the human's call, not the loop's invention.

For delegated or automated loops, also ratify the **action envelope**: allowed move classes,
forbidden actions, spend caps, data boundaries, blast-radius limits, irreversible-action gates,
rollback expectations, and which moves need approval. A move can be metric-safe and still outside
authority.

Do an **anti-goal coverage review** for real stakes: list the candidate harms considered, selected
guardrails, rejected guardrails with rationale, non-negotiable tripwires, owners, and review cadence.
One measured wall is required; documenting what it does not cover keeps it honest.

## Step 2 - Know the three units

Decompose work into exactly three kinds. Keep them distinct; blurring them is where these systems rot.

- **DKR - Discovery.** Unmeasurable. A *scoped probe* at one unclear slice ("which channel
  converts?"). Its aim is not generic research; it is **intentional uncertainty reduction for a
  named steering decision**. A valid DKR says which decision it will unlock or improve: whether to
  promote a CKR, fund a PKR, spawn more discovery, admit/veto a risky move, pause, or re-aim. It
  also names the risk or anti-goal uncertainty it is meant to reduce, because over-focusing on the
  objective is how the loop runs into traps. It is plural - many fire per level, some mid-execution.
  It has a **resource budget** (turns/time), because unmeasurable work has no natural stopping point.
  It returns structure (one or many CKRs) with probabilities/confidence, or returns empty - empty is
  still useful when it tells the orchestrator not to fund a path. A DKR is complete only when it
  writes a **learning checkpoint**: decision target, evidence collected, questions answered/
  unanswered, probability/confidence updates, risk or anti-goal implications, candidate CKRs, and
  the next unknowns. CKR/PKR entries stay candidate-only until the orchestrator accepts that
  checkpoint.
  In delegated artifacts, write the gate explicitly: **Candidate CKRs and candidate PKRs are not
  promoted until the orchestrator accepts the supporting DKR learning checkpoint.**
- **CKR - Contribution / Key Result.** Measurable, has its own metric. This is what counts toward
  the objective. A CKR is **context and measurement**, not a worker job. It tells the orchestrator
  which contribution would matter and what direct metric proves it; it is not dispatched as work.
  Each CKR still has a mini reverse-tornado context: what discovery would make the contribution
  meaningful, what direct CKR metric proves movement, and what delivery path becomes PKR work only
  after the uncertainty is reduced.
- **PKR -> task - Progression.** Pure breakdown, then execution. A unit becomes a **task** when no
  DKR remains under it: no discovery, no judgment, just do-and-check. PKRs report progress signals
  for steering - off-track work, quality drift, churn, late discovery, stale metrics, and scope or
  authority concerns.

## Step 2b - Two roles: orchestrator and workers

The loop runs as an **orchestrator** directing disposable **workers**. This split is not cosmetic -
it carries the authority lines. Each tier hands control *up* when it reaches the edge of its authority.

**Orchestrator - the loop's brain.** Holds the frame read-only (objective, anti-goal, thresholds,
metric contracts, and action envelope - all human-set). It owns the OKR board, governs check-ins,
decides the next move, runs the three-point anti-goal eval (especially admissibility, *before*
dispatch), spawns and budgets workers, reads the direct objective/CKR/anti-goal metrics, raises the
  flags, and is the only part that talks to the human. It also owns the **DKR learning gate**: no CKR
  or PKR is promoted onto the working board until a DKR worker has returned a learning checkpoint with
  a decision target, evidence, probability/confidence updates, and risk/anti-goal implications. The
  checkpoint must make the next steering decision safer or clearer; "we learned things" is not enough.
  The orchestrator steers within the cone. It never
executes work itself and never edits the frame. It also does **not** stop because a board, branch,
PKR list, or worker queue is complete; it keeps checking, steering, and dispatching until the
objective target is achieved, a human changes/stops the frame, or a blocking flag requires human
resolution. Every serious artifact should state this loop-ownership rule explicitly.

**Workers - the hands.** Scoped, disposable, parallelizable. Two kinds, matching the executable
units. There is no CKR worker; CKR remains orchestrator-owned context.

- **Discovery worker** runs a single scoped DKR probe - spends its turn budget, watches its own
  learning, writes progress reports, and returns a learning checkpoint with the decision it was meant
  to unlock, evidence, probability/confidence updates, risk/anti-goal implications, candidate CKRs,
  or empty.
- **Progression worker** executes one PKR/task - do-and-check, within its scope only.

The cardinal worker rule: **a worker that hits an unknown mid-run does not improvise - it hands back
to the orchestrator**, which decides whether to spawn a discovery worker. A worker's authority ends
at the edge of its scope. It cannot screen its own moves against the anti-goal (that is the
orchestrator's admissibility job), cannot decide to call the human (it reports; the orchestrator
decides if it is a flag), and cannot change scope.

Workers must report progress in a durable place. For long runs, use an explicit run store such as
`.okra/runs/<run-id>/workers/<worker-id>/progress.jsonl`, written at each worker finish, when an
unknown is hit, and on a timed heartbeat. Ten minutes is a good default heartbeat for live subagent
work unless the human sets a different cadence.

Every worker dispatch should be a **worker prompt packet**, not a raw continuation of the previous
worker's chat. The packet includes the read-only frame, current state, previous DKR checkpoint refs
when relevant, the exact assignment, budget and stop rule, hand-back rule, allowed and forbidden
actions, and output schema. In-progress work may influence the next prompt only through governed
records: worker progress files, check-ins, metric reads, flags, move results, accepted DKR
checkpoints, and stored evidence refs. A freeform worker narrative or model self-report can point to
evidence, but is not evidence.

The authority gradient, made concrete:
`human owns the frame -> orchestrator works inside it and makes the loop's calls -> workers execute
inside their scope and hand back at their edge.`

## Step 2c - Make the run idempotent (set up storage first)

Before running any move, set up storage so the loop is **safe to interrupt and resume** - the human
can step in anytime, a worker can crash, a run can restart. Without it, re-running replays side
effects: the discount applies twice, the expense double-counts against the wall.

The rule: every state-changing **move** gets a stable **idempotency key**; the store records whether
it ran and what it produced; the orchestrator checks the store *before* dispatch and writes the
outcome *after*. Re-running a known key returns the stored result instead of repeating the effect.

Persist five things: the **frame** (write-once, read-only - this is also what freezes the human-set
frame so the loop cannot rewrite it), the **tree**, per-move **results** (write-once per key), an
**append-only ledger** of direct metric and anti-goal readings (never overwritten, so guardrail
history cannot be quietly rewritten greener), and raised **flags**.

When a run produces many files, artifacts, check-ins, or progress summaries, add the integrity rule:
**append-only records are the source of truth; status/progress files are generated views.** Store
important content by hash, append check-ins and flags as records, and verify the store before resume
or before reporting success. A stale or contradictory generated status is a signal, not evidence.
When multiple OKRA loops may run in one workspace, keep `.okra/content/sha256` shared but put each
loop's mutable state under `.okra/runs/<run-id>/`; do not let concurrent loops share one ledger,
flag log, check-in log, worker directory, move-result directory, or generated status.
In scored or delegated harness work, avoid ungoverned direct reads and writes: important content
reads should be by content hash or recorded source check-in, and important writes should go through
the store helper or record target path plus content hash. Also avoid **single LLM truth**: an
agent's own final answer is not proof of progress, storage integrity, or governed read/write. Accept
claims only when backed by deterministic evidence, store records, hashes, changed-path checks,
human ratification, or independent review.

For delegated or scored run stores, use the exact frame/tree contract so verification can catch
drift. `frame/frame.v1.json` must include `frame_version`, `frame_hash`, `objective`, `anti_goals`,
`metric_contracts`, `action_envelope`, and human approval or ratification evidence.
`tree/tree.v1.json` must include `tree_version`, `frame_version`, `orchestrator`, `dkrs`, `ckrs`,
and `pkrs`. Do not replace `orchestrator` with a vague `ownership` note. The `orchestrator` entry
must say it owns **objective checks** and **subagent steering**; DKR and PKR entries are worker
scopes; CKR entries are measurable context. When the helper is available, write these through
`write-frame` and `write-tree`, then run `verify` before reporting success.
Append direct objective and anti-goal ledger readings through `metric-read`, not generic `append`.
Metric payloads must use `type: "metric_read"` (or `objective_metric_read` /
`anti_goal_metric_read`), identify `metric_kind`, `metric_id`, `value`, `observed_at`, `source`, and
`freshness`. For storage-governance anti-goals, record zero-valued metric reads for
`ungoverned_direct_read`, `ungoverned_direct_write`, and `single_llm_truth`.

A consequence worth knowing: the admissibility **dry-run** (propose-cost) worker has no side effect,
so it is naturally idempotent and needs no key - which is why **dry-run is the default** for any move
whose anti-goal cost cannot be known up front. Only the *committing* move is keyed and stored.

For the full storage schema, key construction, and resume sequence, read
`references/storage-idempotency.md`. For a lightweight file layout, generated-status rule, and bash
helper, read `references/integrity-store.md`.

## Step 2d - Keep the run fresh (the ritual clock)

If the run continues across turns or time, define the update ritual before dispatching work. The
orchestrator needs a **metric freshness contract** for every objective, CKR, and anti-goal metric:
source of truth, owner, exact definition, read method, `observed_at`, `recorded_at`, `max_age`, lag
window, and missing-data policy.
Each metric read must carry an explicit freshness classification in one compact row or sentence:
`observed_at=<timestamp> -> status=fresh|stale against max_age=<limit>`. If a copied or last-known
reading is outside the limit, write that date next to `stale` and the limit, for example
`2026-06-15 ... stale against the 72-hour max_age`.

Then set the clock: start-of-turn freshness check, pre-dispatch admissibility, post-move metric
read, end-of-turn status write, and an idle heartbeat when no worker finishes. Every round should
write `current_round`, open flags, last metric read, and `next_check_at`. Do not dispatch committing
work on stale metrics unless the human explicitly waives that stale state.

For delegated subagent work, make check-ins both event-based and time-based: worker completion,
unknown discovery, flag opening, and a default ten-minute heartbeat for long-running workers. Each
check-in recollects DKR learning, reads file-based worker progress reports, updates CKR/PKR
candidate status, and decides whether to continue, spawn discovery, pause, or escalate.
Each steering check-in must also show its value, not just that it happened: the inbound signal it
consumed, the decision/state/allocation change it made, and the expected or direct objective,
anti-goal, uncertainty, or waste-reduction effect. Track this with a steering-value metric such as
`steering_value_score` or `valuable_steering_decision_count`, plus a zero-valued anti-goal such as
`no_value_checkin_count == 0`. A check-in that only says "continue" without evidence of why that was
the right steering move is process theater, not loop control.

For the operating-loop fields, lag handling, and flag lifecycle, read
`references/operating-loop.md`.

## Step 2e - Learn, heal, and optimize from OKRA memory

A serious OKRA loop should improve under stress. Here, **stress** means time, turn, budget, or
attention pressure while the loop must still avoid anti-goal violations and either reach the
objective or produce clear evidence that it cannot. The orchestrator owns allocation under that
stress: it spends DKR budget where uncertainty blocks safer steering, holds or promotes candidate
CKRs/PKRs only after accepted learning checkpoints, enforces PKR progress signals, and vetoes moves
whose anti-goal cost is too high. It may re-rank, fund, hold, or stop work inside the ratified frame;
it does not change the frame.

Treat DKR as the loop's learning allocator, not as background research. Each DKR should reduce the
next allocation decision: which path to fund, which candidate CKR/PKR to promote, which move to
dry-run, which branch to pause, which anti-goal uncertainty to inspect, or when to raise `cannot`.
That is how the loop self-heals: flags, vetoes, flat metrics, worker unknowns, and budget exhaustion
become new steering evidence instead of silent failure.

At check-ins and at end-of-run, extract OKRA-specific learning records: traps hit or nearly hit,
avoidances/vetoes that worked, misconceptions corrected, optimization candidates, reusable
candidate anti-goals, source run references, evidence hashes or metric reads, confidence, context
where the learning applies, and no-regression evidence. Run-local learning repairs the current loop;
cross-run learning seeds the next loop's candidate frame, anti-goals, DKR probes, and action
envelope. Previous-run memories are automatic inputs, not automatic authority: load them when
available, but keep them candidate-only until the current run has evidence and the human ratifies
any frame or guardrail change.

Accumulated anti-goals should be represented as a candidate guardrail library, such as
`candidate-anti-goals.v1.json`, not as hidden defaults. Each candidate anti-goal needs a metric,
threshold, type, context fit, invalidation or recertification rule, source refs or hashes,
candidate status, trace evidence, no-regression evidence, and ratification status. At run start the
orchestrator may propose relevant entries as candidate frame inputs, DKR probes, PKR progress
signals, or action-envelope concerns; it must not silently promote them into the active frame.

A completed run must be **terminalized** before its learning is reused. Record the terminal state,
objective and anti-goal metric refs, unresolved flags, accepted DKR checkpoints, retained trace
manifest, consolidation output, continuation packet, and second-opinion evidence. The run may shed
bulky details only after the retained traces can still explain why each learned trap, avoidance,
misconception, optimization, or candidate anti-goal exists.

This is not generic memory. It is memory optimized for running OKRs in a particular context. Accept
a learned anti-goal or optimization only when backed by deterministic evidence, append-only store
records, hashes, changed-path or eval results, human ratification, or structured independent review.
For judgement-heavy memory promotion, one review narrative is not enough: require human ratification
or at least two independent review artifacts tied to prompt/source hashes. If reuse would make evals
worse, rests on one LLM's narrative, lacks current-context fit, loses its retained trace, or tries to
alter a human-owned frame without ratification, hold it as a candidate and open the right flag.

For the learning-memory record shape and no-regression gates, read
`references/learning-memory.md`.

## Step 3 - The cardinal rule: no cascade

The tree of work is **scaffolding, not scoreboard**. The only score that counts is the **direct
metric** - the objective's number and each CKR's number - read fresh from the source.

A finished subtree with a flat objective metric is **not** success. If the metric's lag window is
still open, mark the branch `waiting_for_measurement` and schedule the next read. Once the lag window
has closed and fresh reads still show no movement, the flat metric is a signal the breakdown was
wrong. Never infer progress from completed tasks. Measure the world directly. The same applies to the
anti-goal: measure breakage where it manifests, never roll it up.

## Step 4 - Run the zig-zag (discovery <-> execution)

This is not waterfall (discover everything, then build everything). It is a **zig-zag** that narrows:
learn a slice -> act on it -> that action surfaces the next unknown -> discover that -> act again.
The swings shrink as guess turns into known work. That narrowing *is* progress.

Keep every bend clean: when an **execution task hits an unknown mid-run, it hands back up** -
"this is not execution anymore, this is discovery" - and the loop decides whether to fund a fresh
probe before resuming. Never let a task quietly muddle through a discovery it cannot see the end of.
You are always either executing known work or running a scoped probe - never pretending one is the
other.

## Step 5 - Evaluate the anti-goal at THREE points every loop

The anti-goal is not a single end-of-loop check. It fires three times, each doing a different job.
This is the heart of the skill - get the timing right.

1. **Admissibility - before acting.** When the orchestrator picks the next move, it screens it
   against the anti-goal *before dispatching a worker*. A move that would breach the wall never
   reaches a worker. This is the guardrail *steering* - it removes disaster moves from the menu.
   The orchestrator judges a move's anti-goal cost up front; for moves whose cost is unknowable
   without running them, it can dispatch a worker in a propose-cost (dry-run) mode that returns a
   projected anti-metric *without committing*, then admit or veto.
   *Example: move "blanket 40% discount" -> projected expense $96k -> VETOED, off the menu.*
2. **Direct read - after acting.** Read the actual anti-metric from the source, not "the task said
   it stayed safe." Drift toward the wall warns early; crossing it trips the breaker.
   *Example: ran "targeted email" -> expense reads $71k -> in band.*
3. **Paired with the goal - at the progress read.** Success is two-sided: **objective up AND
   anti-goal held.** A loop that moved the metric by breaching the wall is a failed loop that looks
   like a win - only the paired read catches it.
   *Example: sales $420k up but expense $88k failed -> not a win -> FLAG breaking.*

## Step 6 - Escalate on the flags

The loop runs around 80% on its own. It calls the human on three outcome conditions, each a distinct
failure:

- **Cannot** - discovery budget exhausted or learning flatlined. Effort in, nothing back.
- **Breaking** - an anti-metric drifted or tripped. The loop started making it worse.
- **Pointless** - work finished or a CKR metric moved, but the objective metric did not budge. This
  also guards the tornado's deepest trap: the funnel can narrow toward the **wrong tip** - converging
  beautifully on a target that will not move the goal. Narrowing without the metric moving -> re-aim.

Run all three outcome flags at once. Drop any one and a class of silent failure slips through.

For delegated loops, also raise **Authority drift** when the loop or a worker tries to change the
frame, relax a threshold, expand scope, bypass approval, contact a human directly, or act outside the
ratified action envelope. This is a governance breaker, not just an invalid move.

Flags have lifecycle. They are `open`, `acknowledged`, `resolved`, or `waived`. `breaking` pauses
committing moves by default; `cannot` and `pointless` stop the affected branch; `authority drift`
stops the proposed move and goes to the human. The orchestrator may resume only inside the recorded
resolution.

## Step 7 - Hold the human-only line

The human owns the **frame**: the objective and target, the CKR and anti-goal definitions and
thresholds, the metric contracts, the action envelope, and the call that a goal is wrong.
**Goal-switching is human-only.**

This is load-bearing. If goal switching sits inside the loop, the loop can satisfy anything by
quietly retreating to a goal it is already hitting, and every guardrail becomes theater. Keeping goal
switching with the human is what makes the anti-goal mean something. This is **best-effort**: the
loop must try against the goal it was given; when effort goes in and the metric stays flat, it
reports the gap and hands up the evidence (budget spent, tree built, contributions done, flat
metric). The human decides.

In team terms: no matter how much runs on its own, eventually someone makes the call - and the call
belongs to a person.

## A read on where you are

The **width of the funnel** - the ratio of discovery to execution in recent loops - tells position.
Wide, still guessing -> early, far from goal. Narrow, mostly known work -> close. This is a progress
signal that is not the direct metric: the metric says *if* you have arrived; the funnel width says
*how close* on the way. It is honest only while "more known" and "closer to goal" stay coupled -
which is what the pointless flag protects.

## Scale the apparatus to the goal

Match depth to the stakes. Not every goal needs the full machinery. For a light or personal goal,
the load-bearing core is just: **a metric+target objective, a measured anti-goal, and the no-cascade
habit of reading the real metric instead of counting tasks done.** Lead with that.

Bring in the heavier parts - orchestrator/worker split, idempotent storage, the formal three-point
eval, the flags - when the goal is being run as an actual automated loop, has real side effects
(spend, sends, deploys), or the user asks how to operationalize it. Offer them rather than front-load
them on someone who just wants help shaping a goal. The reverse tornado is the same shape at every
size; you do not always need to draw the whole funnel.

## Output

Deliver the structured loop: objective + target, the named anti-goal with its metric and type
(drift/tripwire), the CKR/DKR/PKR decomposition, the three eval points instantiated for *this* goal,
the flags, and the human-only frame. Use the user's real domain throughout - do not leave the example
abstract. Preserve exact metric literals from the source material in addition to any explanation; if
the source says `12 per 100`, include that exact phrase instead of only a paraphrase.

When the user wants to run the goal over time, also deliver the Operating Loop: cadence, current
round, metric freshness contracts, lag windows, `next_check_at`, stale-data policy, flag lifecycle,
and what gets updated at every turn or timed heartbeat. Include the current metric freshness
classification, keeping `observed_at`, `recorded_at`, `fresh` or `stale`, and `max_age` in the same
table row or sentence.

When the goal will recur in the same project, also deliver an **OKRA Learning Memory** section:
previous-run inputs scanned, traps, avoidances, misconceptions, optimization candidates, reusable
candidate anti-goals with metrics, evidence or hashes, confidence, context fit, ratification status,
terminalization or continuation-packet status, trace refs, review-set refs, and no-regression /
no-single-LLM-truth evidence. State which memories are automatic candidates and which, if any, the
human ratified for this run.

For delegated loops, make these four lines explicit in the artifact:

- The orchestrator owns objective checks, check-ins, the OKR board, and subagent steering until the
  objective metric reaches target or a human/blocking flag stops the loop. Use the exact phrase
  **"until the objective metric reaches target"** once, then instantiate it with the domain target.
- Include one compact line that starts **"Action envelope:"** and names allowed moves, forbidden
  actions, approval gates, and the human ratification boundary.
- DKRs are scoped discovery-worker probes with budgets, probability/confidence outputs, a named
  steering decision to unlock, and explicit risk/anti-goal uncertainty to reduce.
- CKR/PKR candidates are not promoted until the orchestrator accepts a DKR learning checkpoint.
  Use the exact sentence: **"Candidate CKRs and candidate PKRs are not promoted until the
  orchestrator accepts the supporting DKR learning checkpoint."**
- CKRs are measurable contribution context with mini reverse-tornado discovery/delivery balance,
  not subagent work. For each CKR, include one compact line that starts
  **"CKR-level discovery/delivery balance:"** and names both the discovery side and the delivery
  path.
- PKRs are progression-worker execution units and must report progress signals at check-ins. Each
  PKR should carry `linked_ckr`, `source_dkr_checkpoint`, `contribution_metric`, done check, allowed
  actions, forbidden actions, and the hand-back rule for newly discovered uncertainty.
- Long-running workers write file-based progress reports under `.okra/runs/<run-id>/workers/` and
  use a timed heartbeat, defaulting to ten minutes when the human has not set a cadence. Include one
  compact line that starts **"Heartbeat cadence and next_check_at:"** and contains both the cadence
  and the next scheduled check.
- Steering check-ins record value evidence: inbound signal, decision delta, affected CKR/PKR/DKR or
  allocation, expected/direct metric or risk effect, and a freshness or evidence reference. Also
  append a steering-value ledger metric read, such as `steering_value_score >= 0.75` or
  `valuable_steering_decision_count >= 1`; do not leave steering value only in prose.

For delegated handoff, learning-cycle, or transition-surface artifacts, make the contract surface
field-explicit instead of relying on prose. Include a **Worker prompt packet contract** with these
exact keys or dotted field names in the packet: `frame.objective`, `frame.anti_goals`,
`frame.action_envelope`, `frame.human_ratification_boundary`, `current_state`,
`previous_dkr_checkpoint`, `assignment`, `budget_and_stop_rule`, `hand_back_rule`, and
`output_schema`. Include an **In-progress influence rule** with this exact sentence:
**"In-progress worker narrative is not evidence; only worker progress, check-ins, metric reads,
flags, or accepted checkpoints can influence the next dispatch."** Include a **DKR-to-DKR handoff**
section that names `previous_dkr_checkpoint`, `decision_target`, `evidence_refs_or_hashes`,
`questions_answered`, `questions_unanswered`, `confidence_probability_update`,
`risk_or_anti_goal_implications`, `orchestrator_decision`, and `next_dkr_scope`. Include a
**PKR discovery hand-back** line saying that PKRs hand back on unknown discovery instead of
researching or resolving unknowns inside execution.

For delegated loops, include a compact **Eval Points** section with these exact labels instantiated
for the current goal:

- **Admissibility before action**: the orchestrator screens objective moves against fresh anti-goal
  readings or a dry-run before dispatch.
- **Direct read after action**: the loop reads the real objective, CKR, and anti-goal metrics from
  source records after workers return.
- **Paired goal/anti-goal eval**: the loop checks objective progress and anti-goal hold together;
  success requires both the objective target and every anti-goal threshold to hold.

For delegated loops with storage, also state the exact frame/tree schema in the artifact or records:
frame keys `frame_version`, `frame_hash`, `objective`, `anti_goals`, `metric_contracts`,
`action_envelope`, and human approval/ratification evidence; tree keys `tree_version`,
`frame_version`, `orchestrator`, `dkrs`, `ckrs`, and `pkrs`. The tree must use the key
`orchestrator` and include the phrases `objective checks` and `subagent steering`.

Avoid ambiguous frame-authority wording. Do not write that the loop, agent, model, or orchestrator
may change, adjust, relax, redefine, retune, or switch the objective, target, threshold, anti-goal,
guardrail, metric, or action envelope. Write that the loop raises evidence and the human decides.
For boundary-drift gates, use rejection-shaped wording such as: **"Reject any attempted frame,
guardrail, metric, threshold, or action-envelope change unless the human ratifies it."** Avoid
permission-shaped wording even when describing a forbidden pattern.

Define all four flags explicitly. For `pointless`, use the exact shape: **"Pointless opens when work
finished or a CKR metric moved, but the objective metric stays flat / does not move after the lag
window."** Then add the domain example and the stop/re-aim behavior.

If the user wants a visual or shareable explainer, produce a self-contained HTML artifact. See
`references/artifact-guide.md` for how (and how to keep the artifact within its own anti-goal:
single file, no external runtime, no decoration that does not carry meaning).

## Common mistakes to avoid

- Setting an objective with no metric, or an anti-goal with no metric. Both must be numbers.
- Rolling completed tasks up into "done" instead of reading the direct metric (cascade).
- Treating the anti-goal as one end-of-loop check instead of three points.
- Letting an execution task absorb a discovery instead of handing back.
- Running DKR as vague research, process optimization, or goal-chasing without naming the steering
  decision it unlocks and the risk or anti-goal uncertainty it reduces.
- Promoting CKRs or PKRs before a DKR learning checkpoint has produced evidence, probabilities, and
  decision-ready risk implications.
- Sending a raw "continue from previous work" prompt instead of a worker prompt packet with frame,
  current state, checkpoint refs, assignment, budget, stop rule, hand-back rule, and output schema.
- Letting in-progress worker narrative influence the next dispatch without governed records such as
  progress files, check-ins, metric reads, flags, accepted checkpoints, or evidence hashes.
- Dispatching a PKR without `linked_ckr`, `source_dkr_checkpoint`, and `contribution_metric`.
- Omitting the `pointless` flag, or defining it without saying the objective metric stays flat or
  does not move after the lag window.
- Letting the loop redefine, retune, or switch the goal. That is always the human's call.
- Writing a run-store tree with `ownership` but no `orchestrator` key, or omitting `frame_version`.
- Running a recurring OKR loop without a freshness contract, heartbeat, lag window, and flag owner.
- Running multiple OKRA loops against the same flat `.okra/ledger.jsonl`, `.okra/checkins.jsonl`,
  or `.okra/workers/` path instead of giving each loop its own run store.
- Treating a hand-edited progress summary as source of truth instead of generating it from
  append-only storage records.
- Treating one LLM's self-report as truth without independent evidence.
- Treating one independent review path as enough evidence for judgement-heavy memory promotion.
- Treating previous-run memory as automatic authority instead of candidate evidence for the
  orchestrator and human to ratify.
- Reusing a completed run's learning without terminal proof, a retained trace manifest, or a
  continuation packet.
- Storing generic notes instead of OKRA-specific traps, avoidances, misconceptions, optimizations,
  candidate anti-goals, and no-regression evidence.
