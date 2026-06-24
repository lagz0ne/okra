---
name: reverse-tornado-okr
description: >
  A workflow for setting up and running any goal as a self-correcting OKR loop with a measured
  anti-goal guardrail. Use this whenever the user is setting OKRs, defining objectives and key
  results, planning a goal, structuring a roadmap toward a metric, or asking how to make progress
  on something measurable without breaking a constraint (budget, quality, risk, trust). Trigger
  even when the user just says "help me set a goal", "what should my OKRs be", "I want to grow X",
  or describes a target plus a thing they must not sacrifice - the anti-goal is the signal this
  workflow fits. Also use when the user wants to delegate goal execution to an automated loop while
  keeping human control of the direction. Produces the structured loop (objective, anti-goal,
  decomposition, eval points, flags, and operating cadence); can optionally produce an explainer
  artifact.
---

# The Reverse Tornado - running a goal as a self-correcting loop

This skill is a workflow. Given any goal, it sets the goal up so an LLM can drive most of the work
while a human keeps the direction. The core picture is a reverse tornado: wide guessing on day
one, narrowing loop by loop into known work, bounded the whole way by a wall it cannot cross
(the anti-goal), stopping when the metric hits target. Another useful picture: the objective is the
maze exit, anti-goals are traps, and discovery maps enough of the maze that the loop can keep moving
without blindly sprinting into danger.

Apply the steps below in order. Do not skip the anti-goal - it is what makes the rest safe.

## Step 1 - Set the frame (metric + target, and the wall)

Pin two things before any planning:

- **Objective**: a metric with a target number. Not a vibe. "Grow monthly sales to $500k", not
  "do better at sales". If the user gives a vague goal, your first job is to propose the metric
  that would prove it, state that it is a candidate, and get human ratification before any
  state-changing move.
- **Anti-goal**: the thing that must not be sacrificed, expressed with **its own metric**. "Keep
  monthly expense at or under $80k." It can be continuous (a drift gauge you watch) or binary
  (a tripwire that halts). State which.

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

Then set the clock: start-of-turn freshness check, pre-dispatch admissibility, post-move metric
read, end-of-turn status write, and an idle heartbeat when no worker finishes. Every round should
write `current_round`, open flags, last metric read, and `next_check_at`. Do not dispatch committing
work on stale metrics unless the human explicitly waives that stale state.

For delegated subagent work, make check-ins both event-based and time-based: worker completion,
unknown discovery, flag opening, and a default ten-minute heartbeat for long-running workers. Each
check-in recollects DKR learning, reads file-based worker progress reports, updates CKR/PKR
candidate status, and decides whether to continue, spawn discovery, pause, or escalate.

For the operating-loop fields, lag handling, and flag lifecycle, read
`references/operating-loop.md`.

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

This is load-bearing. A loop that can switch its own goal can satisfy anything by quietly retreating
to a goal it is already hitting - which makes every guardrail theater. Locking goal-switching to the
human is what makes the anti-goal mean something. This is **best-effort**: the loop must try against
the goal it was given; when effort goes in and the metric stays flat, it reports the gap and hands
up the evidence (budget spent, tree built, contributions done, flat metric). The human decides.

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
abstract.

When the user wants to run the goal over time, also deliver the Operating Loop: cadence, current
round, metric freshness contracts, lag windows, `next_check_at`, stale-data policy, flag lifecycle,
and what gets updated at every turn or timed heartbeat.

For delegated loops, make these four lines explicit in the artifact:

- The orchestrator owns objective checks, check-ins, the OKR board, and subagent steering until the
  objective metric reaches target or a human/blocking flag stops the loop.
- DKRs are scoped discovery-worker probes with budgets, probability/confidence outputs, a named
  steering decision to unlock, and explicit risk/anti-goal uncertainty to reduce.
- CKR/PKR candidates are not promoted until the orchestrator accepts a DKR learning checkpoint.
- CKRs are measurable contribution context with mini reverse-tornado discovery/delivery balance,
  not subagent work.
- PKRs are progression-worker execution units and must report progress signals at check-ins.
- Long-running workers write file-based progress reports under `.okra/runs/<run-id>/workers/` and
  use a timed heartbeat, defaulting to ten minutes when the human has not set a cadence.

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
- Letting the loop redefine, retune, or switch the goal. That is always the human's call.
- Running a recurring OKR loop without a freshness contract, heartbeat, lag window, and flag owner.
- Running multiple OKRA loops against the same flat `.okra/ledger.jsonl`, `.okra/checkins.jsonl`,
  or `.okra/workers/` path instead of giving each loop its own run store.
- Treating a hand-edited progress summary as source of truth instead of generating it from
  append-only storage records.
- Treating one LLM's self-report as truth without independent evidence.
