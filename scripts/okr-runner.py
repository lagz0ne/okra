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
import threading
import time
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
BWRAP_RUNTIME = f"{BWRAP_RUNS}/runtime"
CHECKERS_DIR = REPO_ROOT / "evals" / "blindbox" / "checks"
GOLDEN_DIR = REPO_ROOT / "evals" / "blindbox" / "golden"
CHECK_TIMEOUT = 60
DEFAULT_HEARTBEAT_SECONDS = 30
MAX_SECRET_SCAN_BYTES = 5 * 1024 * 1024
MAX_DIFF_CONTEXT_FILE_BYTES = 512 * 1024
RUNTIME_DIR_NAME = "runtime"
CHECKER_SCRIPTS = {
    "reverse_tornado_loop": "reverse_tornado_loop.py",
    "okra_hard_gates": "okra_hard_gates.py",
    "okra_store_governance": "okra_store_governance.py",
    "okra_checkin_steering": "okra_checkin_steering.py",
    "okra_learning_memory": "okra_learning_memory.py",
    "okra_handoff_contracts": "okra_handoff_contracts.py",
    "okra_terminal_memory": "okra_terminal_memory.py",
    "okra_terminal_run_store": "okra_terminal_run_store.py",
    "operations_stale_metrics": "operations_stale_metrics.py",
}
BUILTIN_CHECK_TYPES = {"file_exists", "file_contains"}
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
        "env_secret_assignment",
        re.compile(
            rb"\b[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|CREDENTIAL|PASSWORD)[A-Z0-9_]*"
            rb"\s*=\s*(?:[\"'][^\"'\s]{20,}[\"']?|"
            rb"[A-Za-z0-9._~:/+=-]{20,}(?![A-Za-z0-9._~:/+=-]))"
        ),
    ),
    (
        "credential_field",
        re.compile(
            rb'(?i)"(?:access|refresh|session|id|api|auth)[_-]?(?:token|secret|key)"\s*:\s*"[^"\s]{20,}"'
        ),
    ),
    ("json_private_key", re.compile(rb'(?i)"private_key"\s*:\s*"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----')),
    ("private_key_block", re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
)
STRUCTURED_CREDENTIAL_EXTS = {".json", ".toml", ".yaml", ".yml", ".env", ".ini", ".conf", ".config", ".properties"}
TRANSCRIPT_CREDENTIAL_EXTS = {".md", ".log", ".txt"}
SNAPSHOT_EXCLUDED_DIRS = {".git", "__pycache__"}
SENSITIVE_UNTRACKED_NAME = re.compile(
    r"(?i)(^|[/_.-])(?:id_rsa|id_dsa|id_ecdsa|id_ed25519|private[_-]?key|"
    r"service[_-]?account|credentials?|secrets?|token|kubeconfig)(?:$|[/_.-])"
)
SENSITIVE_UNTRACKED_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}
PRIVATE_KEY_BLOCK_TEXT = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)
CLAUDE_ACCOUNT_CONFIG_KEYS = ("oauthAccount", "userID", "machineID")
CLAUDE_OAUTH_ACCOUNT_CONFIG_KEYS = (
    "accountUuid",
    "billingType",
    "organizationRateLimitTier",
    "organizationRole",
    "organizationType",
    "organizationUuid",
    "seatTier",
    "userRateLimitTier",
    "workspaceRole",
)


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


def sha256_path(path: Path, *, exclude_top_level: set[str] | None = None) -> str:
    digest = hashlib.sha256()
    if path.is_symlink():
        digest.update(b"symlink\0")
        digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        return digest.hexdigest()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for child in sorted(path.rglob("*")):
        rel_path = child.relative_to(path)
        if exclude_top_level and rel_path.parts and rel_path.parts[0] in exclude_top_level:
            continue
        if "__pycache__" in child.parts:
            continue
        rel = rel_path.as_posix()
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


def safe_sha256_path(path: Path, *, exclude_top_level: set[str] | None = None) -> tuple[str | None, str | None]:
    try:
        return sha256_path(path, exclude_top_level=exclude_top_level), None
    except OSError as exc:
        return None, str(exc)


def matched_secret_pattern(data: bytes) -> str | None:
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(data):
            return name
    return None


def bounded_context_text(text: str, *, limit: int = MAX_DIFF_CONTEXT_FILE_BYTES) -> str:
    text = PRIVATE_KEY_BLOCK_TEXT.sub("[redacted block: private_key_block]", text)
    lines: list[str] = []
    for line in text.splitlines():
        matched_secret = matched_secret_pattern(line.encode("utf-8", errors="replace"))
        if matched_secret:
            lines.append(f"[redacted line: matched {matched_secret}]")
        else:
            lines.append(line)
    redacted_text = "\n".join(lines)
    data = redacted_text.encode("utf-8", errors="replace")
    if len(data) <= limit:
        return redacted_text.rstrip()
    truncated = data[:limit].decode("utf-8", errors="replace").rstrip()
    return f"{truncated}\n[truncated: {len(data) - limit} bytes omitted]"


def is_sensitive_untracked_path(rel: str) -> bool:
    path = Path(rel)
    name = path.name.lower()
    return (
        name == ".env"
        or name.startswith(".env.")
        or path.suffix.lower() in SENSITIVE_UNTRACKED_SUFFIXES
        or bool(SENSITIVE_UNTRACKED_NAME.search(rel))
    )


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


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_progress(run_dir: Path, payload: dict[str, Any]) -> None:
    path = run_dir / "progress.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"recorded_at": utc_now_iso(), **payload}, sort_keys=True) + "\n")


def path_summary(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"path": str(path), "exists": False}
    if path.is_dir():
        file_count = 0
        latest_mtime = stat.st_mtime
        latest_path = path
        for child in path.rglob("*"):
            try:
                if not child.is_file():
                    continue
                child_mtime = child.stat().st_mtime
            except FileNotFoundError:
                continue
            file_count += 1
            if child_mtime > latest_mtime:
                latest_mtime = child_mtime
                latest_path = child
        return {
            "path": str(path),
            "exists": True,
            "kind": "dir",
            "file_count": file_count,
            "latest_path": str(latest_path),
            "latest_mtime": dt.datetime.fromtimestamp(latest_mtime, dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        }
    return {
        "path": str(path),
        "exists": True,
        "kind": "file",
        "bytes": stat.st_size,
        "mtime": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def heartbeat_line(label: str, elapsed_seconds: int, pid: int, summaries: list[dict[str, Any]]) -> str:
    changed = []
    for summary in summaries:
        if not summary.get("exists"):
            continue
        path = Path(str(summary["path"])).name
        if summary.get("kind") == "dir":
            changed.append(
                f"{path}:files={summary.get('file_count')} "
                f"latest={Path(str(summary.get('latest_path'))).name}@{summary.get('latest_mtime')}"
            )
        else:
            changed.append(f"{path}:bytes={summary.get('bytes')} mtime={summary.get('mtime')}")
    suffix = "; ".join(changed) if changed else "no output files yet"
    return f"heartbeat: {label} elapsed={elapsed_seconds}s pid={pid} {suffix}"


def run_logged(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    timeout: int | None = None,
    label: str = "agent",
    run_dir: Path | None = None,
    monitor_paths: list[Path] | None = None,
    heartbeat_seconds: int = DEFAULT_HEARTBEAT_SECONDS,
) -> int:
    print_cmd(cmd)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command_path = log_path.parent / f"{log_path.stem}.command.txt"
    command_path.write_text(shlex.join(cmd) + "\n", encoding="utf-8")
    run_dir = run_dir or log_path.parent
    monitor_paths = monitor_paths or [log_path]
    if dry_run:
        log_path.write_text(shlex.join(cmd) + "\n", encoding="utf-8")
        append_progress(run_dir, {"event": "agent_dry_run", "label": label, "command_path": str(command_path)})
        return 0

    append_progress(
        run_dir,
        {
            "event": "agent_start",
            "label": label,
            "command_path": str(command_path),
            "timeout_seconds": timeout,
            "heartbeat_seconds": heartbeat_seconds,
        },
    )
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            text=True,
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )
        if stdin is not None and proc.stdin is not None:
            def feed_stdin() -> None:
                try:
                    assert proc.stdin is not None
                    proc.stdin.write(stdin)
                except (BrokenPipeError, OSError):
                    append_progress(run_dir, {"event": "agent_stdin_broken_pipe", "label": label, "pid": proc.pid})
                finally:
                    try:
                        if proc.stdin is not None:
                            proc.stdin.close()
                    except (BrokenPipeError, OSError):
                        pass

            threading.Thread(target=feed_stdin, name=f"{label}-stdin", daemon=True).start()

        started = time.monotonic()
        next_heartbeat = started + max(1, heartbeat_seconds)
        while True:
            code = proc.poll()
            now = time.monotonic()
            if code is not None:
                elapsed = int(now - started)
                summaries = [path_summary(path) for path in monitor_paths]
                append_progress(
                    run_dir,
                    {
                        "event": "agent_exit",
                        "label": label,
                        "exit_code": code,
                        "elapsed_seconds": elapsed,
                        "outputs": summaries,
                    },
                )
                return code

            elapsed = int(now - started)
            if timeout is not None and elapsed >= timeout:
                log.write(f"\nTIMEOUT after {timeout} seconds\n")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                append_progress(
                    run_dir,
                    {"event": "agent_timeout", "label": label, "elapsed_seconds": elapsed, "timeout_seconds": timeout},
                )
                return 124

            if now >= next_heartbeat:
                summaries = [path_summary(path) for path in monitor_paths]
                print(heartbeat_line(label, elapsed, proc.pid, summaries), flush=True)
                append_progress(
                    run_dir,
                    {
                        "event": "agent_heartbeat",
                        "label": label,
                        "elapsed_seconds": elapsed,
                        "pid": proc.pid,
                        "outputs": summaries,
                    },
                )
                next_heartbeat = now + max(1, heartbeat_seconds)
            time.sleep(1)


def agents_from_arg(value: str) -> list[str]:
    if value == "both":
        return ["codex", "claude"]
    return [value]


def skill_path(name: str = DEFAULT_SKILL) -> Path:
    path = REPO_ROOT / "skills" / name
    if not path.exists():
        raise RunnerError(f"missing skill: {path}")
    return path


def runtime_dir(run_dir: Path) -> Path:
    return run_dir / RUNTIME_DIR_NAME


def runtime_home(run_dir: Path) -> Path:
    return runtime_dir(run_dir) / "home"


def runtime_cache(run_dir: Path) -> Path:
    return runtime_dir(run_dir) / "cache"


def runtime_agent_output(run_dir: Path) -> Path:
    return runtime_dir(run_dir) / "agent-output"


def runtime_codex_home(run_dir: Path) -> Path:
    return runtime_dir(run_dir) / "codex-home"


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
    allowed_checks = BUILTIN_CHECK_TYPES | set(CHECKER_SCRIPTS)
    for case in load_cases(None):
        path = case["_path"]
        for key in ("id", "description", "skill", "fixture", "prompt", "checks"):
            if key not in case:
                errors.append(f"{path}: missing {key}")
        for optional_bool in ("inject_skill_context", "honor_project_rules"):
            if optional_bool in case and not isinstance(case[optional_bool], bool):
                errors.append(f"{path}: {optional_bool} must be a boolean")
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
    print_cmd([str(helper), "metric-read", "<payload.json>", "<store>"])
    if dry_run:
        return 0

    with tempfile.TemporaryDirectory(prefix="okra-store-helper-") as tmp:
        root = Path(tmp)
        payload_a = root / "move-a.json"
        payload_b = root / "move-b.json"
        frame = root / "frame.json"
        frame_conflict = root / "frame-conflict.json"
        tree = root / "tree.json"
        metric = root / "metric.json"
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
        frame_payload = {
            "frame_version": "frame.v1",
            "frame_hash": "smoke-frame-hash",
            "objective": {"metric": "smoke_objective", "target": 1},
            "anti_goals": [{"metric": "smoke_breakage_count", "threshold": 0, "type": "tripwire"}],
            "metric_contracts": [{"metric": "smoke_objective", "source_of_truth": "fixture"}],
            "action_envelope": {"allowed": ["helper smoke"], "forbidden": ["external side effects"]},
            "human_approval": {"status": "ratified", "approver": "validator"},
        }
        tree_payload = {
            "tree_version": "tree.v1",
            "frame_version": "frame.v1",
            "orchestrator": {
                "owns": ["objective checks", "check-ins", "OKR board", "subagent steering"],
            },
            "dkrs": [{"id": "DKR-smoke", "worker_scope": "discovery"}],
            "ckrs": [{"id": "CKR-smoke", "kind": "measurable contribution context"}],
            "pkrs": [{"id": "PKR-smoke", "worker_scope": "progression"}],
        }
        frame.write_text(json.dumps(frame_payload) + "\n", encoding="utf-8")
        frame_conflict_payload = {**frame_payload, "objective": {"metric": "changed_objective", "target": 2}}
        frame_conflict.write_text(json.dumps(frame_conflict_payload) + "\n", encoding="utf-8")
        tree.write_text(json.dumps(tree_payload) + "\n", encoding="utf-8")
        metric.write_text(
            json.dumps(
                {
                    "type": "metric_read",
                    "metric_kind": "objective",
                    "metric_id": "objective.smoke",
                    "value": 1,
                    "target": 1,
                    "observed_at": "2026-06-24T00:00:00Z",
                    "source": "helper smoke",
                    "freshness": "observed_at=2026-06-24T00:00:00Z -> status=fresh against max_age=1d",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        write_frame = run([str(helper), "write-frame", str(frame), run_store])
        replay_frame = run([str(helper), "write-frame", str(frame), run_store])
        conflict_frame = run([str(helper), "write-frame", str(frame_conflict), run_store])
        write_tree = run([str(helper), "write-tree", str(tree), run_store])
        metric_read = run([str(helper), "metric-read", str(metric), run_store])
        key = "smoke/frame/hash/node/write/scope/input"

        first = run([str(helper), "move-result", key, str(payload_a), run_store])
        replay = run([str(helper), "move-result", key, str(payload_a), run_store])
        conflict = run([str(helper), "move-result", key, str(payload_b), run_store])
        verify = run([str(helper), "verify", run_store])

        if (
            write_frame.returncode
            or replay_frame.returncode
            or conflict_frame.returncode == 0
            or write_tree.returncode
            or metric_read.returncode
            or first.returncode
            or replay.returncode
            or conflict.returncode == 0
            or verify.returncode
        ):
            print("okra-store helper move-result smoke failed", file=sys.stderr)
            for label, proc in (
                ("write-frame", write_frame),
                ("replay-frame", replay_frame),
                ("conflict-frame", conflict_frame),
                ("write-tree", write_tree),
                ("metric-read", metric_read),
                ("first", first),
                ("replay", replay),
                ("conflict", conflict),
                ("verify", verify),
            ):
                print(f"{label}: exit {proc.returncode}\n{proc.stdout}", file=sys.stderr)
            return 1
    return 0


def validate_secret_patterns(*, dry_run: bool = False) -> int:
    print_cmd(["secret-patterns", "--calibrate"])
    if dry_run:
        return 0
    positives = {
        "env_digits": b"API_TOKEN=abcdefghijklmnopqrstuvwxyz123456",
        "env_alpha": b"SESSION_TOKEN=abcdefghijklmnopqrstuvwx",
        "env_underscore": b"TOKEN=my_secret_token_value_here",
        "env_parenthetical": b"TOKEN=abcdefghij1234567890 (rotated)",
        "openai": b"sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        "private_key": b"-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----",
        "json_private_key": b'{"private_key":"-----BEGIN PRIVATE KEY-----\\nabc"}',
    }
    negatives = {
        "function_call": b"matched_secret = matched_secret_pattern(data)",
        "model_env": b"CODEX_MODEL=gpt-5.5",
        "short_assignment": b"API_TOKEN=short",
    }
    failures = 0
    for label, data in positives.items():
        if matched_secret_pattern(data) is None:
            print(f"secret pattern positive missed: {label}", file=sys.stderr)
            failures += 1
    for label, data in negatives.items():
        matched = matched_secret_pattern(data)
        if matched is not None:
            print(f"secret pattern negative matched: {label} -> {matched}", file=sys.stderr)
            failures += 1
    if not failures:
        print("secret pattern calibration ok")
    return failures


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
        (script_name, check_type.replace("_", "-"))
        for check_type, script_name in sorted(CHECKER_SCRIPTS.items())
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
    failures += run_checked(
        ["bash", "-n", str(REPO_ROOT / "scripts" / "run-claude-model-matrix.sh")],
        dry_run=args.dry_run,
    )
    failures += validate_store_helper_behavior(dry_run=args.dry_run)
    failures += validate_secret_patterns(dry_run=args.dry_run)

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
                runtime_home(run_dir).mkdir(parents=True, exist_ok=True)
                runtime_cache(run_dir).mkdir(parents=True, exist_ok=True)
                runtime_agent_output(run_dir).mkdir(parents=True, exist_ok=True)
                runtime_codex_home(run_dir).mkdir(parents=True, exist_ok=True)
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


def write_diff_context(out_dir: Path) -> Path:
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    diff = subprocess.run(
        ["git", "diff", "--", "."],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    cached_diff = subprocess.run(
        ["git", "diff", "--cached", "--", "."],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    untracked_sections: list[str] = []
    if untracked.returncode == 0:
        for rel in sorted(line for line in untracked.stdout.splitlines() if line.strip()):
            if is_sensitive_untracked_path(rel):
                untracked_sections.append(f"## {rel}\n[skipped: credential-looking path]")
                continue
            raw_path = REPO_ROOT / rel
            if raw_path.is_symlink():
                untracked_sections.append(f"## {rel}\n[symlink: {os.readlink(raw_path)}]")
                continue
            path = raw_path.resolve(strict=False)
            if REPO_ROOT not in path.parents and path != REPO_ROOT:
                untracked_sections.append(f"## {rel}\n[skipped: path escapes repository]")
                continue
            if not path.is_file():
                untracked_sections.append(f"## {rel}\n[skipped: not a regular file]")
                continue
            size = path.stat().st_size
            if size > MAX_DIFF_CONTEXT_FILE_BYTES:
                untracked_sections.append(f"## {rel}\n[skipped: {size} bytes exceeds diff context limit]")
                continue
            untracked_sections.append(f"## {rel}\n[untracked file: {size} bytes; content not embedded]")
    else:
        untracked_sections.append(bounded_context_text(untracked.stdout))
    out_file = out_dir / "diff-context.txt"
    out_file.write_text(
        "\n".join(
            [
                "$ git status --short",
                bounded_context_text(status.stdout),
                f"[exit {status.returncode}]",
                "",
                "$ git diff -- .",
                bounded_context_text(diff.stdout),
                f"[exit {diff.returncode}]",
                "",
                "$ git diff --cached -- .",
                bounded_context_text(cached_diff.stdout),
                f"[exit {cached_diff.returncode}]",
                "",
                "$ git ls-files --others --exclude-standard",
                bounded_context_text(untracked.stdout),
                f"[exit {untracked.returncode}]",
                "",
                "# Untracked file review",
                "Untracked file contents are not embedded in this artifact. For review completeness,",
                "read each listed untracked path directly unless it is marked skipped or credential-looking.",
                "",
                "\n\n".join(untracked_sections),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return out_file


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
        diff_context = write_diff_context(out_dir)
        prompt += (
            "\nFor diff mode, read this precomputed diff context before reviewing: "
            f"{diff_context}\n"
            "If the diff context lists untracked files that are not marked skipped or credential-looking, "
            "read those paths directly before signing off.\n"
        )
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
    codex_home = runtime_codex_home(run_dir)
    codex_home.mkdir(parents=True, exist_ok=True)
    for dirname in (".tmp", "tmp", "sessions", "logs", "cache", "shell_snapshots", "skills"):
        (codex_home / dirname).mkdir(parents=True, exist_ok=True)
    (codex_home / "auth.json").touch(exist_ok=True)
    runtime_home(run_dir).mkdir(parents=True, exist_ok=True)
    runtime_cache(run_dir).mkdir(parents=True, exist_ok=True)


def sanitized_claude_account_config(host_config: Path) -> dict[str, Any]:
    if not host_config.exists():
        return {}
    try:
        data = json.loads(host_config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    sanitized: dict[str, Any] = {}
    for key in CLAUDE_ACCOUNT_CONFIG_KEYS:
        if key not in data:
            continue
        value = data[key]
        if key == "oauthAccount" and isinstance(value, dict):
            sanitized[key] = {
                child_key: value[child_key]
                for child_key in CLAUDE_OAUTH_ACCOUNT_CONFIG_KEYS
                if child_key in value
            }
        else:
            sanitized[key] = value
    return sanitized


def prepare_claude_home(run_dir: Path) -> None:
    home = runtime_home(run_dir)
    claude_home = home / ".claude"
    claude_home.mkdir(parents=True, exist_ok=True)
    for dirname in ("session-env", "sessions", "shell-snapshots", "projects", "tasks", "cache"):
        (claude_home / dirname).mkdir(parents=True, exist_ok=True)
    claude_account_config = sanitized_claude_account_config(Path.home() / ".claude.json")
    (home / ".claude.json").write_text(
        json.dumps(claude_account_config, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (claude_home / ".credentials.json").touch(exist_ok=True)
    runtime_cache(run_dir).mkdir(parents=True, exist_ok=True)


def scrub_runtime_state(run_dir: Path) -> str | None:
    path = runtime_dir(run_dir)
    if path.exists():
        try:
            shutil.rmtree(path)
        except OSError as exc:
            return f"{path}: {exc}"
    return None


def build_case_prompt(case: dict[str, Any], workspace_root: str) -> str:
    skill_name = case["skill"]
    if case.get("inject_skill_context", True):
        skill_context = (
            f"Skill name: ${skill_name}\n"
            f"Project-local Claude skill path: {workspace_root}/.claude/skills/"
            f"{skill_name}\n"
            f"Project-local Codex skill path: {workspace_root}/.codex/skills/"
            f"{skill_name}\n"
            "If the runtime does not auto-load project-local skills, read that skill's SKILL.md before working.\n"
        )
    else:
        skill_context = ""
    return (
        f"{case['prompt']}\n\n"
        f"{skill_context}"
        f"Work only inside {workspace_root}. Do not inspect eval case definitions or expected checks.\n"
    )


def run_verify_gate(case: dict[str, Any], workspace: Path) -> dict[str, Any] | None:
    """Run the skill's PUBLIC completeness gate on the produced artifact.

    Uses the public contract shipped with the skill (contracts/<name>.v1.json) and the
    okra-verify-artifact.py helper. This is the product's own definition-of-done, not the
    hidden eval rubric. Returns the JSON report, or None when the case opts out.
    """
    contract_name = case.get("verify_contract")
    if not contract_name:
        return None
    skill = skill_path(case["skill"])
    contract = skill / "contracts" / contract_name
    verifier = skill / "scripts" / "okra-verify-artifact.py"
    allowed = case.get("allowed_paths") or []
    if not allowed:
        return {"complete": None, "error": "no allowed_paths to verify"}
    artifact = workspace / allowed[0]
    if not (contract.exists() and verifier.exists() and artifact.exists()):
        return {"complete": None, "error": "verify gate assets missing"}
    proc = subprocess.run(
        [sys.executable, str(verifier), str(artifact), "--contract", str(contract), "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"complete": None, "error": (proc.stdout + proc.stderr)[:500]}


def build_repair_prompt(case: dict[str, Any], workspace_root: str, gaps: str) -> str:
    artifact = (case.get("allowed_paths") or ["the task file"])[0]
    return (
        f"The file {artifact} you wrote does not yet satisfy the OKRA public completeness contract "
        f"for a {case['id']} artifact. It is missing the documented, required sections listed below. "
        f"Edit {artifact} to add each one; keep all existing correct content and do not delete sections.\n\n"
        f"Missing (from the skill's own published contract, not any hidden rubric):\n{gaps}\n\n"
        f"Work only inside {workspace_root}. Do not inspect eval case definitions or expected checks. "
        f"After editing, stop.\n"
    )


def load_coherence_review(case: dict[str, Any]) -> list[str]:
    contract_name = case.get("verify_contract")
    if not contract_name:
        return []
    contract = skill_path(case["skill"]) / "contracts" / contract_name
    if not contract.exists():
        return []
    try:
        data = json.loads(contract.read_text(encoding="utf-8"))
    except Exception:
        return []
    rules = data.get("coherence_review") or []
    return [r for r in rules if isinstance(r, str)]


def build_coherence_detect_prompt(case: dict[str, Any], workspace_root: str, rules: list[str]) -> str:
    artifact = (case.get("allowed_paths") or ["the task file"])[0]
    checklist = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
    return (
        f"READ-ONLY REVIEW. Do NOT modify {artifact} or any file. You are auditing {artifact} against "
        f"each OKRA public coherence rule below (each restates a documented rule from the skill, not any "
        f"hidden rubric). Be STRICT and adversarial: your job is to FIND violations, not to reassure.\n\n"
        f"Coherence rules:\n{checklist}\n\n"
        f"For EACH rule, do this in your reply:\n"
        f"- Quote the exact sentence(s) in the artifact most relevant to that rule (search the whole file).\n"
        f"- Then mark it PASS or VIOLATION. Mark VIOLATION whenever a required field is called optional, "
        f"omittable, conditional, or 'need not' be carried; is left empty / none / n/a / tbd; is stated "
        f"only in a definition table but never actually filled in with concrete content; or the rule is "
        f"contradicted anywhere. If genuinely unsure, mark VIOLATION.\n\n"
        f"Then end your reply with exactly one final line:\n"
        f"COHERENCE_VIOLATIONS: NONE   (only if every rule is a clear PASS)\n"
        f"COHERENCE_VIOLATIONS: <comma-separated rule numbers>   (every rule you marked VIOLATION)\n"
        f"Do not edit any file. Work only inside {workspace_root}. Do not inspect eval case definitions."
    )


def build_coherence_prompt(case: dict[str, Any], workspace_root: str, rules: list[str], only: list[int] | None = None) -> str:
    artifact = (case.get("allowed_paths") or ["the task file"])[0]
    chosen = [(i, r) for i, r in enumerate(rules, 1) if not only or i in only]
    checklist = "\n".join(f"{i}. {r}" for i, r in chosen)
    return (
        f"The file {artifact} violates the OKRA public coherence rules below (each restates a documented "
        f"rule from the skill, not any hidden rubric). Make the SMALLEST edits needed to fix ONLY these "
        f"violations -- fix any place where a required field is said to be optional/omittable, is left "
        f"empty, or is contradicted.\n\n"
        f"Rules to fix:\n{checklist}\n\n"
        f"Keep all existing correct content; do not rewrite or delete compliant sections. Work only "
        f"inside {workspace_root}. Do not inspect eval case definitions or expected checks. After editing, stop.\n"
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
        BWRAP_RUNTIME,
        "--dir",
        f"{BWRAP_RUNTIME}/home",
        "--dir",
        f"{BWRAP_RUNTIME}/cache",
        "--dir",
        f"{BWRAP_RUNTIME}/agent-output",
        "--dir",
        f"{BWRAP_RUNTIME}/codex-home",
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
        str(runtime_home(run_dir)),
        f"{BWRAP_RUNTIME}/home",
        "--bind",
        str(runtime_cache(run_dir)),
        f"{BWRAP_RUNTIME}/cache",
        "--bind",
        str(runtime_agent_output(run_dir)),
        f"{BWRAP_RUNTIME}/agent-output",
        "--bind-try",
        str(runtime_codex_home(run_dir)),
        f"{BWRAP_RUNTIME}/codex-home",
    ]
    if agent == "codex":
        cmd += [
            "--ro-bind-try",
            f"{host_home}/.codex/auth.json",
            f"{BWRAP_RUNTIME}/codex-home/auth.json",
        ]
    elif agent == "claude":
        cmd += [
            "--ro-bind-try",
            f"{host_home}/.claude/.credentials.json",
            f"{BWRAP_RUNTIME}/home/.claude/.credentials.json",
        ]
    cmd += [
        "--setenv",
        "HOME",
        f"{BWRAP_RUNTIME}/home",
        "--setenv",
        "PATH",
        env_path,
        "--setenv",
        "TMPDIR",
        "/tmp",
        "--setenv",
        "XDG_CACHE_HOME",
        f"{BWRAP_RUNTIME}/cache",
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


def agent_command(agent: str, workspace_root: str, runs_root: str, *, honor_project_rules: bool = False) -> list[str]:
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
        ]
        if not honor_project_rules:
            cmd.append("--ignore-rules")
        cmd += [
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
        ]
        if not honor_project_rules:
            cmd.append("--safe-mode")
        cmd += [
            "--dangerously-skip-permissions",
            "--no-session-persistence",
            "--output-format",
            "text",
        ]
        if model:
            cmd += ["--model", model]
        return cmd
    raise RunnerError(f"unknown agent: {agent}")


def isolated_command(agent: str, workspace: Path, run_dir: Path, isolation: str, case: dict[str, Any]) -> list[str]:
    workspace_root = BWRAP_WORKSPACE if isolation == "bwrap" else str(workspace)
    runtime_root = BWRAP_RUNTIME if isolation == "bwrap" else str(runtime_dir(run_dir))
    cmd = agent_command(agent, workspace_root, runtime_root, honor_project_rules=case.get("honor_project_rules", False))
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
    heartbeat_seconds: int,
) -> int:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    agent_output = runtime_agent_output(run_dir)
    agent_output.mkdir(parents=True, exist_ok=True)
    if agent == "codex":
        prepare_codex_home(run_dir)
    elif agent == "claude":
        prepare_claude_home(run_dir)
    prompt_path = artifacts / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    cmd = isolated_command(agent, workspace, run_dir, isolation, case)
    if agent == "claude":
        cmd = cmd + [prompt]
        stdin = None
        log_path = artifacts / "final.md"
    else:
        stdin = prompt
        log_path = artifacts / "agent.log"

    try:
        raw_monitor_paths = [
            log_path,
            artifacts / "final.md",
            agent_output / "final.md",
            workspace / "tasks",
            workspace / ".okra",
        ]
        monitor_paths = []
        seen_monitor_paths = set()
        for path in raw_monitor_paths:
            key = str(path)
            if key in seen_monitor_paths:
                continue
            seen_monitor_paths.add(key)
            monitor_paths.append(path)
        code = run_logged(
            cmd,
            cwd=workspace,
            log_path=log_path,
            stdin=stdin,
            dry_run=dry_run,
            timeout=timeout,
            label=f"{case['id']} / {agent}",
            run_dir=run_dir,
            monitor_paths=monitor_paths,
            heartbeat_seconds=heartbeat_seconds,
        )
        if agent == "codex" and not dry_run:
            final_output = agent_output / "final.md"
            if final_output.exists():
                shutil.copy2(final_output, artifacts / "final.md")
        if dry_run:
            return 0
        return code
    finally:
        scrub_error = scrub_runtime_state(run_dir)
        if scrub_error:
            append_progress(run_dir, {"event": "runtime_scrub_failed", "detail": scrub_error})


def git_changed_paths(workspace: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
    )
    if proc.returncode:
        raise RunnerError(f"cannot read workspace git status: {proc.stdout.strip()}")
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
    try:
        changed = snapshot_changed_paths(workspace, baseline) if baseline is not None else git_changed_paths(workspace)
    except RunnerError as exc:
        return {
            "type": "changed_paths_allowlist",
            "path": ",".join(allowed_paths),
            "passed": False,
            "detail": str(exc),
            "changed_paths": [],
        }
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


def credential_findings(root: Path, *, skip_runtime: bool) -> list[str]:
    findings: list[str] = []
    placeholder_paths = {
        Path("codex-home/auth.json"),
        Path("home/.claude/.credentials.json"),
    }

    def on_walk_error(exc: OSError) -> None:
        filename = Path(exc.filename) if exc.filename else root
        try:
            rel = filename.relative_to(root)
        except ValueError:
            rel = filename
        findings.append(f"{rel}: unreadable during credential audit: {exc}")

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=on_walk_error, followlinks=False):
        current = Path(dirpath)
        rel_dir = current.relative_to(root)
        dirnames[:] = sorted(dirnames)
        if skip_runtime:
            if rel_dir.parts and rel_dir.parts[0] == RUNTIME_DIR_NAME:
                dirnames[:] = []
                continue
            if not rel_dir.parts:
                dirnames[:] = [dirname for dirname in dirnames if dirname != RUNTIME_DIR_NAME]
        for filename in sorted(filenames):
            path = current / filename
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(root)
            # The top-level runtime/ tree is covered by runtime_scratch_cleanup,
            # which fails closed and scans/hashes leftovers if scrub does not remove it.
            if skip_runtime and rel.parts and rel.parts[0] == RUNTIME_DIR_NAME:
                continue
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
                    and path.suffix
                ):
                    continue
                if pattern.search(data):
                    findings.append(f"{rel}: matched {name}")
                    break
    return findings


def evaluate_credential_artifacts(run_dir: Path) -> dict[str, Any]:
    findings = credential_findings(run_dir, skip_runtime=True)

    if findings:
        detail = "potential credential material preserved: " + ", ".join(findings[:10])
        if len(findings) > 10:
            detail += f" (+{len(findings) - 10} more)"
    else:
        detail = "no known credential patterns found in preserved artifacts outside runtime/"
    return {
        "type": "credential_artifact_audit",
        "path": str(run_dir),
        "passed": not findings,
        "detail": detail,
        "findings": findings,
    }


def evaluate_runtime_cleanup(run_dir: Path) -> dict[str, Any]:
    path = runtime_dir(run_dir)
    if path.exists():
        findings = credential_findings(path, skip_runtime=False)
        digest, hash_error = safe_sha256_path(path)
        if hash_error:
            findings.append(f".: runtime hash unavailable: {hash_error}")
        detail = (
            "runtime scratch still exists after scrub; leftover scratch scanned"
            + (" and hashed" if not hash_error else "; hash unavailable")
        )
        if findings:
            detail += ": " + ", ".join(findings[:10])
            if len(findings) > 10:
                detail += f" (+{len(findings) - 10} more)"
        passed = False
    else:
        detail = "runtime scratch scrubbed"
        findings = []
        digest = None
        passed = True
    return {
        "type": "runtime_scratch_cleanup",
        "path": str(path),
        "passed": passed,
        "detail": detail,
        "runtime_tree_sha256": digest,
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
    workspace_content_hash = sha256_path(workspace, exclude_top_level={".git"})
    return {
        # runtime/ is intentionally excluded here; runtime_scratch_cleanup emits
        # runtime_tree_sha256 when leftover scratch remains after scrub.
        "run_tree_sha256_before_result": sha256_path(run_dir, exclude_top_level={RUNTIME_DIR_NAME}),
        "artifacts_tree_sha256": sha256_path(artifacts) if artifacts.exists() else "missing",
        "workspace_tree_sha256": workspace_content_hash,
        "workspace_content_sha256": workspace_content_hash,
        "changed_paths_sha256": changed_path_hashes(workspace, baseline),
        "artifact_files_sha256": artifact_files,
    }


def write_result(run_dir: Path, result: dict[str, Any]) -> None:
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    digest = sha256_path(result_path)
    (run_dir / "result.sha256").write_text(f"{digest}  result.json\n", encoding="utf-8")


def evaluate_sha256_sidecar(run_dir: Path, filename: str) -> dict[str, Any]:
    path = run_dir / filename
    sidecar = run_dir / f"{filename.rsplit('.', 1)[0]}.sha256"
    if not path.exists():
        return {
            "type": "sha256_sidecar_integrity",
            "path": filename,
            "passed": False,
            "detail": f"missing {filename}",
        }
    if not sidecar.exists():
        return {
            "type": "sha256_sidecar_integrity",
            "path": str(sidecar.relative_to(run_dir)),
            "passed": False,
            "detail": f"missing {sidecar.name}",
        }
    text = sidecar.read_text(encoding="utf-8", errors="replace").strip()
    parts = text.split()
    expected_hash = parts[0] if parts else ""
    expected_name = parts[-1] if len(parts) >= 2 else ""
    actual_hash = sha256_path(path)
    passed = expected_hash == actual_hash and expected_name == filename
    detail = "sha256 sidecar matches" if passed else (
        f"sha256 sidecar mismatch: expected {expected_hash or '<missing>'} {expected_name or '<missing>'}, "
        f"actual {actual_hash} {filename}"
    )
    return {
        "type": "sha256_sidecar_integrity",
        "path": str(sidecar.relative_to(run_dir)),
        "passed": passed,
        "detail": detail,
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
    }


def expected_prompt_for_result(case: dict[str, Any], result: dict[str, Any], workspace: Path) -> str:
    isolation = result.get("isolation")
    workspace_root = BWRAP_WORKSPACE if isolation == "bwrap" else str(workspace)
    return build_case_prompt(case, workspace_root)


def evaluate_preserved_input_integrity(case: dict[str, Any], result: dict[str, Any], run_dir: Path, workspace: Path) -> dict[str, Any]:
    input_hash = result.get("input_hashes")
    if not isinstance(input_hash, dict):
        return {
            "type": "preserved_input_integrity",
            "path": "result.json",
            "passed": False,
            "detail": "missing input_hashes in result.json",
        }

    prompt_path = run_dir / "artifacts" / "prompt.md"
    mismatches: list[str] = []
    current = {
        "case_sha256": sha256_path(case["_path"]),
        "fixture_sha256": sha256_path(FIXTURES_DIR / case["fixture"]),
        "skill_sha256": sha256_path(skill_path(case["skill"])),
        "prompt_sha256": sha256_text(expected_prompt_for_result(case, result, workspace)),
    }
    for key, digest in current.items():
        if input_hash.get(key) != digest:
            mismatches.append(f"{key}: result={input_hash.get(key, '<missing>')} current={digest}")

    if prompt_path.exists():
        prompt_artifact_hash = sha256_path(prompt_path)
        if input_hash.get("prompt_sha256") != prompt_artifact_hash:
            mismatches.append(
                f"prompt_artifact_sha256: result={input_hash.get('prompt_sha256', '<missing>')} "
                f"artifact={prompt_artifact_hash}"
            )
    else:
        mismatches.append("prompt artifact missing: artifacts/prompt.md")

    detail = "preserved input hashes match current case, fixture, skill, and prompt" if not mismatches else (
        "preserved input drift: " + "; ".join(mismatches)
    )
    return {
        "type": "preserved_input_integrity",
        "path": "result.json",
        "passed": not mismatches,
        "detail": detail,
        "current_input_sha256": current,
    }


def evaluate_preserved_output_integrity(result: dict[str, Any], run_dir: Path, workspace: Path) -> dict[str, Any]:
    output_hash = result.get("output_hashes")
    if not isinstance(output_hash, dict):
        return {
            "type": "preserved_output_integrity",
            "path": "result.json",
            "passed": False,
            "detail": "missing output_hashes in result.json",
        }

    artifacts = run_dir / "artifacts"
    current_artifact_hashes: dict[str, str] = {}
    if artifacts.exists():
        for path in sorted(child for child in artifacts.rglob("*") if child.is_file()):
            current_artifact_hashes[path.relative_to(run_dir).as_posix()] = sha256_path(path)

    try:
        current_changed_hashes = changed_path_hashes(workspace)
    except RunnerError as exc:
        current_changed_hashes = {"<error>": str(exc)}

    current = {
        "artifacts_tree_sha256": sha256_path(artifacts) if artifacts.exists() else "missing",
        "changed_paths_sha256": current_changed_hashes,
        "artifact_files_sha256": current_artifact_hashes,
    }
    skipped_legacy_fields: list[str] = []
    workspace_content_hash = sha256_path(workspace, exclude_top_level={".git"})
    if "workspace_content_sha256" in output_hash:
        current["workspace_content_sha256"] = workspace_content_hash
    elif "workspace_tree_sha256" in output_hash:
        # Older results included .git in workspace_tree_sha256. Git can refresh
        # index metadata during a read-only recheck, so do not treat that legacy
        # hash as portable preserved evidence.
        skipped_legacy_fields.append("workspace_tree_sha256")
    mismatches = [
        f"{key}: result={output_hash.get(key, '<missing>')} current={value}"
        for key, value in current.items()
        if output_hash.get(key) != value
    ]
    if mismatches:
        detail = "preserved output drift: " + "; ".join(mismatches)
    else:
        detail = "preserved output hashes match workspace and artifacts"
        if skipped_legacy_fields:
            detail += "; skipped non-portable legacy fields: " + ", ".join(skipped_legacy_fields)
    return {
        "type": "preserved_output_integrity",
        "path": "result.json",
        "passed": not mismatches,
        "detail": detail,
        "current_output_sha256": current,
        "skipped_legacy_fields": skipped_legacy_fields,
    }


def checker_hashes_for_case(case: dict[str, Any]) -> dict[str, str]:
    checker_hashes: dict[str, str] = {}
    for check in case.get("checks", []):
        script_name = CHECKER_SCRIPTS.get(check.get("type"))
        if not script_name:
            continue
        script = CHECKERS_DIR / script_name
        checker_hashes[script.name] = sha256_path(script) if script.exists() else "missing"
    return checker_hashes


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
        elif check.get("type") in CHECKER_SCRIPTS:
            script = CHECKERS_DIR / CHECKER_SCRIPTS[check["type"]]
            if not path.exists():
                detail = "missing store" if check["type"] in {
                    "okra_store_governance",
                    "okra_checkin_steering",
                    "okra_terminal_run_store",
                } else "missing file"
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
    return {
        "prompt_sha256": sha256_text(prompt),
        "case_sha256": sha256_path(case["_path"]),
        "fixture_sha256": sha256_path(FIXTURES_DIR / case["fixture"]),
        "skill_sha256": sha256_path(skill_path(case["skill"])),
        "runner_sha256": sha256_path(REPO_ROOT / "scripts" / "okr-runner.py"),
        "checker_sha256": checker_hashes_for_case(case),
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
    keep_going = False if args.fail_fast else args.keep_going or args.agent == "both"
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
            run_name = f"{timestamp()}-{slug(case['id'])}-{agent}-{slug(model_identity(agent)['requested'])}"
            run_dir = RUN_ROOT / "blindbox" / run_name
            workspace = prepare_workspace(case, run_dir)
            baseline_snapshot = workspace_snapshot(workspace)
            workspace_root = BWRAP_WORKSPACE if args.isolation == "bwrap" else str(workspace)
            prompt = build_case_prompt(case, workspace_root)
            runner_error = ""
            try:
                print(
                    f"start: {case['id']} / {agent} model={model_identity(agent)['requested']} "
                    f"run_dir={run_dir}",
                    flush=True,
                )
                code = run_agent_case(
                    agent=agent,
                    case=case,
                    run_dir=run_dir,
                    workspace=workspace,
                    prompt=prompt,
                    isolation=args.isolation,
                    dry_run=args.dry_run,
                    timeout=args.timeout,
                    heartbeat_seconds=args.heartbeat_seconds,
                )
                # Opt-in runner-orchestrated produce -> verify -> repair against the skill's
                # PUBLIC completeness gate (never the hidden checkers). Default off => other
                # cases and runs are byte-for-byte unaffected.
                repair_iters = getattr(args, "verify_repair_iterations", 0) or 0
                if not args.dry_run and repair_iters > 0 and case.get("verify_contract"):
                    for attempt in range(1, repair_iters + 1):
                        report = run_verify_gate(case, workspace)
                        if report is None:
                            break
                        (run_dir / "artifacts" / f"verify-{attempt}.json").write_text(
                            json.dumps(report, indent=2) + "\n", encoding="utf-8"
                        )
                        append_progress(run_dir, {
                            "event": "verify_gate",
                            "attempt": attempt,
                            "complete": report.get("complete"),
                            "missing": [m.get("id") for m in report.get("missing", [])],
                        })
                        if report.get("complete") or report.get("complete") is None:
                            break
                        if attempt == repair_iters:
                            break
                        gaps = "\n".join(f"- {m.get('hint', '')}" for m in report.get("missing", []))
                        repair_prompt = build_repair_prompt(case, workspace_root, gaps)
                        code = run_agent_case(
                            agent=agent,
                            case=case,
                            run_dir=run_dir,
                            workspace=workspace,
                            prompt=repair_prompt,
                            isolation=args.isolation,
                            dry_run=args.dry_run,
                            timeout=args.timeout,
                            heartbeat_seconds=args.heartbeat_seconds,
                        )
                    # Two-step public coherence review: read-only DETECT (artifact restored
                    # afterward so it is byte-identical), then FIX only the rules the agent reports
                    # as violated. A compliant artifact is detected clean and never edited (no
                    # regression); a sloppy one is repaired against positive documented rules.
                    coherence_rules = load_coherence_review(case)
                    artifact_file = workspace / (case.get("allowed_paths") or [""])[0]
                    if coherence_rules and artifact_file.is_file():
                        for cround in range(1, 3):  # up to 2 detect->fix rounds; clean artifacts exit round 1
                            pre_detect = artifact_file.read_text(encoding="utf-8")
                            detect_prompt = build_coherence_detect_prompt(case, workspace_root, coherence_rules)
                            run_agent_case(
                                agent=agent, case=case, run_dir=run_dir, workspace=workspace,
                                prompt=detect_prompt, isolation=args.isolation, dry_run=args.dry_run,
                                timeout=args.timeout, heartbeat_seconds=args.heartbeat_seconds,
                            )
                            # guarantee detect is non-mutating
                            artifact_file.write_text(pre_detect, encoding="utf-8")
                            final_md = run_dir / "artifacts" / "final.md"
                            verdict = final_md.read_text(encoding="utf-8", errors="ignore") if final_md.exists() else ""
                            m = re.search(r"COHERENCE_VIOLATIONS:\s*([^\n]*)", verdict, re.IGNORECASE)
                            payload = (m.group(1).strip() if m else "")
                            nums = [int(x) for x in re.findall(r"\d+", payload)] if payload else []
                            violated = bool(nums) and payload.upper() != "NONE"
                            append_progress(run_dir, {
                                "event": "coherence_detect", "round": cround,
                                "verdict": payload[:120], "will_fix": violated,
                            })
                            if not violated:
                                break
                            fix_prompt = build_coherence_prompt(case, workspace_root, coherence_rules, only=nums)
                            code = run_agent_case(
                                agent=agent, case=case, run_dir=run_dir, workspace=workspace,
                                prompt=fix_prompt, isolation=args.isolation, dry_run=args.dry_run,
                                timeout=args.timeout, heartbeat_seconds=args.heartbeat_seconds,
                            )
                            creport = run_verify_gate(case, workspace)
                            if creport is not None:
                                (run_dir / "artifacts" / f"verify-coherence-{cround}.json").write_text(
                                    json.dumps(creport, indent=2) + "\n", encoding="utf-8"
                                )
                checks = [] if args.dry_run else [evaluate_agent_execution(agent, run_dir, code)]
                if not args.dry_run:
                    checks.extend(evaluate_checks(workspace, case["checks"]))
                    checks.append(evaluate_allowed_paths(workspace, case["allowed_paths"], baseline_snapshot))
                    checks.append(evaluate_runtime_cleanup(run_dir))
                    checks.append(evaluate_credential_artifacts(run_dir))
            except KeyboardInterrupt:
                code = 130
                runner_error = "runner interrupted; runtime scratch scrubbed and partial result written"
                scrub_error = scrub_runtime_state(run_dir)
                if scrub_error:
                    runner_error = f"{runner_error}; runtime scrub failed: {scrub_error}"
                    append_progress(run_dir, {"event": "runtime_scrub_failed", "detail": scrub_error})
                checks = [
                    {
                        "type": "agent_execution",
                        "path": str(run_dir / "artifacts"),
                        "passed": False,
                        "detail": runner_error,
                        "exit_code": code,
                    },
                    evaluate_allowed_paths(workspace, case["allowed_paths"], baseline_snapshot),
                    evaluate_runtime_cleanup(run_dir),
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
                    "agent auth files mounted read-only when required; Claude account config is minimized into "
                    "runtime home before launch; sandbox env is cleared before agent launch; "
                    "runtime home/cache/output scratch lives under run_dir/runtime/ and "
                    "is checked for post-run removal; preserved run artifacts and run-tree hashes outside "
                    "runtime/ are scanned for known credential patterns; if runtime/ remains after scrub, "
                    "the runtime cleanup check scans and hashes that leftover scratch"
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


def latest_blindbox_run(case_id: str, agent: str, model: str) -> Path:
    pattern = f"*-{slug(case_id)}-{slug(agent)}-{slug(model)}"
    matches: list[Path] = []
    for path in sorted(path for path in (RUN_ROOT / "blindbox").glob(pattern) if path.is_dir()):
        result_path = path / "result.json"
        if not result_path.exists():
            continue
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if result.get("dry_run"):
            continue
        matches.append(path)
    if not matches:
        raise RunnerError(f"no preserved blindbox run found for case={case_id} agent={agent} model={model}")
    return matches[-1]


def recheck_blindbox_run(run_dir: Path, *, forced_case: str | None, write: bool) -> tuple[dict[str, Any], bool]:
    run_dir = run_dir.resolve()
    result_path = run_dir / "result.json"
    if not result_path.exists():
        raise RunnerError(f"missing result.json: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    case_id = forced_case or result.get("case")
    if not isinstance(case_id, str) or not case_id:
        raise RunnerError(f"cannot infer case for {run_dir}; pass --case")
    case = load_cases([case_id])[0]
    workspace = run_dir / "workspace"
    if not workspace.exists():
        raise RunnerError(f"missing preserved workspace: {workspace}")

    checks = [
        evaluate_sha256_sidecar(run_dir, "result.json"),
        evaluate_preserved_input_integrity(case, result, run_dir, workspace),
        evaluate_preserved_output_integrity(result, run_dir, workspace),
    ]
    checks.extend(evaluate_checks(workspace, case["checks"]))
    checks.append(evaluate_allowed_paths(workspace, case["allowed_paths"]))
    checks.append(evaluate_runtime_cleanup(run_dir))
    checks.append(evaluate_credential_artifacts(run_dir))

    failed_checks = [check for check in checks if not check["passed"]]
    recheck = {
        "type": "blindbox_recheck",
        "run_dir": str(run_dir),
        "case": case_id,
        "agent": result.get("agent"),
        "model": result.get("model"),
        "rechecked_at": utc_now_iso(),
        "current_case_sha256": sha256_path(case["_path"]),
        "current_checker_sha256": checker_hashes_for_case(case),
        "preserved_result_sha256": sha256_path(result_path),
        "checks": checks,
        "passed": not failed_checks,
    }
    if write:
        path = run_dir / "recheck.json"
        path.write_text(json.dumps(recheck, indent=2) + "\n", encoding="utf-8")
        (run_dir / "recheck.sha256").write_text(f"{sha256_path(path)}  recheck.json\n", encoding="utf-8")
    return recheck, not failed_checks


def cmd_recheck_blindbox(args: argparse.Namespace) -> int:
    run_dirs = [Path(path) for path in args.run_dir]
    if args.latest:
        if run_dirs:
            raise RunnerError("pass either explicit run dirs or --latest, not both")
        model = args.model or requested_model(args.agent)
        if not model:
            raise RunnerError("--latest requires --model or the agent model env var")
        cases = load_cases(args.case)
        run_dirs = [latest_blindbox_run(case["id"], args.agent, model) for case in cases]
    if not run_dirs:
        raise RunnerError("provide at least one run dir or pass --latest")

    failures = 0
    records: list[dict[str, Any]] = []
    forced_case = args.case[0] if args.case and len(args.case) == 1 else None
    for run_dir in run_dirs:
        recheck, passed = recheck_blindbox_run(run_dir, forced_case=forced_case, write=not args.no_write)
        records.append(recheck)
        status = "ok" if passed else "failed"
        model = recheck.get("model")
        model_label = model.get("requested") if isinstance(model, dict) else model
        print(f"recheck {status}: {recheck['case']} / {recheck.get('agent')} model={model_label} -> {recheck['run_dir']}")
        for check in recheck["checks"]:
            if not check["passed"]:
                print(f"  check failed: {check['type']} {check.get('path')}: {check['detail']}")
        if not passed:
            failures += 1
    if args.json:
        print(json.dumps(records, indent=2))
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
    blindbox.add_argument("--fail-fast", action="store_true", help="stop after the first failed case")
    blindbox.add_argument("--timeout", type=int, default=1800)
    blindbox.add_argument("--heartbeat-seconds", type=int, default=DEFAULT_HEARTBEAT_SECONDS)
    blindbox.add_argument(
        "--verify-repair-iterations",
        type=int,
        default=0,
        help="opt-in: runner-orchestrated produce->verify->repair against the skill's public "
        "completeness gate for cases that declare verify_contract (0 = off, current behavior)",
    )
    blindbox.set_defaults(func=cmd_blindbox)

    recheck = sub.add_parser("recheck-blindbox", help="rerun deterministic checks over preserved blindbox artifacts")
    recheck.add_argument("run_dir", nargs="*", help="preserved .runs/blindbox/<run> directories to recheck")
    recheck.add_argument("--latest", action="store_true", help="recheck the latest run for each selected case/model")
    recheck.add_argument("--agent", choices=["codex", "claude"], default="claude")
    recheck.add_argument("--model", help="model label used in the preserved run name")
    recheck.add_argument("--case", action="append", help="case id; with --latest, selects cases; with one explicit run dir, overrides inference")
    recheck.add_argument("--no-write", action="store_true", help="do not write recheck.json next to result.json")
    recheck.add_argument("--json", action="store_true", help="also print machine-readable recheck records")
    recheck.set_defaults(func=cmd_recheck_blindbox)

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
