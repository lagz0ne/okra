# Current Storage Signals

Observed harness failures to guard against:

- An agent reads fixture notes, skill references, or prior progress summaries and then produces a
  confident plan without any record of what source content shaped the plan.
- An agent writes `tasks/*.md` directly and later claims it used governed storage, but there is no
  content hash linking the final artifact to a store record.
- An agent edits `status.md` by hand and treats it as current progress even though the append-only
  check-ins or metric ledger disagree.
- An agent says "verified" in its final answer, but no deterministic verifier output, content hash,
  changed-path evidence, second review, or human ratification backs the claim.

Required operating signals:

- Missing source read record opens `breaking`.
- Missing write record for the final artifact opens `breaking`.
- Store verification failure opens `breaking`.
- Storage friction that prevents the agent from doing OKRA work opens `pointless`.
- A semantic claim with only one LLM narrative as evidence opens `breaking`.

The loop should stay bash-first. A database, service, or long-lived daemon is not required for this
fixture.
