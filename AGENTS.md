# Agent Workflow

This repo is the development workspace for the `reverse-tornado-okr` skill and its eval/review harness. Keep the environment useful before expanding the skill itself.

## Control Surface

- Canonical skill: `skills/reverse-tornado-okr/`
- Claude project skill link: `.claude/skills/reverse-tornado-okr`
- Codex project skill link: `.codex/skills/reverse-tornado-okr`
- Blindbox cases: `evals/blindbox/cases/*.json`
- Eval fixtures: `evals/blindbox/fixtures/*`
- Shared runner: `scripts/okr-runner.py`
- Independent blindbox checkers: `evals/blindbox/checks/*.py`
- Run artifacts: `.runs/` (ignored)

## Default Dogfooding Workflow

This project uses `reverse-tornado-okr` as the default workflow for non-trivial work on the skill,
runner, evals, review harness, release workflow, or OKRA memory. Do not wait for the user to say
"use OKRA" when the task is goal-like or changes the operating surface. Load the project-local skill
from `.codex/skills/reverse-tornado-okr` or `.claude/skills/reverse-tornado-okr`; if the runtime does
not auto-load project skills, read `skills/reverse-tornado-okr/SKILL.md` before acting.

For dogfooded work:

- Draft a candidate objective and measured anti-goal before planning. The default trust anti-goal is
  `single_llm_truth_acceptance_count == 0`.
- Scan available `.okra/memory/**`, active `.okra/runs/**`, and relevant preserved `.runs/**`
  evidence as candidate input, not authority.
- For multi-step or agent-facing changes, use a run-scoped `.okra/runs/<run-id>/` store and append
  check-ins, metric reads, flags, worker progress, and acceptance evidence.
- Do not accept semantic claims, memory promotion, or "done" status from one model narrative alone.
  Use deterministic evidence where possible and independent Codex/Claude or human review for
  judgement-heavy claims.
- When a dogfooded run completes, terminalize it before reuse: record objective and anti-goal reads,
  unresolved flags, accepted learning checkpoints, retained traces, consolidation output, and
  second-opinion evidence. Completed runs may shed bulky detail only after the retained trace can
  still explain why each learned trap, avoidance, or candidate guardrail exists.

## Before Development

Run:

```sh
scripts/validate-skills.sh
scripts/run-blindbox.sh --dry-run --agent both
```

Use the dry-run to inspect prompt packets and bwrap commands before spending model calls.

## Real Eval

Run real isolated evals when credentials and model access are available. Scored runs must pin model
labels through `CODEX_MODEL` and `ANTHROPIC_MODEL` so `result.json` records the model requested by
each CLI. The default scored path runs every blindbox case, including storage governance and
check-in steering:

```sh
CODEX_MODEL=<codex-model> ANTHROPIC_MODEL=<claude-model> \
scripts/run-blindbox.sh --agent both
```

For a narrower smoke pass while iterating, run the core text cases plus the two stateful harness
cases explicitly:

```sh
CODEX_MODEL=<codex-model> ANTHROPIC_MODEL=<claude-model> \
scripts/run-blindbox.sh --agent both --case smoke-reverse-tornado
CODEX_MODEL=<codex-model> ANTHROPIC_MODEL=<claude-model> \
scripts/run-blindbox.sh --agent both --case okra-self-harness
CODEX_MODEL=<codex-model> ANTHROPIC_MODEL=<claude-model> \
scripts/run-blindbox.sh --agent both --case real-life-operations
CODEX_MODEL=<codex-model> ANTHROPIC_MODEL=<claude-model> \
scripts/run-blindbox.sh --agent both --case okra-learning-memory
CODEX_MODEL=<codex-model> ANTHROPIC_MODEL=<claude-model> \
scripts/run-blindbox.sh --agent both --case okra-default-dogfood
CODEX_MODEL=<codex-model> ANTHROPIC_MODEL=<claude-model> \
scripts/run-blindbox.sh --agent both --case okra-storage-governance
CODEX_MODEL=<codex-model> ANTHROPIC_MODEL=<claude-model> \
scripts/run-blindbox.sh --agent both --case okra-checkin-steering
```

Run the Claude model matrix when validating Claude behavior across the current Opus and Sonnet
targets. The default matrix is `claude-opus-4-8` plus `claude-sonnet-5`; override with
`ANTHROPIC_MODEL_MATRIX` only when the current model policy changes:

```sh
scripts/run-claude-model-matrix.sh --case okra-handoff-contracts
```

The matrix wrapper reruns current deterministic checkers over each preserved workspace after a
scored run and writes `recheck.json` beside `result.json`. Recheck also validates the preserved
`result.sha256`, prompt/input hashes, workspace output hashes, changed-path allowlist, and
credential/runtime cleanup checks. When checker code changes or a release verdict needs a no-model
refresh, use:

```sh
scripts/run-claude-model-matrix.sh --recheck-latest --case okra-handoff-contracts
```

The runner copies a fixture into `.runs/blindbox/<run>/workspace`, injects the skill into project-local Claude/Codex skill folders, then executes the selected agent through `bwrap`. The sandbox exposes the eval workspace plus `.runs/blindbox/<run>/runtime/` as writable during execution; runtime contains the per-run agent home, cache, Codex home, and agent output scratch. Runtime scratch is scrubbed after the agent exits, and archived prompt, command, progress, final, and result packets are kept outside writable sandbox mounts. Selected system/tool paths are read-only. It does not mount this host repo into the sandbox, so eval cases and expected checks are not readable by the agent. Network remains available so agent CLIs can call their APIs.

The bwrap environment is cleared before launch, then the runner sets only the per-run HOME, cache,
PATH, and locale variables it needs. Agent auth files are still mounted read-only when required for
model access, so scored runs should use trusted fixtures/prompts or eval-scoped credentials. Results
record input hashes, requested model labels, CLI version, allowed-path checks, and checker timeouts.
The runtime cleanup check verifies `.runs/blindbox/<run>/runtime/` was removed after execution. The
credential artifact audit scans preserved run artifacts outside that directory. Runtime
auth/home/cache/output scratch is controlled by the single `runtime/` directory, ignored by the
preserved-artifact credential check and run-tree hashes, and scrubbed as containment after each
agent exits. If scrub fails and `runtime/` remains, the runtime cleanup check scans and hashes the
leftover scratch before failing the run.

Do not use `--isolation none` for scored runs. The runner refuses it unless `--allow-unisolated`
is passed because unisolated workspaces can read the repo-local eval cases and checkers, and this
path does not mount host agent auth files. Treat it as a structure-only debugging mode.

If bwrap isolation itself looks broken, run:

```sh
python3 scripts/okr-runner.py doctor --check-bwrap
```

## Review

Run both agent review paths before claiming changes to the skill, runner, evals, or workflow are done:

```sh
scripts/review-skill.sh --agent both
```

For a diff-focused review, use:

```sh
scripts/review-skill.sh --agent both --mode diff
```

The Claude diff path receives a precomputed `diff-context.txt` artifact because its review tool
surface is read-only. Diff mode reviews the working tree and index against `HEAD`; it is not a
branch-vs-main review. Untracked file contents are not embedded in `diff-context.txt`; reviewers
must read listed safe untracked paths directly before signing off.

Review outputs land in `.runs/review/`. Address critical findings before merging the workflow into future skill work.
The Claude review path is intentionally read-only by tool surface; use normal development commands, not the review wrapper, when applying fixes.

## Development Rules

- Keep the skill body concise; move longer reusable detail into `references/`.
- Add deterministic scripts only when they remove repeated or fragile work.
- Keep eval prompts separate from expected checks, keep graders under `evals/`, and archive every prompt packet.
- For real-life readiness, require operating-loop behavior: numeric metric contracts, freshness
  rules, heartbeat cadence, lag windows, action envelope, flag lifecycle, and idempotent storage.
- Prefer black-box evals and independent review over self-reported success.
- Do not delete or rewrite unrelated user changes.
