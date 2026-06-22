# Okra

Okra packages the `reverse-tornado-okr` skill: a workflow for turning a goal into a measured,
self-correcting OKR loop with an anti-goal guardrail.

The repo is set up as both a skill development workspace and a releasable plugin:

- Claude Code plugin manifest: `.claude-plugin/plugin.json`
- Codex plugin manifest: `.codex-plugin/plugin.json`
- Canonical skill: `skills/reverse-tornado-okr/SKILL.md`
- Blindbox evals: `evals/blindbox/`
- Review prompt: `evals/review/skill-review.md`
- Runner: `scripts/okr-runner.py`

## What The Skill Does

Use the skill when a user is setting OKRs, defining measurable goals, planning a roadmap toward a
metric, or delegating goal execution while keeping human control of direction.

It produces:

- objective and target metric
- measured anti-goal and guardrail type
- DKR/CKR/PKR decomposition
- three-point anti-goal evaluation
- escalation flags and human-owned frame
- operating-loop cadence for recurring or automated runs

For real-life runs, the skill requires metric freshness contracts, heartbeat cadence, lag windows,
flag lifecycle, action envelope, and idempotent storage.

## Claude Code

Validate the plugin locally:

```sh
claude plugin validate . --strict
claude plugin tag --dry-run .
```

Install from GitHub after the repository is published:

```sh
claude plugin marketplace add lagz0ne/okra
claude plugin install okra@okra-marketplace
```

The unqualified `claude plugin install okra` also works when no other configured marketplace exposes
an `okra` plugin.

## Codex

Validate the skill and eval harness:

```sh
scripts/validate-skills.sh
scripts/run-blindbox.sh --dry-run --agent both
```

The repo-local skill links are:

```text
.claude/skills/reverse-tornado-okr -> ../../skills/reverse-tornado-okr
.codex/skills/reverse-tornado-okr -> ../../skills/reverse-tornado-okr
```

## Real Eval

Run a real isolated eval when Claude/Codex credentials are available:

```sh
scripts/run-blindbox.sh --agent both --case real-life-operations
```

The runner copies a fixture into `.runs/`, injects the skill into a disposable workspace, launches
the selected agent through `bwrap`, and preserves prompts, logs, outputs, hashes, and check results.

## Review

Before releasing skill or harness changes, run:

```sh
scripts/review-skill.sh --agent both
```

Review outputs land under `.runs/review/`.

## Release

The plugin version lives in both manifests:

- `.claude-plugin/plugin.json`
- `.codex-plugin/plugin.json`

For a Claude Code release tag:

```sh
claude plugin validate . --strict
claude plugin tag .
git push origin main --tags
```

## License

MIT
