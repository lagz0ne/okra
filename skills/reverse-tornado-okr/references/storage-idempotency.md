# Storage and Idempotency

Use this reference when the goal is being run as an automated loop, has side effects, or must survive interruption and resume.

If the run also produces many artifacts, check-ins, or progress summaries, use
`integrity-store.md` with this reference. The short version: append-only records are source of truth;
human-readable status is generated.

## Store

Persist these records before running the first state-changing move. In a workspace where multiple
OKRA loops may run at the same time, keep the shared root as `.okra/` and place mutable state under
`.okra/runs/<run-id>/`; only `.okra/content/sha256/` is shared across runs.

- `.okra/runs/<run-id>/frame/frame.v1.json`: write-once objective, target, anti-goal, thresholds, owner, and ratification time.
  Include `frame_version`, `frame_hash`, metric contracts, anti-goal coverage review, action
  envelope, and the human approval record.
- `.okra/runs/<run-id>/tree/tree.v1.json`: current DKR/CKR/PKR decomposition and worker scopes.
  Include `tree_version`, `frame_version`, `orchestrator`, `dkrs`, `ckrs`, and `pkrs`. The
  `orchestrator` field must explicitly own objective checks, check-ins, the OKR board, and subagent
  steering. Do not use a generic `ownership` field as a substitute for `orchestrator`.
- `.okra/runs/<run-id>/moves/<key-sha256>.json`: write-once committed move result. Each file
  records the full `idempotency_key`, `key_sha256`, `payload_sha256`, committed timestamp, and payload.
- `.okra/runs/<run-id>/ledger.jsonl`: append-only direct objective and anti-goal readings with `observed_at`,
  `recorded_at`, source, query/report hash, window, value, unit, and freshness status.
  When the helper is available, write these with `metric-read` and payload type `metric_read`,
  `objective_metric_read`, or `anti_goal_metric_read`; do not use ambiguous `kind: objective`
  ledger payloads.
- `.okra/runs/<run-id>/flags.jsonl`: append-only `cannot`, `breaking`, `pointless`, and `authority_drift` flags with
  lifecycle status and resolution records.
- `.okra/runs/<run-id>/checkins.jsonl`: append-only steering records for each ritual check-in, including learning
  collected, PKR signals, stale metrics, process/context updates, and next steering decision.
- `.okra/runs/<run-id>/workers/<worker-id>/progress.jsonl`: append-only file-based progress reports from DKR and PKR
  workers. DKR reports include the steering decision the probe is meant to unlock, the risk or
  anti-goal uncertainty it is reducing, learning collected, probability/confidence updates,
  remaining unknowns, candidate CKRs, and `next_report_at`.

Do not rewrite frame or ledger records to make a run look safer after the fact. Add a new reading or
a human-ratified frame revision instead. A revision is a new immutable frame record with diff,
reason, approver, timestamp, affected metrics, and whether it relaxes any guardrail.

Do not hand-edit generated progress summaries to make them agree with the run. Regenerate summaries
from source records and treat contradictions as `breaking`, `cannot`, or `authority_drift` evidence.

## Idempotency Keys

Use a stable key for every committing move:

```text
<run-id>/<frame-version>/<frame-hash>/<metric-contract-hash>/<action-approval-id>/<tree-node-id>/<move-kind>/<scope-hash>/<input-hash>/<attempt-policy>
```

Include enough input to distinguish materially different side effects. Do not include timestamps, worker ids, random ids, or retry counts unless they change the intended effect.

The key must change when the frame, metric definition, guardrail threshold, authority envelope, or
human approval changes. Reusing a result across frame revisions is allowed only for explicitly
read-only discovery outputs that the orchestrator re-admits under the current frame.

The `run-id` is part of the key and the path. Two OKRA loops may have identical frame hashes or task
names and still must not share move results unless a human explicitly imports evidence from one run
into another. Shared content blobs are reusable by hash; mutable logs and move results are not.

Dry-run propose-cost moves do not need idempotency keys because they do not commit side effects. If a dry-run writes to an external system, it is not a dry-run and must be keyed.

## Dispatch Sequence

1. Read the current ratified frame and refuse to continue if the frame is still only a candidate.
2. Refuse committing moves when required metric readings are stale, missing, or blocked by an
   unresolved flag unless the human has recorded a waiver for this move.
3. Refuse and flag `authority_drift` if the worker or move tries to alter the frame, expand scope,
   bypass approval, relax a threshold, or leave the action envelope.
4. Build the candidate move and run admissibility against the anti-goal.
5. If CKR/PKR candidates depend on unresolved uncertainty, dispatch a DKR worker first. The DKR must
   name the steering decision it will unlock and the risk or anti-goal uncertainty it will reduce.
   Require a learning checkpoint before promoting candidates onto the working board.
6. If cost is unknown, run a propose-cost dry-run and admit or veto from that result.
7. Construct the idempotency key for an admitted committing move.
8. If `moves/<key-sha256>.json` exists, reuse it and do not dispatch the worker again.
9. Dispatch the worker with the frozen scope and key.
10. Require worker progress reports on completion, unknown discovery, flag-worthy risk, and timed
    heartbeat. Ten minutes is a useful default for live long-running workers.
11. Write the result once under `.okra/runs/<run-id>/moves/`.
12. Read direct objective and anti-goal metrics from source and append to `ledger.jsonl` through
    `metric-read` when the helper is available.
13. Append a check-in record with worker progress refs, PKR signals, learning collected,
    process/context updates, and `next_check_at`.
14. Evaluate `cannot`, `breaking`, `pointless`, and `authority_drift` flags.
15. Regenerate status from source records; do not edit it by hand.

## Resume Sequence

On restart, choose the explicit run store first, for example `.okra/runs/<run-id>/`. Load that run's
current frame revision, tree, move results, ledger, and flags. Check unresolved blocking flags and
metric freshness before rebuilding the next move. Never infer success from an existing subtree; use
ledger readings only if they satisfy the current metric contract, otherwise take a fresh direct read.

Before promoting CKR/PKR candidates or resuming a worker lane, verify that the corresponding DKR
learning checkpoint and worker progress reports exist. The checkpoint must state the decision target,
evidence, probability/confidence update, and risk or anti-goal implications. Missing learning
evidence is a `cannot` signal, not permission to guess the remaining structure.

If the frame changed while a worker was running, do not commit that worker's result automatically.
Record the worker output as evidence, re-run admissibility under the new frame, and either commit
under a new key or discard/redo the move.
