# Integrity Store

Use this reference when an OKRA loop continues across turns, produces many artifacts, or needs
progress to remain consistent across summaries, check-ins, flags, and metric reads.

The integrity rule is simple:

**Append-only records are the source of truth. Human-readable status is generated.**

This keeps storage lightweight while preventing `status.md` from saying one thing, `flags.jsonl`
another, and the DKR/CKR/PKR tree a third.

For scored or delegated harness runs, add two anti-goals:

- **No ungoverned direct read**: important content reads should come from a content hash or append a
  source/check-in record that says what was read and why.
- **No ungoverned direct write**: important artifact writes should go through the helper or append a
  write record with target path and content hash.
- **No single LLM truth**: an LLM's final answer or self-assessment is not proof of progress,
  integrity, or governed read/write. Acceptance needs independent evidence.

## Recommended Layout

Use one `.okra` root per workspace, then one run directory per active OKRA loop. The shared root
holds content-addressed blobs that are safe to reuse; each run owns its own frame, tree, logs,
workers, moves, drafts, and generated status.

```text
.okra/
  content/
    sha256/<hash>
  runs/
    <run-id>/
      frame/
        frame.v1.json
        current
      tree/
        tree.v1.json
        current
      drafts/
      moves/
        <key-sha256>.json
      workers/
        <worker-id>/progress.jsonl
      ledger.jsonl
      flags.jsonl
      checkins.jsonl
      status.md
```

For a single lightweight run, the helper still supports the legacy flat `.okra/ledger.jsonl` layout.
For delegated, recurring, or parallel loops, use `.okra/runs/<run-id>/` and pass that run directory
as the helper's store argument. Do not use a global `.okra/current` pointer as authority while
multiple loops are active; every worker report, metric read, check-in, flag, and status view should
carry or imply the run id through its path.

Authoritative records:

- `.okra/runs/<run-id>/frame/*.json`: write-once human-ratified frame revisions.
- `.okra/runs/<run-id>/tree/*.json`: versioned DKR/CKR/PKR structure and worker scopes.
- `.okra/content/sha256/<hash>`: prompts, artifacts, worker outputs, review notes, and other important
  content addressed by SHA-256.
- `.okra/runs/<run-id>/moves/<key-sha256>.json`: write-once committed move outcomes. Each file
  records the full `idempotency_key`, `key_sha256`, `payload_sha256`, committed timestamp, and payload.
- `.okra/runs/<run-id>/workers/<worker-id>/progress.jsonl`: append-only worker progress reports for DKR and PKR
  subagents.
- `.okra/runs/<run-id>/ledger.jsonl`: append-only objective, CKR, and anti-goal metric reads.
- `.okra/runs/<run-id>/flags.jsonl`: append-only flag lifecycle records.
- `.okra/runs/<run-id>/checkins.jsonl`: append-only check-in records.

Generated view:

- `.okra/runs/<run-id>/status.md`: generated from append-only source records. Do not edit it by
  hand or treat it as authority.

## Required Frame and Tree Shape

For delegated or scored runs, keep the frame and tree boring and machine-checkable.

`frame/frame.v1.json` must be an object with:

- `frame_version`
- `frame_hash`
- `objective`
- `anti_goals`
- `metric_contracts`
- `action_envelope`
- `human_approval` or other explicit ratification evidence

`tree/tree.v1.json` must be an object with:

- `tree_version`
- `frame_version`
- `orchestrator`
- `dkrs`
- `ckrs`
- `pkrs`

Use the exact key `orchestrator`. Do not replace it with `ownership`. The orchestrator entry should
say it owns `objective checks`, check-ins, the OKR board, and `subagent steering`. DKR entries should
be discovery-worker scopes with budgets, decision targets, risk or anti-goal uncertainty, and
probability/confidence outputs. CKR entries should be measurable contribution context, not worker
jobs. PKR entries should be progression-worker scopes with progress signals.

When the helper is available, prefer:

```sh
"$helper" write-frame frame.json "$run_store"
"$helper" write-tree tree.json "$run_store"
"$helper" verify "$run_store"
```

If `verify` reports missing `frame_version`, `orchestrator`, `objective checks`, or
`subagent steering`, fix the JSON before dispatching or reporting success.

## Metric Read Records

Use the helper's `metric-read` command for objective, CKR, and anti-goal ledger entries. Do not use
generic `append ledger` for these reads in scored or delegated runs.

```json
{"type":"metric_read","metric_kind":"objective","metric_id":"objective.governed_content_use_rate","value":0.9,"target":0.9,"observed_at":"2026-06-24T00:00:00Z","source":"deterministic checker","freshness":"observed_at=2026-06-24T00:00:00Z -> status=fresh against max_age=72h"}
```

For storage-governance runs, append zero-valued anti-goal metric reads with `type:
"anti_goal_metric_read"` and metric ids containing `ungoverned_direct_read`,
`ungoverned_direct_write`, and `single_llm_truth`.

## Append-Only Log Contract

Every line in a run's `ledger.jsonl`, `flags.jsonl`, and `checkins.jsonl` should be a JSON object
with:

- `seq`: increasing integer
- `recorded_at`: when the record was written
- `prev_hash`: previous record hash, or `GENESIS`
- `payload_sha256`: hash of the payload
- `payload`: the event payload
- `record_hash`: hash of the canonical record without `record_hash`

Concurrent appenders must not write the same JSONL file without a lock. The helper uses per-log
`.lock` files so two agents cannot compute the same `seq` or `prev_hash` for one run log. Separate
runs do not share mutable logs; they only share immutable content blobs.

Verification should fail when:

- a sequence number is missing or duplicated
- `prev_hash` does not match the previous line
- `payload_sha256` does not match the payload
- a referenced content hash is missing
- a generated status file is older than a source record

For scored harness runs, a claim should be accepted only when it is backed by independent evidence:

- store verification output for integrity
- content hashes for important read/write content
- append-only records for check-ins, metric reads, flags, governed reads, and governed writes
- changed-path allowlists for workspace writes
- second-agent or human review for semantic judgments that a script cannot decide

When recording scored acceptance evidence, append a check-in payload with
`type: "acceptance_evidence_checkin"`. Include `single_llm_truth_acceptance_count: 0` and evidence
entries for at least store verification, content hashes, and changed-path or deterministic-checker
results. This keeps "the agent said it worked" out of the acceptance path.

## Check-In Records

Check-ins are the steering cadence. Store them as records, not just prose.

A useful check-in payload includes:

- `round`
- `frame_hash`
- `tree_hash`
- `objective_read`
- `anti_goal_read`
- `active_dkrs`
- `active_ckrs`
- `active_pkrs`
- `dkr_learning_checkpoint`
- `candidate_ckrs`
- `candidate_pkrs`
- `worker_progress_refs`
- `pkr_signals`
- `open_flags`
- `learning_collected`
- `process_context_updates`
- `next_check_at`
- `steering_decision`

PKR signals should include off-track work, quality drift, churn, late discovery, stale metrics, and
scope or authority concerns.

DKR learning checkpoints should include the steering decision the probe is meant to unlock, the risk
or anti-goal uncertainty it is reducing, evidence collected, questions answered/unanswered,
probability or confidence changes, candidate CKRs, and remaining unknowns. The orchestrator should
not promote CKR or PKR candidates until such a checkpoint is accepted.

For long-running subagents, use both event-based and time-based check-ins. Workers report on
completion, when an unknown is found, when a flag-worthy risk appears, and on a timed heartbeat.
Unless the human sets another cadence, use a ten-minute heartbeat for live worker progress. Store
the worker-side reports in `.okra/runs/<run-id>/workers/<worker-id>/progress.jsonl`; the
orchestrator check-in then references those reports through `worker_progress_refs`.

Governed content use should also be explicit in check-ins:

- `content_read`: a payload with `content_sha256` for important content read from the store.
- `content_write`: a payload with `target` and `content_sha256` for important artifacts written
  through the store.
- `steering_checkin`: a payload with `worker_progress_refs`, `pkr_signals`, and `steering_decision`.
- `acceptance_evidence_checkin`: a payload with deterministic evidence and
  `single_llm_truth_acceptance_count: 0`.

## Resume Rule

Before resuming a loop or reporting success:

1. Verify append-only hash chains.
2. Verify referenced content hashes exist.
3. Verify the current frame and tree exist and match records that cite them.
4. Read unresolved blocking flags.
5. Read metric freshness.
6. Regenerate status from source records.

If verification fails, do not dispatch committing work. Open `breaking` for corrupted history,
`authority_drift` for unratified frame/tree changes, or `cannot` when required records are missing.

If the only proof of success is one LLM's narrative, do not accept the result. Record the narrative
as content, then gather deterministic evidence or an independent review.

## Lightweight Helper

The optional helper `scripts/okra-store.sh` creates and checks this layout:

```sh
helper=".codex/skills/reverse-tornado-okr/scripts/okra-store.sh"
test -x "$helper" || helper=".claude/skills/reverse-tornado-okr/scripts/okra-store.sh"

"$helper" init .okra
run_store="$("$helper" init-run onboarding-activation .okra)"
"$helper" write-frame frame.json "$run_store"
"$helper" write-tree tree.json "$run_store"
"$helper" put path/to/artifact.md "$run_store"
"$helper" read-content <sha256> "$run_store"
"$helper" write-content tasks/loop.md "$run_store/drafts/loop.md" "$run_store"
"$helper" move-result <idempotency-key> move-result.json "$run_store"
"$helper" worker-report dkr-1 progress.json "$run_store"
"$helper" append checkins payload.json "$run_store"
"$helper" verify "$run_store"
"$helper" status "$run_store"
```

The helper is deliberately small. It is not a database. Its job is to make integrity easy enough
that agents use it before relying on summaries.
