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

## Before Development

Run:

```sh
scripts/validate-skills.sh
scripts/run-blindbox.sh --dry-run --agent both
```

Use the dry-run to inspect prompt packets and bwrap commands before spending model calls.

## Real Eval

Run a real smoke eval when credentials and model access are available:

```sh
scripts/run-blindbox.sh --agent both --case smoke-reverse-tornado
scripts/run-blindbox.sh --agent both --case real-life-operations
```

The runner copies a fixture into `.runs/blindbox/<run>/workspace`, injects the skill into project-local Claude/Codex skill folders, then executes the selected agent through `bwrap`. The sandbox exposes the eval workspace and run directory as writable, selected system/tool paths as read-only, and per-run writable agent homes. It does not mount this host repo into the sandbox, so eval cases and expected checks are not readable by the agent. Network remains available so agent CLIs can call their APIs.

The bwrap environment is cleared before launch, then the runner sets only the per-run HOME, cache,
PATH, and locale variables it needs. Agent auth files are still mounted read-only when required for
model access, so scored runs should use trusted fixtures/prompts or eval-scoped credentials. Results
record input hashes, CLI version, allowed-path checks, and checker timeouts.

Do not use `--isolation none` for scored runs. The runner refuses it unless `--allow-unisolated` is passed because unisolated workspaces can read the repo-local eval cases and checkers.

## Review

Run both agent review paths before claiming changes to the skill, runner, evals, or workflow are done:

```sh
scripts/review-skill.sh --agent both
```

For a Codex diff-focused review, use:

```sh
scripts/review-skill.sh --agent codex --mode diff
```

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
