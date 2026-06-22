# Skill Development Setup Review

Review this repository as a skill development environment for `reverse-tornado-okr`. Focus on whether a future Claude or Codex agent can:

- find and edit the canonical skill without duplicating it
- run basic skill validation
- run isolated blindbox evals against Claude and Codex
- preserve raw eval artifacts for independent inspection
- run review/verification before claiming agent-facing changes are done
- require real-life OKR operation mechanics: ratified frame, metric freshness, heartbeat cadence,
  lag windows, action envelope, flag lifecycle, storage/idempotency, and blocked states
- catch eval false confidence from vocabulary-only outputs, product-code edits, stale metrics,
  uncontained paths, missing hashes, or unchecked credentials

Findings should come first, ordered by severity, with concrete file and line references. Do not modify files.
