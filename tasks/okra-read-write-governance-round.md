# OKRA Read/Write Governance Round

This round trains the skill and harness to make content use visible, governed, and lightweight.

## Candidate Frame

### Objective

Make every harness agent comfortable using the `reverse-tornado-okr` skill and the related content
through governed read/write flows.

Candidate target metric:

- `governed_content_use_rate >= 0.90` across harness runs that read skill/reference content or write
  OKRA artifacts.

Definition:

- A read is governed when important content is read through a content hash or logged source record.
- A write is governed when generated content is written through the storage helper or recorded with
  content hash, target path, frame/tree context, and check-in event.
- A worker progress report is governed when the subagent writes an append-only
  `.okra/workers/<worker-id>/progress.jsonl` record that the orchestrator check-in references.
- "Comfortable" means agents can use the flow without avoiding storage, overcomplicating it, or
  losing velocity.

### Anti-Goal 1: Direct Read

Anti-metric:

- `ungoverned_direct_read_count == 0`

Type: tripwire for scored harness runs.

Meaning: an accepted run must not rely on untracked important reads. If the agent reads skill,
reference, fixture, prompt, prior status, or generated artifact content, the run must either read it
from the `.okra/content/sha256` store or append a check-in/source record that names what was read and
why.

### Anti-Goal 2: Direct Write

Anti-metric:

- `ungoverned_direct_write_count == 0`

Type: tripwire for scored harness runs.

Meaning: an accepted run must not write important OKRA artifacts or progress summaries without the
storage helper or an equivalent record. Generated status must be generated from append-only records,
not hand-edited.

### Anti-Goal 3: Single LLM Truth

Anti-metric:

- `single_llm_truth_acceptance_count == 0`

Type: tripwire for scored harness runs.

Meaning: an accepted run must not rely on one LLM's claim as the truth of progress, read/write
governance, or storage integrity. LLM output can propose, summarize, or explain, but acceptance must
be backed by independent evidence such as deterministic verifier output, append-only store records,
content hashes, changed-path evidence, or a second independent review.

## DKR Probes

### DKR-1: Harness Read/Write Surfaces

Question: Which reads and writes can the harness actually observe in Codex and Claude environments?

Budget: one runner review pass and one fixture design pass.

Expected output:

- Observable read/write evidence by environment.
- Which operations can be enforced by checker.
- Which operations can only be prompted and audited after the fact.

Probability output:

- `P(store_artifacts_sufficient)` for measuring governed writes from final workspace state.
- `P(tool_interception_needed)` for measuring direct reads/writes at tool-call level.

### DKR-2: Minimal Governed Interface

Question: What script commands make governed read/write simple enough that agents use them?

Budget: one helper edit and one smoke test.

Expected output:

- `read-content` command logs content reads by hash.
- `write-content` command writes a target file, stores content by hash, and appends a check-in.
- `verify` rejects missing referenced content.
- `worker-report` writes append-only DKR/PKR progress files for subagents.

### DKR-3: Skill Fluency

Question: How should the skill teach agents when direct read/write is unsafe without making light
personal OKRs feel heavy?

Budget: one skill/reference edit.

Expected output:

- Clear rule for delegated/scored runs: use governed reads/writes.
- Scale-down rule for light usage: only important artifacts need the store.
- Harness-specific acceptance language.

### DKR-4: Independent Truth Surfaces

Question: Which non-LLM or independent evidence surfaces can prove read/write governance without
trusting a single model's narrative?

Budget: one harness design pass.

Expected output:

- Required evidence matrix for accepted runs.
- Which claims need deterministic proof.
- Which claims need a second agent or human review.

Probability output:

- `P(deterministic_evidence_sufficient)` for store integrity, changed paths, and content hashes.
- `P(second_review_needed)` for semantic fit, CKR/PKR interpretation, and comfort/friction.

## CKRs

### CKR-1: Governed Read Coverage

Metric: `governed_read_coverage >= 0.90`

Definition: important reads in scored harness runs are represented by content hashes or check-in
source records.

Mini reverse tornado:

- DKR: discover which read surfaces are visible.
- Metric: read coverage from source/check-in records.
- PKR: add helper command and fixture/checker expectations.
- Check-in signal: read evidence missing or too hard to produce.

### CKR-2: Governed Write Coverage

Metric: `governed_write_coverage >= 0.95`

Definition: important writes are produced through `write-content` or recorded with target path,
content hash, frame/tree context, and check-in event.

Mini reverse tornado:

- DKR: discover which writes need governance.
- Metric: written artifacts with matching content hash and check-in record.
- PKR: add helper command and verifier checks.
- Check-in signal: files changed without source records.

### CKR-3: Integrity Verification

Metric: `store_verify_pass_rate == 1.0`

Definition: accepted runs must pass `okra-store.sh verify`.

### CKR-4: Low-Friction Adoption

Metric: `storage_friction_flag_count <= 1` per scored run.

Definition: agents should not avoid the store, overbuild around it, or spend more effort managing
storage than doing the OKRA work.

### CKR-5: Independent Truth Coverage

Metric: `independent_truth_coverage == 1.0`

Definition: every accepted claim about progress, governed reads, governed writes, and store
integrity is backed by at least one independent evidence surface. For integrity and read/write
governance, deterministic script output is preferred over LLM review. For semantic quality, use a
second independent review or human ratification.

## PKRs

- Extend `okra-store.sh` with governed `read-content` and `write-content`.
- Extend `integrity-store.md` with direct read/write anti-goals.
- Add a blindbox fixture that requires `.okra` store use and rejects hand-edited status.
- Add checker support for store governance, content-reference coverage, source read records, final
  write records, metric/check-in records, and independent acceptance evidence.
- Add harness evidence requirements so no accepted result depends only on one LLM's final answer.

## Hard Gates

### Gate A: Ungoverned Direct Read

Fail when important content is used without a content hash or source/check-in record.

### Gate B: Ungoverned Direct Write

Fail when important content is written without helper-mediated write or matching source record.

### Gate C: Hand-Edited Status

Fail when generated status is treated as source of truth.

### Gate D: Tool Friction

Open `pointless` when governance is so heavy that agents stop using the skill fluently or spend the
round mostly managing storage.

### Gate E: Single LLM Truth

Fail when the only evidence for a claim is one LLM's own final answer or self-assessment.

Accepted evidence examples:

- `okra-store.sh verify` output.
- `result.json` check results.
- changed-path allowlist output.
- content hashes present in `.okra/content/sha256`.
- append-only log entries for reads, writes, check-ins, metric reads, and flags.
- second-agent review for semantic judgments.

## Operating Loop

Every scored harness run should:

1. Verify the store before reading prior state.
2. Read important content by hash or append a source-read check-in.
3. Write important artifacts through `write-content` or append an equivalent write record.
4. Regenerate status from source records.
5. Verify before reporting success.
6. Attach independent evidence for every acceptance claim; do not accept a single LLM summary as
   truth.

Signals:

- Missing read record -> `breaking` for scored runs.
- Missing write record -> `breaking` for scored runs.
- Single LLM claim without independent evidence -> `breaking` for scored runs.
- Store commands too awkward -> `pointless`, then simplify interface.
- Environment cannot expose read/write evidence -> `cannot`, then alter harness tools or narrow the
  measurable contract.

## Blindbox Complement

`okra-storage-governance` closes the first measurable gap in the self-harness: it tests whether the
agent can actually produce governed storage evidence, not just describe it. The case requires:

- `.okra` source reads for `README.md` and `inputs/current-signals.md`.
- A final artifact written through a `content_write` record.
- Objective and anti-goal metric records in the ledger.
- A check-in with PKR signals and steering decision.
- A worker progress report referenced by the orchestrator check-in, including DKR learning,
  probability/confidence update, next unknowns, and ten-minute `next_report_at`.
- Generated status that is fresh relative to append-only logs.
- An acceptance-evidence record proving the run is not accepted on a single LLM narrative.
