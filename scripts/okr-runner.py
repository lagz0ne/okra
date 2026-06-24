#!/usr/bin/env python3
"""Shared runner for skill validation, review, and blindbox evals."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILL = "reverse-tornado-okr"
CASES_DIR = REPO_ROOT / "evals" / "blindbox" / "cases"
FIXTURES_DIR = REPO_ROOT / "evals" / "blindbox" / "fixtures"
REVIEW_PROMPT = REPO_ROOT / "evals" / "review" / "skill-review.md"
RUN_ROOT = REPO_ROOT / ".runs"
BWRAP_WORKSPACE = "/tmp/workspace"
BWRAP_RUNS = "/tmp/runs"
CHECKERS_DIR = REPO_ROOT / "evals" / "blindbox" / "checks"
GOLDEN_DIR = REPO_ROOT / "evals" / "blindbox" / "golden"
CHECK_TIMEOUT = 60
MAX_SECRET_SCAN_BYTES = 5 * 1024 * 1024
QUICK_VALIDATE = (
    Path.home()
    / ".codex"
    / "skills"
    / ".system"
    / "skill-creator"
    / "scripts"
    / "quick_validate.py"
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("openai_key", re.compile(rb"\bsk-proj-[A-Za-z0-9_-]{20,}\b")),
    ("anthropic_key", re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(rb"\bxox[aboprs]-[A-Za-z0-9-]{20,}\b")),
    ("bearer_token", re.compile(rb"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._-]{30,}")),
    (
        "credential_field",
        re.compile(
            rb'(?i)"(?:access|refresh|session|id|api|auth)[_-]?(?:token|secret|key)"\s*:\s*"[^"\s]{20,}"'
        ),
    ),
)
STRUCTURED_CREDENTIAL_EXTS = {".json", ".toml", ".yaml", ".yml", ".env", ".ini", ".conf", ".config", ".properties"}
TRANSCRIPT_CREDENTIAL_EXTS = {".md", ".log", ".txt"}
SNAPSHOT_EXCLUDED_DIRS = {".git", "__pycache__"}


class RunnerError(RuntimeError):
    pass


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-") or "run"


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def tool_version(name: str) -> str:
    if not command_exists(name):
        return "missing"
    proc = subprocess.run(
        [name, "--version"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
    )
    return (proc.stdout.strip().splitlines() or ["unknown"])[0]


def print_cmd(cmd: list[str]) -> None:
    print("+ " + shlex.join(cmd))


def run_checked(cmd: list[str], *, cwd: Path = REPO_ROOT, dry_run: bool = False) -> int:
    print_cmd(cmd)
    if dry_run:
        return 0
    return subprocess.run(cmd, cwd=cwd).returncode


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_symlink():
        digest.update(b"symlink\0")
        digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        return digest.hexdigest()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for child in sorted(path.rglob("*")):
        if "__pycache__" in child.parts:
            continue
        rel = child.relative_to(path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        if child.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(child).encode("utf-8", errors="surrogateescape"))
        elif child.is_file():
            digest.update(b"file\0")
            digest.update(child.read_bytes())
        else:
            continue
        digest.update(b"\0")
    return digest.hexdigest()


def workspace_snapshot(workspace: Path) -> dict[str, str]:
    """Hash workspace files without trusting mutable Git state."""
    hashes: dict[str, str] = {}
    for child in sorted(workspace.rglob("*")):
        rel = child.relative_to(workspace)
        if any(part in SNAPSHOT_EXCLUDED_DIRS for part in rel.parts):
            continue
        if child.is_file() or child.is_symlink():
            hashes[rel.as_posix()] = sha256_path(child)
    return hashes


def snapshot_changed_paths(workspace: Path, baseline: dict[str, str]) -> list[str]:
    current = workspace_snapshot(workspace)
    paths = {
        path
        for path in set(baseline) | set(current)
        if baseline.get(path) != current.get(path)
    }
    return sorted(paths)


def validate_relative_path(value: Any, *, label: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"{label}: missing path"
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return f"{label}: path must be workspace-relative and cannot contain '..': {value!r}"
    return None


def workspace_path(workspace: Path, rel_path: str) -> Path:
    error = validate_relative_path(rel_path, label="check")
    if error:
        raise RunnerError(error)
    root = workspace.resolve()
    resolved = (workspace / rel_path).resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise RunnerError(f"path escapes workspace: {rel_path}")
    return resolved


def run_logged(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    timeout: int | None = None,
) -> int:
    print_cmd(cmd)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command_path = log_path.parent / f"{log_path.stem}.command.txt"
    command_path.write_text(shlex.join(cmd) + "\n", encoding="utf-8")
    if dry_run:
        log_path.write_text(shlex.join(cmd) + "\n", encoding="utf-8")
        return 0
    with log_path.open("w", encoding="utf-8") as log:
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                input=stdin,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            log.write(f"\nTIMEOUT after {timeout} seconds\n")
            return 124
    return proc.returncode


def agents_from_arg(value: str) -> list[str]:
    if value == "both":
        return ["codex", "claude"]
    return [value]


def skill_path(name: str = DEFAULT_SKILL) -> Path:
    path = REPO_ROOT / "skills" / name
    if not path.exists():
        raise RunnerError(f"missing skill: {path}")
    return path


def load_cases(selected: list[str] | None) -> list[dict[str, Any]]:
    case_files = sorted(CASES_DIR.glob("*.json"))
    cases: list[dict[str, Any]] = []
    selected_set = set(selected or [])
    for path in case_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_path"] = path
        if not selected_set or data["id"] in selected_set:
            cases.append(data)
    missing = selected_set - {case["id"] for case in cases}
    if missing:
        raise RunnerError("unknown case(s): " + ", ".join(sorted(missing)))
    return cases


def validate_cases() -> list[str]:
    errors: list[str] = []
    allowed_checks = {
        "file_exists",
        "file_contains",
        "reverse_tornado_loop",
        "okra_hard_gates",
        "okra_store_governance",
        "okra_checkin_steering",
        "operations_stale_metrics",
    }
    for case in load_cases(None):
        path = case["_path"]
        for key in ("id", "description", "skill", "fixture", "prompt", "checks"):
            if key not in case:
                errors.append(f"{path}: missing {key}")
        if "skill" in case and not (REPO_ROOT / "skills" / case["skill"]).exists():
            errors.append(f"{path}: missing skill {case['skill']}")
        if "fixture" in case and not (FIXTURES_DIR / case["fixture"]).exists():
            errors.append(f"{path}: missing fixture {case['fixture']}")
        if "allowed_paths" not in case:
            errors.append(f"{path}: missing allowed_paths")
            allowed_paths = []
        else:
            allowed_paths = case.get("allowed_paths")
        if not isinstance(allowed_paths, list):
            errors.append(f"{path}: allowed_paths must be a list")
        elif not allowed_paths:
            errors.append(f"{path}: allowed_paths must not be empty")
        else:
            for index, allowed_path in enumerate(allowed_paths):
                error = validate_relative_path(allowed_path, label=f"{path}: allowed_paths {index}")
                if error:
                    errors.append(error)
        checks = case.get("checks")
        if not isinstance(checks, list):
            errors.append(f"{path}: checks must be a list")
            continue
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                errors.append(f"{path}: check {index} must be an object")
                continue
            check_type = check.get("type")
            if check_type not in allowed_checks:
                errors.append(f"{path}: check {index} has unknown type {check_type!r}")
            error = validate_relative_path(check.get("path"), label=f"{path}: check {index}")
            if error:
                errors.append(error)
            if check_type == "file_contains" and not isinstance(check.get("contains"), list):
                errors.append(f"{path}: check {index} file_contains requires contains list")
    return errors


def validate_skill_fallback(path: Path) -> list[str]:
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        return [f"{path}: missing SKILL.md"]
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        return [f"{skill_md}: missing YAML frontmatter"]
    try:
        _, frontmatter, _ = text.split("---", 2)
    except ValueError:
        return [f"{skill_md}: unterminated YAML frontmatter"]
    if not re.search(r"(?m)^name:\s*" + re.escape(path.name) + r"\s*$", frontmatter):
        return [f"{skill_md}: name must match folder {path.name}"]
    if not re.search(r"(?m)^description:\s*(>|\S)", frontmatter):
        return [f"{skill_md}: missing description"]
    if "TODO" in frontmatter:
        return [f"{skill_md}: TODO left in frontmatter"]
    errors = []
    for match in re.finditer(r"`(references/[^`]+)`|\((references/[^)]+)\)", text):
        ref = match.group(1) or match.group(2)
        ref_path = path / ref
        if not ref_path.exists():
            errors.append(f"{skill_md}: missing referenced file {ref}")
    return errors


def validate_project_skill_links() -> list[str]:
    errors = []
    for base in (REPO_ROOT / ".claude" / "skills", REPO_ROOT / ".codex" / "skills"):
        expected = base / DEFAULT_SKILL
        if not expected.is_symlink():
            errors.append(f"{expected}: must be a symlink to ../../skills/{DEFAULT_SKILL}")
            continue
        if expected.resolve() != skill_path(DEFAULT_SKILL).resolve():
            errors.append(f"{expected}: resolves to {expected.resolve()}, expected {skill_path(DEFAULT_SKILL).resolve()}")
    return errors


def validate_store_helper_behavior(*, dry_run: bool = False) -> int:
    helper = skill_path() / "scripts" / "okra-store.sh"
    print_cmd([str(helper), "move-result", "<idempotency-key>", "<payload.json>", "<store>"])
    if dry_run:
        return 0

    with tempfile.TemporaryDirectory(prefix="okra-store-helper-") as tmp:
        root = Path(tmp)
        payload_a = root / "move-a.json"
        payload_b = root / "move-b.json"
        payload_a.write_text('{"type":"move","value":1}\n', encoding="utf-8")
        payload_b.write_text('{"type":"move","value":2}\n', encoding="utf-8")

        def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
            )

        init = run([str(helper), "init", ".okra"])
        if init.returncode:
            print(init.stdout, file=sys.stderr)
            return 1
        init_run = run([str(helper), "init-run", "smoke", ".okra"])
        if init_run.returncode:
            print(init_run.stdout, file=sys.stderr)
            return 1
        run_store = init_run.stdout.strip().splitlines()[-1]
        key = "smoke/frame/hash/node/write/scope/input"

        first = run([str(helper), "move-result", key, str(payload_a), run_store])
        replay = run([str(helper), "move-result", key, str(payload_a), run_store])
        conflict = run([str(helper), "move-result", key, str(payload_b), run_store])
        verify = run([str(helper), "verify", run_store])

        if first.returncode or replay.returncode or conflict.returncode == 0 or verify.returncode:
            print("okra-store helper move-result smoke failed", file=sys.stderr)
            for label, proc in (("first", first), ("replay", replay), ("conflict", conflict), ("verify", verify)):
                print(f"{label}: exit {proc.returncode}\n{proc.stdout}", file=sys.stderr)
            return 1
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    failures = 0
    for path in sorted((REPO_ROOT / "skills").iterdir()):
        if path.is_dir():
            fallback_errors = validate_skill_fallback(path)
            for error in fallback_errors:
                print(error, file=sys.stderr)
            failures += len(fallback_errors)
            if QUICK_VALIDATE.exists():
                failures += run_checked(
                    [sys.executable, str(QUICK_VALIDATE), str(path)],
                    dry_run=args.dry_run,
                )
            else:
                print(f"warning: optional quick validator missing: {QUICK_VALIDATE}", file=sys.stderr)

    for script in sorted((REPO_ROOT / "skills").glob("*/scripts/*.py")):
        failures += run_checked(
            [sys.executable, "-m", "py_compile", str(script)],
            dry_run=args.dry_run,
        )
    for script in sorted(CHECKERS_DIR.glob("*.py")):
        failures += run_checked(
            [sys.executable, "-m", "py_compile", str(script)],
            dry_run=args.dry_run,
        )

    calibrated_checkers = [
        ("reverse_tornado_loop.py", "reverse-tornado-loop"),
        ("okra_hard_gates.py", "okra-hard-gates"),
        ("operations_stale_metrics.py", "operations-stale-metrics"),
        ("okra_store_governance.py", "okra-store-governance"),
        ("okra_checkin_steering.py", "okra-checkin-steering"),
    ]
    for checker_name, golden_name in calibrated_checkers:
        checker = CHECKERS_DIR / checker_name
        golden = GOLDEN_DIR / golden_name
        if not checker.exists():
            print(f"missing calibrated checker: {checker}", file=sys.stderr)
            failures += 1
            continue
        if not golden.exists():
            print(f"missing golden calibration corpus: {golden}", file=sys.stderr)
            failures += 1
            continue
        failures += run_checked(
            [sys.executable, str(checker), "--calibrate", str(golden)],
            dry_run=args.dry_run,
        )

    failures += run_checked(
        [sys.executable, "-m", "py_compile", str(REPO_ROOT / "scripts" / "okr-runner.py")],
        dry_run=args.dry_run,
    )
    failures += run_checked(
        ["bash", "-n", str(skill_path() / "scripts" / "okra-store.sh")],
        dry_run=args.dry_run,
    )
    failures += validate_store_helper_behavior(dry_run=args.dry_run)

    case_errors = validate_cases()
    for error in case_errors:
        print(error, file=sys.stderr)
    failures += len(case_errors)

    link_errors = validate_project_skill_links()
    for error in link_errors:
        print(error, file=sys.stderr)
    failures += len(link_errors)

    if failures:
        print(f"validation failed: {failures} issue(s)", file=sys.stderr)
        return 1
    print("validation ok")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    required = ["python3", "git", "bwrap"]
    agent_tools = ["codex", "claude"]
    missing = [name for name in required + agent_tools if not command_exists(name)]
    for name in required + agent_tools:
        status = "ok" if command_exists(name) else "missing"
        path = shutil.which(name) or "-"
        print(f"{name}: {status} {path}")
    if args.check_bwrap and command_exists("bwrap"):
        if args.dry_run:
            workspace = Path("/tmp/okr-bwrap-dry-workspace")
            run_dir = Path("/tmp/okr-bwrap-dry-run")
            code = run_checked(
                bwrap_prefix(workspace, run_dir)
                + [
                    "/usr/bin/sh",
                    "-c",
                    f"test -r /etc/resolv.conf && test ! -e {shlex.quote(str(REPO_ROOT / 'evals'))}",
                ],
                dry_run=True,
            )
        else:
            with tempfile.TemporaryDirectory(prefix="okr-bwrap-workspace-") as workspace_tmp, tempfile.TemporaryDirectory(
                prefix="okr-bwrap-run-"
            ) as run_tmp:
                workspace = Path(workspace_tmp)
                run_dir = Path(run_tmp)
                (run_dir / "home").mkdir(parents=True, exist_ok=True)
                (run_dir / "cache").mkdir(parents=True, exist_ok=True)
                (run_dir / "agent-output").mkdir(parents=True, exist_ok=True)
                code = run_checked(
                    bwrap_prefix(workspace, run_dir)
                    + [
                        "/usr/bin/sh",
                        "-c",
                        f"test -r /etc/resolv.conf && test ! -e {shlex.quote(str(REPO_ROOT / 'evals'))}",
                    ],
                    dry_run=False,
                )
        if code:
            missing.append("bwrap-smoke")
    return 1 if missing else 0


def review_prompt(mode: str) -> str:
    prompt = REVIEW_PROMPT.read_text(encoding="utf-8")
    return (
        f"{prompt}\n\n"
        f"Repository root: {REPO_ROOT}\n"
        f"Canonical skill: {skill_path()}\n"
        f"Review mode: {mode}\n"
    )


def run_codex_review(mode: str, out_dir: Path, dry_run: bool, timeout: int | None) -> int:
    out_file = out_dir / "codex.md"
    if mode == "diff":
        cmd = ["codex", "exec", "review", "--uncommitted", "-o", str(out_file)]
        return run_logged(cmd, cwd=REPO_ROOT, log_path=out_dir / "codex.log", dry_run=dry_run, timeout=timeout)

    cmd = [
        "codex",
        "exec",
        "--cd",
        str(REPO_ROOT),
        "--sandbox",
        "read-only",
        "--ephemeral",
        "-o",
        str(out_file),
        "-",
    ]
    return run_logged(
        cmd,
        cwd=REPO_ROOT,
        log_path=out_dir / "codex.log",
        stdin=review_prompt(mode),
        dry_run=dry_run,
        timeout=timeout,
    )


def run_claude_review(mode: str, out_dir: Path, dry_run: bool, timeout: int | None) -> int:
    out_file = out_dir / "claude.md"
    prompt = review_prompt(mode)
    if mode == "diff":
        prompt += "\nFor diff mode, inspect `git status --short` and `git diff -- .` before reviewing.\n"
    cmd = [
        "claude",
        "-p",
        "--safe-mode",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "Read,Grep,Glob,LS",
        "--add-dir",
        str(REPO_ROOT),
        "--output-format",
        "text",
        prompt,
    ]
    code = run_logged(cmd, cwd=REPO_ROOT, log_path=out_file, dry_run=dry_run, timeout=timeout)
    return code


def cmd_review(args: argparse.Namespace) -> int:
    out_dir = RUN_ROOT / "review" / f"{timestamp()}-{args.mode}"
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for agent in agents_from_arg(args.agent):
        if not command_exists(agent):
            print(f"missing agent CLI: {agent}", file=sys.stderr)
            failures += 1
            continue
        if agent == "codex":
            failures += run_codex_review(args.mode, out_dir, args.dry_run, args.timeout)
        elif agent == "claude":
            failures += run_claude_review(args.mode, out_dir, args.dry_run, args.timeout)
    print(f"review artifacts: {out_dir}")
    return 1 if failures else 0


def copy_skill_into_workspace(workspace: Path, name: str) -> None:
    src = skill_path(name)
    for base in (workspace / ".claude" / "skills", workspace / ".codex" / "skills"):
        dest = base / name
        base.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)


def prepare_workspace(case: dict[str, Any], run_dir: Path) -> Path:
    fixture = FIXTURES_DIR / case["fixture"]
    workspace = run_dir / "workspace"
    shutil.copytree(fixture, workspace)
    (workspace / "tasks").mkdir(exist_ok=True)
    copy_skill_into_workspace(workspace, case["skill"])
    subprocess.run(["git", "init", "-b", "main"], cwd=workspace, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "add", "-A"], cwd=workspace, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=OKR Eval",
            "-c",
            "user.email=okr-eval@example.invalid",
            "commit",
            "-m",
            "eval baseline",
        ],
        cwd=workspace,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return workspace


def prepare_codex_home(run_dir: Path) -> None:
    codex_home = run_dir / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    for dirname in (".tmp", "tmp", "sessions", "logs", "cache", "shell_snapshots", "skills"):
        (codex_home / dirname).mkdir(parents=True, exist_ok=True)
    (codex_home / "auth.json").touch(exist_ok=True)
    (run_dir / "home").mkdir(parents=True, exist_ok=True)
    (run_dir / "cache").mkdir(parents=True, exist_ok=True)


def prepare_claude_home(run_dir: Path) -> None:
    home = run_dir / "home"
    claude_home = home / ".claude"
    claude_home.mkdir(parents=True, exist_ok=True)
    for dirname in ("session-env", "sessions", "shell-snapshots", "projects", "tasks", "cache"):
        (claude_home / dirname).mkdir(parents=True, exist_ok=True)
    (claude_home / ".credentials.json").touch(exist_ok=True)
    (run_dir / "cache").mkdir(parents=True, exist_ok=True)


def scrub_runtime_state(run_dir: Path) -> None:
    for path in (
        run_dir / "codex-home" / "auth.json",
        run_dir / "home" / ".claude" / ".credentials.json",
    ):
        if path.exists():
            path.unlink()
    for dirname in ("home", "cache", "codex-home", "agent-output"):
        path = run_dir / dirname
        if path.exists():
            shutil.rmtree(path)


def build_case_prompt(case: dict[str, Any], workspace_root: str) -> str:
    skill_name = case["skill"]
    return (
        f"{case['prompt']}\n\n"
        f"Skill name: ${skill_name}\n"
        f"Project-local Claude skill path: {workspace_root}/.claude/skills/"
        f"{skill_name}\n"
        f"Project-local Codex skill path: {workspace_root}/.codex/skills/"
        f"{skill_name}\n"
        "If the runtime does not auto-load project-local skills, read that skill's SKILL.md before working.\n"
        f"Work only inside {workspace_root}. Do not inspect eval case definitions or expected checks.\n"
    )


def bwrap_prefix(workspace: Path, run_dir: Path, agent: str | None = None) -> list[str]:
    env_path = os.environ.get("PATH", "")
    host_home = str(Path.home())
    cmd = [
        "bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--clearenv",
        "--share-net",
        "--proc",
        "/proc",
        "--dev-bind",
        "/dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        BWRAP_WORKSPACE,
        "--dir",
        BWRAP_RUNS,
        "--dir",
        f"{BWRAP_RUNS}/home",
        "--dir",
        f"{BWRAP_RUNS}/cache",
        "--dir",
        f"{BWRAP_RUNS}/agent-output",
        "--dir",
        f"{BWRAP_RUNS}/codex-home",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind-try",
        "/bin",
        "/bin",
        "--ro-bind-try",
        "/lib",
        "/lib",
        "--ro-bind-try",
        "/lib64",
        "/lib64",
        "--ro-bind-try",
        "/etc",
        "/etc",
        "--ro-bind-try",
        "/opt",
        "/opt",
        "--dir",
        "/run",
        "--dir",
        "/run/systemd",
        "--ro-bind-try",
        "/run/systemd/resolve",
        "/run/systemd/resolve",
        "--ro-bind-try",
        "/run/resolvconf",
        "/run/resolvconf",
        "--dir",
        "/home",
        "--dir",
        host_home,
        "--ro-bind-try",
        f"{host_home}/.local/bin",
        f"{host_home}/.local/bin",
        "--ro-bind-try",
        f"{host_home}/.local/share/mise",
        f"{host_home}/.local/share/mise",
        "--ro-bind-try",
        f"{host_home}/.local/share/claude",
        f"{host_home}/.local/share/claude",
        "--bind",
        str(workspace),
        BWRAP_WORKSPACE,
        "--bind",
        str(run_dir / "home"),
        f"{BWRAP_RUNS}/home",
        "--bind",
        str(run_dir / "cache"),
        f"{BWRAP_RUNS}/cache",
        "--bind",
        str(run_dir / "agent-output"),
        f"{BWRAP_RUNS}/agent-output",
        "--bind-try",
        str(run_dir / "codex-home"),
        f"{BWRAP_RUNS}/codex-home",
    ]
    if agent == "codex":
        cmd += [
            "--ro-bind-try",
            f"{host_home}/.codex/auth.json",
            f"{BWRAP_RUNS}/codex-home/auth.json",
        ]
    elif agent == "claude":
        cmd += [
            "--ro-bind-try",
            f"{host_home}/.claude/.credentials.json",
            f"{BWRAP_RUNS}/home/.claude/.credentials.json",
        ]
    cmd += [
        "--setenv",
        "HOME",
        f"{BWRAP_RUNS}/home",
        "--setenv",
        "PATH",
        env_path,
        "--setenv",
        "TMPDIR",
        "/tmp",
        "--setenv",
        "XDG_CACHE_HOME",
        "/tmp/cache",
        "--setenv",
        "LANG",
        "C.UTF-8",
        "--chdir",
        BWRAP_WORKSPACE,
    ]
    return cmd


def model_env_name(agent: str) -> str:
    if agent == "codex":
        return "CODEX_MODEL"
    if agent == "claude":
        return "ANTHROPIC_MODEL"
    return f"{agent.upper()}_MODEL"


def requested_model(agent: str) -> str | None:
    value = os.environ.get(model_env_name(agent))
    return value.strip() if value and value.strip() else None


def agent_command(agent: str, workspace_root: str, runs_root: str) -> list[str]:
    model = requested_model(agent)
    if agent == "codex":
        cmd = [
            "env",
            f"HOME={runs_root}/home",
            f"CODEX_HOME={runs_root}/codex-home",
            f"XDG_CACHE_HOME={runs_root}/cache",
            "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--cd",
            workspace_root,
        ]
        if model:
            cmd += ["--model", model]
        cmd += ["-o", f"{runs_root}/agent-output/final.md", "-"]
        return cmd
    if agent == "claude":
        cmd = [
            "env",
            f"HOME={runs_root}/home",
            f"XDG_CACHE_HOME={runs_root}/cache",
            "claude",
            "-p",
            "--safe-mode",
            "--dangerously-skip-permissions",
            "--no-session-persistence",
            "--output-format",
            "text",
        ]
        if model:
            cmd += ["--model", model]
        return cmd
    raise RunnerError(f"unknown agent: {agent}")


def isolated_command(agent: str, workspace: Path, run_dir: Path, isolation: str) -> list[str]:
    workspace_root = BWRAP_WORKSPACE if isolation == "bwrap" else str(workspace)
    runs_root = BWRAP_RUNS if isolation == "bwrap" else str(run_dir)
    cmd = agent_command(agent, workspace_root, runs_root)
    if isolation == "none":
        return cmd
    return bwrap_prefix(workspace, run_dir, agent) + cmd


def run_agent_case(
    *,
    agent: str,
    case: dict[str, Any],
    run_dir: Path,
    workspace: Path,
    prompt: str,
    isolation: str,
    dry_run: bool,
    timeout: int | None,
) -> int:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    agent_output = run_dir / "agent-output"
    agent_output.mkdir(parents=True, exist_ok=True)
    if agent == "codex":
        prepare_codex_home(run_dir)
    elif agent == "claude":
        prepare_claude_home(run_dir)
    prompt_path = artifacts / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    cmd = isolated_command(agent, workspace, run_dir, isolation)
    if agent == "claude":
        cmd = cmd + [prompt]
        stdin = None
        log_path = artifacts / "final.md"
    else:
        stdin = prompt
        log_path = artifacts / "agent.log"

    try:
        code = run_logged(
            cmd,
            cwd=workspace,
            log_path=log_path,
            stdin=stdin,
            dry_run=dry_run,
            timeout=timeout,
        )
        if agent == "codex" and not dry_run:
            final_output = agent_output / "final.md"
            if final_output.exists():
                shutil.copy2(final_output, artifacts / "final.md")
        if dry_run:
            return 0
        return code
    finally:
        scrub_runtime_state(run_dir)


def git_changed_paths(workspace: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
    )
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return sorted(set(paths))


def is_allowed_changed_path(path: str, allowed_paths: list[str]) -> bool:
    for allowed in allowed_paths:
        normalized = allowed.rstrip("/")
        if path == normalized or path.startswith(normalized + "/"):
            return True
    return False


def evaluate_allowed_paths(
    workspace: Path,
    allowed_paths: list[str],
    baseline: dict[str, str] | None = None,
) -> dict[str, Any]:
    changed = snapshot_changed_paths(workspace, baseline) if baseline is not None else git_changed_paths(workspace)
    unexpected = [path for path in changed if not is_allowed_changed_path(path, allowed_paths)]
    if unexpected:
        detail = "unexpected changes: " + ", ".join(unexpected)
    else:
        detail = "changed paths allowed: " + (", ".join(changed) if changed else "none")
    return {
        "type": "changed_paths_allowlist",
        "path": ",".join(allowed_paths),
        "passed": not unexpected,
        "detail": detail,
        "changed_paths": changed,
    }


def evaluate_credential_artifacts(run_dir: Path) -> dict[str, Any]:
    findings: list[str] = []
    placeholder_paths = {
        Path("codex-home/auth.json"),
        Path("home/.claude/.credentials.json"),
    }
    for path in sorted(run_dir.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(run_dir)
        if rel in placeholder_paths:
            findings.append(f"{rel}: auth placeholder still preserved")
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            findings.append(f"{rel}: unreadable during credential audit: {exc}")
            continue
        if size > MAX_SECRET_SCAN_BYTES:
            findings.append(f"{rel}: exceeds credential scan limit ({size} bytes)")
            continue
        try:
            with path.open("rb") as handle:
                data = handle.read()
        except OSError as exc:
            findings.append(f"{rel}: unreadable during credential audit: {exc}")
            continue
        for name, pattern in SECRET_PATTERNS:
            if (
                name == "credential_field"
                and path.suffix.lower() not in STRUCTURED_CREDENTIAL_EXTS
                and path.suffix.lower() not in TRANSCRIPT_CREDENTIAL_EXTS
                and path.name not in {".env"}
            ):
                continue
            if pattern.search(data):
                findings.append(f"{rel}: matched {name}")
                break

    if findings:
        detail = "potential credential material preserved: " + ", ".join(findings[:10])
        if len(findings) > 10:
            detail += f" (+{len(findings) - 10} more)"
    else:
        detail = "no known credential patterns found in preserved artifacts"
    return {
        "type": "credential_artifact_audit",
        "path": str(run_dir),
        "passed": not findings,
        "detail": detail,
        "findings": findings,
    }


def classify_agent_exit(agent: str, run_dir: Path, code: int) -> str:
    if code == 0:
        return "agent command exited 0"
    if code == 124:
        return "agent command timed out"

    artifacts = run_dir / "artifacts"
    snippets: list[str] = []
    for name in ("final.md", "agent.log"):
        path = artifacts / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            snippets.append(text[:4000])
    combined = "\n".join(snippets)
    if re.search(r"(?i)(failed to authenticate|invalid authentication credentials|api error:\s*401|401)", combined):
        return f"{agent} exited {code}: authentication failure"
    if re.search(r"(?i)(rate limit|too many requests|429)", combined):
        return f"{agent} exited {code}: rate limit"
    if re.search(r"(?i)(timeout|timed out)", combined):
        return f"{agent} exited {code}: timeout"
    if re.search(r"(?i)(permission denied|not allowed|unauthorized)", combined):
        return f"{agent} exited {code}: permission or authorization failure"
    return f"{agent} exited {code}"


def evaluate_agent_execution(agent: str, run_dir: Path, code: int) -> dict[str, Any]:
    return {
        "type": "agent_execution",
        "path": str(run_dir / "artifacts"),
        "passed": code == 0,
        "detail": classify_agent_exit(agent, run_dir, code),
        "exit_code": code,
    }


def changed_path_hashes(workspace: Path, baseline: dict[str, str] | None = None) -> dict[str, str]:
    hashes: dict[str, str] = {}
    changed_paths = snapshot_changed_paths(workspace, baseline) if baseline is not None else git_changed_paths(workspace)
    for rel in changed_paths:
        path = workspace / rel
        if path.exists():
            hashes[rel] = sha256_path(path)
        else:
            hashes[rel] = "deleted"
    return hashes


def output_hashes(run_dir: Path, workspace: Path, baseline: dict[str, str] | None = None) -> dict[str, Any]:
    artifacts = run_dir / "artifacts"
    artifact_files: dict[str, str] = {}
    if artifacts.exists():
        for path in sorted(child for child in artifacts.rglob("*") if child.is_file()):
            artifact_files[path.relative_to(run_dir).as_posix()] = sha256_path(path)
    return {
        "run_tree_sha256_before_result": sha256_path(run_dir),
        "artifacts_tree_sha256": sha256_path(artifacts) if artifacts.exists() else "missing",
        "workspace_tree_sha256": sha256_path(workspace),
        "changed_paths_sha256": changed_path_hashes(workspace, baseline),
        "artifact_files_sha256": artifact_files,
    }


def write_result(run_dir: Path, result: dict[str, Any]) -> None:
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    digest = sha256_path(result_path)
    (run_dir / "result.sha256").write_text(f"{digest}  result.json\n", encoding="utf-8")


def evaluate_checks(workspace: Path, checks: list[dict[str, Any]], *, check_timeout: int = CHECK_TIMEOUT) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for check in checks:
        rel_path = check.get("path")
        try:
            path = workspace_path(workspace, rel_path)
        except RunnerError as exc:
            results.append({**check, "passed": False, "detail": str(exc)})
            continue
        passed = False
        detail = ""
        if check.get("type") == "file_exists":
            passed = path.exists()
            detail = "exists" if passed else "missing"
        elif check.get("type") == "file_contains":
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")
                missing = [needle for needle in check.get("contains", []) if needle not in text]
                passed = not missing
                detail = "all strings present" if passed else "missing: " + ", ".join(missing)
            else:
                detail = "missing file"
        elif check.get("type") == "reverse_tornado_loop":
            script = CHECKERS_DIR / "reverse_tornado_loop.py"
            if not path.exists():
                detail = "missing file"
            elif not script.exists():
                detail = f"missing checker: {script}"
            else:
                try:
                    proc = subprocess.run(
                        [sys.executable, str(script), str(path)],
                        cwd=workspace,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=check_timeout,
                    )
                    passed = proc.returncode == 0
                    detail = proc.stdout.strip()
                except subprocess.TimeoutExpired:
                    detail = f"checker timeout after {check_timeout} seconds"
        elif check.get("type") == "okra_hard_gates":
            script = CHECKERS_DIR / "okra_hard_gates.py"
            if not path.exists():
                detail = "missing file"
            elif not script.exists():
                detail = f"missing checker: {script}"
            else:
                try:
                    proc = subprocess.run(
                        [sys.executable, str(script), str(path)],
                        cwd=workspace,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=check_timeout,
                    )
                    passed = proc.returncode == 0
                    detail = proc.stdout.strip()
                except subprocess.TimeoutExpired:
                    detail = f"checker timeout after {check_timeout} seconds"
        elif check.get("type") == "okra_store_governance":
            script = CHECKERS_DIR / "okra_store_governance.py"
            if not path.exists():
                detail = "missing store"
            elif not script.exists():
                detail = f"missing checker: {script}"
            else:
                try:
                    proc = subprocess.run(
                        [sys.executable, str(script), str(path)],
                        cwd=workspace,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=check_timeout,
                    )
                    passed = proc.returncode == 0
                    detail = proc.stdout.strip()
                except subprocess.TimeoutExpired:
                    detail = f"checker timeout after {check_timeout} seconds"
        elif check.get("type") == "okra_checkin_steering":
            script = CHECKERS_DIR / "okra_checkin_steering.py"
            if not path.exists():
                detail = "missing store"
            elif not script.exists():
                detail = f"missing checker: {script}"
            else:
                try:
                    proc = subprocess.run(
                        [sys.executable, str(script), str(path)],
                        cwd=workspace,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=check_timeout,
                    )
                    passed = proc.returncode == 0
                    detail = proc.stdout.strip()
                except subprocess.TimeoutExpired:
                    detail = f"checker timeout after {check_timeout} seconds"
        elif check.get("type") == "operations_stale_metrics":
            script = CHECKERS_DIR / "operations_stale_metrics.py"
            if not path.exists():
                detail = "missing file"
            elif not script.exists():
                detail = f"missing checker: {script}"
            else:
                try:
                    proc = subprocess.run(
                        [sys.executable, str(script), str(path)],
                        cwd=workspace,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=check_timeout,
                    )
                    passed = proc.returncode == 0
                    detail = proc.stdout.strip()
                except subprocess.TimeoutExpired:
                    detail = f"checker timeout after {check_timeout} seconds"
        else:
            detail = f"unknown check type: {check.get('type')}"
        results.append({**check, "passed": passed, "detail": detail})
    return results


def model_identity(agent: str) -> dict[str, str]:
    env_name = model_env_name(agent)
    requested = requested_model(agent)
    if requested:
        return {"requested": requested, "source": env_name, "delivery": "cli_flag"}
    return {"requested": "cli-default", "source": "unresolved", "delivery": "agent_default"}


def input_hashes(case: dict[str, Any], prompt: str) -> dict[str, Any]:
    checker_hashes: dict[str, str] = {}
    for check in case.get("checks", []):
        checker_type = check.get("type")
        if checker_type == "reverse_tornado_loop":
            script = CHECKERS_DIR / "reverse_tornado_loop.py"
            checker_hashes[script.name] = sha256_path(script) if script.exists() else "missing"
        elif checker_type == "okra_hard_gates":
            script = CHECKERS_DIR / "okra_hard_gates.py"
            checker_hashes[script.name] = sha256_path(script) if script.exists() else "missing"
        elif checker_type == "okra_store_governance":
            script = CHECKERS_DIR / "okra_store_governance.py"
            checker_hashes[script.name] = sha256_path(script) if script.exists() else "missing"
        elif checker_type == "okra_checkin_steering":
            script = CHECKERS_DIR / "okra_checkin_steering.py"
            checker_hashes[script.name] = sha256_path(script) if script.exists() else "missing"
        elif checker_type == "operations_stale_metrics":
            script = CHECKERS_DIR / "operations_stale_metrics.py"
            checker_hashes[script.name] = sha256_path(script) if script.exists() else "missing"
    return {
        "prompt_sha256": sha256_text(prompt),
        "case_sha256": sha256_path(case["_path"]),
        "fixture_sha256": sha256_path(FIXTURES_DIR / case["fixture"]),
        "skill_sha256": sha256_path(skill_path(case["skill"])),
        "runner_sha256": sha256_path(REPO_ROOT / "scripts" / "okr-runner.py"),
        "checker_sha256": checker_hashes,
    }


def cmd_blindbox(args: argparse.Namespace) -> int:
    if args.isolation == "bwrap" and not command_exists("bwrap"):
        raise RunnerError("bwrap is required for --isolation bwrap")
    if args.isolation == "none" and not args.allow_unisolated:
        raise RunnerError(
            "--isolation none exposes eval cases/checks and does not mount host auth files; "
            "pass --allow-unisolated to acknowledge this structure-only path"
        )

    cases = load_cases(args.case)
    keep_going = args.keep_going or args.agent == "both"
    failures = 0
    for case in cases:
        for agent in agents_from_arg(args.agent):
            if not command_exists(agent) and not args.dry_run:
                print(f"missing agent CLI: {agent}", file=sys.stderr)
                failures += 1
                continue
            if not args.dry_run and requested_model(agent) is None:
                print(f"missing explicit model for scored run: set {model_env_name(agent)}", file=sys.stderr)
                failures += 1
                continue
            run_name = f"{timestamp()}-{slug(case['id'])}-{agent}"
            run_dir = RUN_ROOT / "blindbox" / run_name
            workspace = prepare_workspace(case, run_dir)
            baseline_snapshot = workspace_snapshot(workspace)
            workspace_root = BWRAP_WORKSPACE if args.isolation == "bwrap" else str(workspace)
            prompt = build_case_prompt(case, workspace_root)
            runner_error = ""
            try:
                code = run_agent_case(
                    agent=agent,
                    case=case,
                    run_dir=run_dir,
                    workspace=workspace,
                    prompt=prompt,
                    isolation=args.isolation,
                    dry_run=args.dry_run,
                    timeout=args.timeout,
                )
                checks = [] if args.dry_run else [evaluate_agent_execution(agent, run_dir, code)]
                if not args.dry_run:
                    checks.extend(evaluate_checks(workspace, case["checks"]))
                    checks.append(evaluate_allowed_paths(workspace, case["allowed_paths"], baseline_snapshot))
                    checks.append(evaluate_credential_artifacts(run_dir))
            except KeyboardInterrupt:
                code = 130
                runner_error = "runner interrupted; runtime scratch scrubbed and partial result written"
                scrub_runtime_state(run_dir)
                checks = [
                    {
                        "type": "agent_execution",
                        "path": str(run_dir / "artifacts"),
                        "passed": False,
                        "detail": runner_error,
                        "exit_code": code,
                    },
                    evaluate_allowed_paths(workspace, case["allowed_paths"], baseline_snapshot),
                    evaluate_credential_artifacts(run_dir),
                ]
            result = {
                "case": case["id"],
                "agent": agent,
                "fixture": case["fixture"],
                "isolation": args.isolation,
                "timeout": args.timeout,
                "checker_timeout": CHECK_TIMEOUT,
                "keep_going": keep_going,
                "model": model_identity(agent),
                "allowed_paths": case.get("allowed_paths", []),
                "workspace": str(workspace),
                "prompt_path": str(run_dir / "artifacts" / "prompt.md"),
                "command_path": str(
                    run_dir
                    / "artifacts"
                    / ("final.command.txt" if agent == "claude" else "agent.command.txt")
                ),
                "agent_version": tool_version(agent),
                "input_hashes": input_hashes(case, prompt),
                "output_hashes": {} if args.dry_run else output_hashes(run_dir, workspace, baseline_snapshot),
                "credential_policy": (
                    "agent auth file mounted read-only when required; sandbox env is cleared before "
                    "agent launch; runtime home/cache/output scratch directories are scrubbed after "
                    "the agent exits; preserved run artifacts are scanned for known credential patterns; "
                    "runtime scratch containment is deletion, not post-scrub audit coverage"
                ),
                "exit_code": code,
                "dry_run": args.dry_run,
                "runner_error": runner_error,
                "checks": checks,
            }
            write_result(run_dir, result)
            failed_checks = [check for check in checks if not check["passed"]]
            if code or failed_checks:
                failures += 1
                status = "failed"
            else:
                status = "ok"
            print(f"{status}: {case['id']} / {agent} -> {run_dir}")
            if failed_checks:
                for check in failed_checks:
                    print(f"  check failed: {check['type']} {check.get('path')}: {check['detail']}")
            if runner_error:
                return 130
            if failures and not keep_going:
                return 1
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="check local tool availability")
    doctor.add_argument("--check-bwrap", action="store_true", help="run a tiny bwrap smoke command")
    doctor.add_argument("--dry-run", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    validate = sub.add_parser("validate", help="validate skills and eval case files")
    validate.add_argument("--dry-run", action="store_true")
    validate.set_defaults(func=cmd_validate)

    review = sub.add_parser("review", help="run Claude/Codex review")
    review.add_argument("--agent", choices=["codex", "claude", "both"], default="both")
    review.add_argument("--mode", choices=["skill", "diff"], default="skill")
    review.add_argument("--dry-run", action="store_true")
    review.add_argument("--timeout", type=int, default=1800)
    review.set_defaults(func=cmd_review)

    blindbox = sub.add_parser("blindbox", help="run isolated blindbox evals")
    blindbox.add_argument("--agent", choices=["codex", "claude", "both"], default="both")
    blindbox.add_argument("--case", action="append", help="case id to run; defaults to all cases")
    blindbox.add_argument("--isolation", choices=["bwrap", "none"], default="bwrap")
    blindbox.add_argument("--dry-run", action="store_true")
    blindbox.add_argument("--allow-unisolated", action="store_true")
    blindbox.add_argument("--keep-going", action="store_true")
    blindbox.add_argument("--timeout", type=int, default=1800)
    blindbox.set_defaults(func=cmd_blindbox)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
