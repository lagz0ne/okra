# OKRA Storage Integrity Round

This is the next OKRA round for training the skill to use storage fluently.

## Candidate Frame

### Objective

Make storage a fluent part of `reverse-tornado-okr` delegated runs.

Candidate target metric:

- `storage_fluency_acceptance_rate >= 0.90` across artifacts that claim to run or manage an OKRA
  loop over time.

An accepted artifact must describe where the frame, tree, content, moves, metric reads, check-ins,
flags, and generated status live, and how integrity is verified before progress is trusted.

### Anti-Goal

Do not let separate progress surfaces contradict each other.

Candidate anti-metric:

- `contradictory_progress_surface_count == 0`

Type: tripwire. Any accepted artifact where `status.md`, task/progress prose, ledger records, flags,
or tree state can claim incompatible progress without a detectable integrity failure is rejected.

## Model

Storage is not just persistence. It is the integrity boundary for the loop.

- Source of truth is append-only records: frame revisions, tree versions, committed move results,
  metric ledger, worker progress reports, check-ins, and flags.
- Human-readable progress views are generated from those records.
- Content that matters is content-addressed by hash.
- Check-ins are stored as records, not only summarized in prose.
- Subagents report through `.okra/workers/<worker-id>/progress.jsonl`; orchestrator check-ins read
  those files before steering DKR/CKR/PKR state.
- Verification runs before resume, before reporting success, and before accepting a generated view.

The rule: **events are authoritative; summaries are derived.**

## DKR Probes

### DKR-1: Minimal Store Shape

Question: What is the smallest file layout that protects integrity without making the skill feel
heavy?

Budget: one design pass and one script smoke pass.

Expected output:

- A recommended `.okra/` layout.
- Which files are source records versus generated views.
- Which records are write-once, append-only, or generated.

Probability output:

- `P(simple_file_store_sufficient)` for a bash-first implementation.
- `P(needs_database)` if hash-chain verification proves too awkward.

### DKR-2: Integrity Contract

Question: What can make two progress surfaces disagree, and how can a lightweight verifier catch it?

Budget: one design pass.

Expected output:

- Hash-chain rules for JSONL logs.
- Content-address rules for artifacts and run content.
- Generated-view staleness rules.
- Resume refusal conditions.

### DKR-3: Skill Fluency

Question: How should the skill tell agents to use storage without front-loading too much machinery?

Budget: one skill edit pass.

Expected output:

- A concise skill instruction.
- A longer reference file.
- A tiny script interface for common actions.

## CKRs

### CKR-1: Integrity Store Coverage

Metric: `required_store_surface_coverage == 1.0`

Required surfaces:

- frame
- tree
- content blobs
- committed moves
- metric ledger
- check-ins
- worker progress files
- flags
- generated status
- manifest/hash verification

Each CKR has its own mini reverse tornado: discover the minimum store surface, define the direct
coverage metric, admit PKRs only after the store surface is known, and check in on contradictions.

### CKR-2: Contradiction Detection

Metric: `known_contradiction_detection_rate >= 0.95`

Definition: handcrafted contradictions such as broken hash chains, missing referenced content,
stale generated status, and mismatched frame/tree hashes are detected by the verifier or explicitly
flagged as unsupported.

### CKR-3: Bash-First Operability

Metric: `bash_store_smoke_pass_rate == 1.0`

Definition: `init`, `put`, `append`, `verify`, and `status` work in a disposable directory using
common local tools.

### CKR-4: Skill Fluency

Metric: `storage_guidance_completeness == 1.0`

Definition: the skill tells agents when to use the store, what records are authoritative, when to
generate status, and when to refuse resume/reporting because integrity failed.

### CKR-5: Worker Report Coverage

Metric: `worker_progress_report_coverage >= 0.95`

Definition: long-running DKR/PKR workers produce append-only progress files with learning collected,
probability/confidence updates when applicable, PKR health signals, and `next_report_at`. The
default live heartbeat is ten minutes unless the human sets another cadence.

## PKR Admission Rules

A PKR is admissible only when it links to a DKR finding and one CKR.

Candidate PKRs:

- Add an integrity-store reference.
- Update the skill body to point recurring/delegated runs to that reference.
- Add a tiny bash helper for `.okra` stores.
- Add a worker progress report command for subagent check-ins.
- Smoke test helper commands in a temporary store.
- Add a future eval case only after the store contract has stabilized.

## Hard Gates

### Gate A: Summary-As-Truth

Fail when a human-readable progress file is authoritative rather than generated from source records.

### Gate B: Mutable History

Fail when ledger, check-in, flag, move, or frame history can be edited in place without detection.

### Gate C: Untracked Content

Fail when artifacts, prompts, outputs, or review notes can be referenced without a content hash.

### Gate D: Resume Without Verification

Fail when a loop can resume without verifying frame, tree, move, ledger, flag, and generated-view
integrity.

### Gate E: Overbuilt Store

Fail softly when the design needs a database, service, or complex runtime before bash scripts and
files have been tried. This opens `cannot` or `pointless`, not `breaking`, unless it blocks use.

## Operating Loop

Cadence:

- Every check-in appends one check-in record.
- Every long-running worker appends progress on completion, unknown discovery, flag-worthy risk, and
  the ten-minute heartbeat.
- Every metric read appends one ledger record.
- Every flag lifecycle change appends one flag record.
- Every reporting turn regenerates status from the records.
- Every resume runs verification before dispatch.

Signals:

- Broken hash chain -> `breaking`.
- Missing content hash -> `breaking`.
- Missing worker progress report for active subagent work -> `stale_steering` or `cannot`.
- Generated status stale -> regenerate or open `cannot` if regeneration fails.
- Frame/tree mismatch -> `authority_drift` if unratified, otherwise require a new version.
- Too much storage friction -> `pointless` if agents avoid the store and progress quality does not
  improve.

Next move:

- Add the integrity-store reference and bash helper, then use smoke tests to decide whether the
  bash-first store is sufficient for the skill.
