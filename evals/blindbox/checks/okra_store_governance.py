#!/usr/bin/env python3
"""Black-box store governance checks for OKRA blindbox runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


TARGET_ARTIFACT = Path("tasks/okra-governed-loop.md")
TARGET_RUN_ID = "storage-governance"
SOURCE_FILES = [Path("README.md"), Path("inputs/current-signals.md")]
LOG_NAMES = ("ledger", "flags", "checkins")
EXPECTED_FAIL_PATTERNS = {
    "empty-worker-progress": r"empty worker progress report",
    "flat-store": r"missing run-scoped OKRA store",
    "missing-worker-progress": r"missing worker progress directory|missing worker progress reports",
    "nonzero-anti-goal": r"ledger anti-goal metric is not zero",
}


def canonical_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def store_root(store: Path) -> Path:
    if store.parent.name == "runs":
        return store.parent.parent
    return store


def workspace_for_store(store: Path) -> Path:
    return store_root(store).parent


def content_dir_for_store(store: Path) -> Path:
    return store_root(store) / "content" / "sha256"


def display_path(path: Path, store: Path) -> str:
    try:
        return path.relative_to(workspace_for_store(store)).as_posix()
    except ValueError:
        return str(path)


def load_log(store: Path, name: str, errors: list[str]) -> list[dict[str, Any]]:
    path = store / f"{name}.jsonl"
    if not path.exists():
        errors.append(f"missing log: {display_path(path, store)}")
        return []

    records: list[dict[str, Any]] = []
    prev = "GENESIS"
    expected_seq = 1
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        label = f"{display_path(path, store)}:{lineno}"
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{label}: invalid json: {exc}")
            continue

        if record.get("seq") != expected_seq:
            errors.append(f"{label}: expected seq {expected_seq}, got {record.get('seq')}")
        if record.get("prev_hash") != prev:
            errors.append(f"{label}: prev_hash mismatch")

        payload = record.get("payload")
        if record.get("payload_sha256") != canonical_hash(payload):
            errors.append(f"{label}: payload_sha256 mismatch")

        without_hash = {key: value for key, value in record.items() if key != "record_hash"}
        record_hash = canonical_hash(without_hash)
        if record.get("record_hash") != record_hash:
            errors.append(f"{label}: record_hash mismatch")

        prev = str(record.get("record_hash", ""))
        expected_seq += 1
        records.append(record)
    return records


def load_worker_progress(store: Path, errors: list[str]) -> list[dict[str, Any]]:
    workers = store / "workers"
    if not workers.is_dir():
        errors.append(f"missing worker progress directory: {display_path(workers, store)}")
        return []

    progress_files = sorted(workers.glob("*/progress.jsonl"))
    if not progress_files:
        errors.append(f"missing worker progress reports: {display_path(workers, store)}/*/progress.jsonl")
        return []

    records: list[dict[str, Any]] = []
    for path in progress_files:
        prev = "GENESIS"
        expected_seq = 1
        file_record_count = 0
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if not line.strip():
                continue
            label = f"{display_path(path, store)}:{lineno}"
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{label}: invalid json: {exc}")
                continue

            if record.get("seq") != expected_seq:
                errors.append(f"{label}: expected seq {expected_seq}, got {record.get('seq')}")
            if record.get("prev_hash") != prev:
                errors.append(f"{label}: prev_hash mismatch")

            payload = record.get("payload")
            if record.get("payload_sha256") != canonical_hash(payload):
                errors.append(f"{label}: payload_sha256 mismatch")

            without_hash = {key: value for key, value in record.items() if key != "record_hash"}
            record_hash = canonical_hash(without_hash)
            if record.get("record_hash") != record_hash:
                errors.append(f"{label}: record_hash mismatch")

            prev = str(record.get("record_hash", ""))
            expected_seq += 1
            file_record_count += 1
            records.append(record)
        if file_record_count == 0:
            errors.append(f"empty worker progress report: {display_path(path, store)}")
    return records


def hash_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"content_sha256", "source_content_sha256", "target_content_sha256"} and isinstance(child, str):
                refs.append(child)
            refs.extend(hash_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(hash_refs(child))
    return refs


def payload_type(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("record_type", "record_kind", "kind", "event", "type"):
        value = payload.get(key)
        if value is not None:
            return str(value).lower()
    return ""


def payload_text(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).lower()


def is_zero(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, str):
        return value.strip().lower() in {"0", "0.0", "zero"}
    return False


def normalized_target(value: Any, workspace: Path | None = None) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = value.strip()
    if cleaned.startswith("/tmp/workspace/"):
        cleaned = cleaned.removeprefix("/tmp/workspace/")
    elif workspace is not None:
        try:
            path = Path(cleaned)
            if path.is_absolute():
                cleaned = path.resolve(strict=False).relative_to(workspace.resolve()).as_posix()
        except ValueError:
            pass
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def has_pattern(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None


def load_json_object(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing {label}: {display_path(path, path.parent.parent)}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{display_path(path, path.parent.parent)}: invalid json: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{display_path(path, path.parent.parent)}: {label} must be an object")
        return {}
    return value


def check_frame_tree(store: Path, errors: list[str]) -> None:
    frame = load_json_object(store / "frame" / "frame.v1.json", errors, "ratified frame")
    tree = load_json_object(store / "tree" / "tree.v1.json", errors, "OKR tree")

    frame_text = payload_text(frame)
    if frame:
        for key in ("frame_version", "objective", "anti_goals", "metric_contracts", "action_envelope"):
            if key not in frame:
                errors.append(f"frame missing {key}")
        if "human_approval" not in frame_text and "ratified" not in frame_text:
            errors.append("frame lacks human approval or ratification evidence")
        if "frame_hash" not in frame:
            errors.append("frame lacks frame_hash")
        if not (store / "frame" / "current").exists():
            errors.append("frame lacks frame/current pointer")

    tree_text = payload_text(tree)
    if tree:
        for key in ("tree_version", "frame_version", "orchestrator", "dkrs", "ckrs", "pkrs"):
            if key not in tree:
                errors.append(f"tree missing {key}")
        if "objective checks" not in tree_text or "subagent steering" not in tree_text:
            errors.append("tree lacks orchestrator ownership of objective checks and subagent steering")
        if not (store / "tree" / "current").exists():
            errors.append("tree lacks tree/current pointer")


def check_content_store(store: Path, records: dict[str, list[dict[str, Any]]], errors: list[str]) -> None:
    content_dir = content_dir_for_store(store)
    if not content_dir.is_dir():
        errors.append("missing content-addressed store: .okra/content/sha256")
        return

    for path in sorted(content_dir.iterdir()):
        if not path.is_file():
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", path.name):
            errors.append(f"content file is not a sha256 name: {display_path(path, store)}")
            continue
        digest = file_hash(path)
        if digest != path.name:
            errors.append(f"content hash mismatch: {display_path(path, store)}")

    for name, log_records in records.items():
        for index, record in enumerate(log_records, start=1):
            for ref in hash_refs(record.get("payload")):
                if not (content_dir / ref).is_file():
                    errors.append(f".okra/{name}.jsonl:{index}: missing referenced content hash: {ref}")


def log_status_summary(path: Path) -> tuple[int, str]:
    if not path.exists():
        return 0, "-"
    lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    if not lines:
        return 0, "-"
    try:
        record = json.loads(lines[-1])
    except json.JSONDecodeError:
        return len(lines), "<invalid-json>"
    return len(lines), str(record.get("record_hash", "-"))


def status_row_present(text: str, name: str, count: int, last_hash: str) -> bool:
    pattern = rf"\|\s*{re.escape(name)}\s*\|\s*{count}\s*\|\s*`{re.escape(last_hash)}`\s*\|"
    return has_pattern(pattern, text)


def check_status(store: Path, errors: list[str]) -> None:
    status = store / "status.md"
    if not status.exists():
        errors.append("missing generated status: .okra/status.md")
        return

    text = status.read_text(encoding="utf-8", errors="replace")
    if "Generated from append-only source records." not in text or "Do not edit it by hand." not in text:
        errors.append(".okra/status.md does not look like the generated helper status")

    for name in LOG_NAMES:
        count, last_hash = log_status_summary(store / f"{name}.jsonl")
        if not status_row_present(text, name, count, last_hash):
            errors.append(f".okra/status.md is stale for {name} log")

    worker_count = 0
    workers = store / "workers"
    if workers.exists():
        for source in workers.glob("*/progress.jsonl"):
            worker_count += len(
                [line for line in source.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
            )
    if not status_row_present(text, "worker progress", worker_count, "per-worker logs"):
        errors.append(".okra/status.md is stale for worker progress logs")


def check_source_reads(workspace: Path, store: Path, checkins: list[dict[str, Any]], errors: list[str]) -> None:
    content_dir = content_dir_for_store(store)
    read_hashes = {
        payload.get("content_sha256")
        for record in checkins
        if isinstance((payload := record.get("payload")), dict)
        and payload_type(payload) in {"content_read", "source_read"}
    }

    for rel in SOURCE_FILES:
        source = workspace / rel
        if not source.exists():
            errors.append(f"missing expected source fixture: {rel}")
            continue
        digest = file_hash(source)
        if not (content_dir / digest).is_file():
            errors.append(f"source file was not stored by content hash: {rel}")
        if digest not in read_hashes:
            errors.append(f"source file was not read through governed content record: {rel}")


def check_final_write(workspace: Path, store: Path, checkins: list[dict[str, Any]], errors: list[str]) -> None:
    target = workspace / TARGET_ARTIFACT
    if not target.exists():
        errors.append(f"missing target artifact: {TARGET_ARTIFACT}")
        return

    target_hash = file_hash(target)
    content_dir = content_dir_for_store(store)
    if not (content_dir / target_hash).is_file():
        errors.append("target artifact content is not stored by hash")

    writes = []
    for record in checkins:
        payload = record.get("payload")
        if isinstance(payload, dict) and payload_type(payload) == "content_write":
            writes.append(payload)

    matching = [
        payload
        for payload in writes
        if normalized_target(payload.get("target"), workspace) == TARGET_ARTIFACT.as_posix()
        and payload.get("content_sha256") == target_hash
    ]
    if not matching:
        errors.append("target artifact lacks matching content_write record with actual content hash")


def check_metric_and_checkin_records(records: dict[str, list[dict[str, Any]]], errors: list[str]) -> None:
    ledger_payloads = [record.get("payload") for record in records.get("ledger", [])]
    ledger_text = "\n".join(payload_text(payload) for payload in ledger_payloads)
    has_objective_read = any(
        isinstance(payload, dict)
        and payload_type(payload) in {"metric_read", "direct_metric_read", "objective_metric_read", "objective_read"}
        and (
            "objective" in payload_text(payload)
            or str(payload.get("metric_id", "")).lower().startswith(("obj", "objective"))
            or ("target" in payload and payload_type(payload) == "metric_read")
        )
        for payload in ledger_payloads
    )
    if not has_objective_read:
        errors.append("ledger lacks objective metric read")
    for needle in ("ungoverned_direct_read", "ungoverned_direct_write", "single_llm_truth"):
        matching_payloads = [
            payload
            for payload in ledger_payloads
            if isinstance(payload, dict)
            and payload_type(payload) in {"metric_read", "direct_metric_read", "anti_goal_metric_read", "anti_goal_read"}
            and needle in payload_text(payload)
        ]
        if not matching_payloads:
            errors.append(f"ledger lacks anti-goal metric read: {needle}")
        elif not any(is_zero(payload.get("value")) for payload in matching_payloads):
            errors.append(f"ledger anti-goal metric is not zero: {needle}")

    checkin_payloads = [record.get("payload") for record in records.get("checkins", [])]
    checkins = [payload for payload in checkin_payloads if isinstance(payload, dict)]
    has_operating_checkin = any(
        payload_type(payload) in {"check_in", "checkin", "heartbeat", "steering_checkin"}
        and "pkr_signals" in payload
        and "steering_decision" in payload
        and "worker_progress_refs" in payload
        for payload in checkins
    )
    if not has_operating_checkin:
        errors.append("checkins lack worker_progress_refs plus PKR signals and steering decision")


def check_worker_progress(records: dict[str, list[dict[str, Any]]], errors: list[str]) -> None:
    payloads = [record.get("payload") for record in records.get("worker_progress", [])]
    text = "\n".join(payload_text(payload) for payload in payloads)
    if not payloads:
        return
    if not has_pattern(r"\b(DKR|discovery|PKR|progression)\b", text):
        errors.append("worker progress reports do not identify DKR/PKR worker scope")
    if not has_pattern(r"(learning_collected|learning|probability|confidence|next_unknown|next unknown)", text):
        errors.append("worker progress reports lack DKR learning/probability signal")
    if not has_pattern(r"(next_report_at|10[- ]?minute|ten[- ]minute)", text):
        errors.append("worker progress reports lack time-based next_report_at heartbeat")


def check_move_results(store: Path, errors: list[str]) -> None:
    moves = store / "moves"
    if not moves.is_dir():
        errors.append("missing idempotency move-results directory: .okra/runs/<run-id>/moves")
        return
    move_files = sorted(moves.glob("*.json"))
    if not move_files:
        errors.append("missing idempotency move result")
        return
    for path in move_files:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{display_path(path, store)}: invalid json: {exc}")
            continue
        key = record.get("idempotency_key")
        payload = record.get("payload")
        if not isinstance(key, str) or not key:
            errors.append(f"{display_path(path, store)}: missing idempotency_key")
            continue
        key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
        if path.stem != key_hash or record.get("key_sha256") != key_hash:
            errors.append(f"{display_path(path, store)}: idempotency key hash mismatch")
        if record.get("payload_sha256") != canonical_hash(payload):
            errors.append(f"{display_path(path, store)}: payload_sha256 mismatch")
        if "committed_at" not in record:
            errors.append(f"{display_path(path, store)}: missing committed_at")


def check_acceptance_evidence(records: dict[str, list[dict[str, Any]]], artifact_text: str, errors: list[str]) -> None:
    checkins = [
        record.get("payload")
        for record in records.get("checkins", [])
        if isinstance(record.get("payload"), dict)
    ]
    evidence_records = [
        payload
        for payload in checkins
        if payload_type(payload) in {"acceptance_evidence", "independent_evidence", "acceptance_evidence_checkin"}
    ]
    if not evidence_records:
        errors.append("missing acceptance evidence check-in record")
    else:
        evidence_text = "\n".join(payload_text(payload) for payload in evidence_records)
        if "single_llm_truth_acceptance_count" not in evidence_text or not has_pattern(
            r"single_llm_truth_acceptance_count[^0-9]{0,20}0", evidence_text
        ):
            errors.append("acceptance evidence does not set single_llm_truth_acceptance_count to 0")
        if (
            "store_verify" not in evidence_text
            and "store_verification" not in evidence_text
            and "okra-store.sh verify" not in evidence_text
        ):
            errors.append("acceptance evidence lacks store_verify")
        if "content_hash" not in evidence_text and "content_sha256" not in evidence_text:
            errors.append("acceptance evidence lacks content_hash/content_sha256")
        if "changed_path" not in evidence_text and "deterministic_checker" not in evidence_text:
            errors.append("acceptance evidence lacks changed-path or deterministic-checker evidence")
        if "worker_progress" not in evidence_text and "progress.jsonl" not in evidence_text:
            errors.append("acceptance evidence lacks worker progress file evidence")

    required_artifact_patterns = {
        "ungoverned direct read anti-metric": r"ungoverned_direct_read_count[^0-9]{0,40}0",
        "ungoverned direct write anti-metric": r"ungoverned_direct_write_count[^0-9]{0,40}0",
        "single LLM truth anti-metric": r"single_llm_truth_acceptance_count[^0-9]{0,40}0",
        "DKR learning checkpoint gate": (
            r"(learning checkpoint|dkr checkpoint)[\s\S]{0,800}"
            r"(candidate|promot|orchestrator acceptance|orchestrator accepts?)"
            r"|(?:candidate\s+(?:CKRs?|PKRs?)|CKRs?\s*/\s*PKRs?\s+candidates?|CKRs?\s+and\s+PKRs?\s+candidates?)"
            r"[\s\S]{0,500}(not promoted until|remain candidates until|learning checkpoint|dkr checkpoint)"
            r"|promoted[_ -]after[_ -]dkr[_ -]checkpoint|checkpoint[_ -]accepted"
        ),
        "worker progress files": r"(\.okra/workers|progress\.jsonl|worker progress file|file-based worker reports?)",
        "append-only source rule": (
            r"append-only[\s\S]{0,300}(source of truth|generated view|generated status|status[^.\n]{0,80}generated)"
            r"|status\.md[\s\S]{0,180}(generated|never the source of truth)"
        ),
        "independent evidence rule": r"(independent evidence|deterministic evidence|deterministic verifier)",
    }
    for name, pattern in required_artifact_patterns.items():
        if not has_pattern(pattern, artifact_text):
            errors.append(f"artifact missing {name}")


def analyze_store(store: Path) -> list[str]:
    errors: list[str] = []
    workspace = workspace_for_store(store)
    check_frame_tree(store, errors)
    records = {name: load_log(store, name, errors) for name in LOG_NAMES}
    records["worker_progress"] = load_worker_progress(store, errors)
    check_content_store(store, records, errors)
    check_status(store, errors)
    check_source_reads(workspace, store, records.get("checkins", []), errors)
    check_final_write(workspace, store, records.get("checkins", []), errors)
    check_metric_and_checkin_records(records, errors)
    check_worker_progress(records, errors)
    check_move_results(store, errors)

    artifact = workspace / TARGET_ARTIFACT
    artifact_text = artifact.read_text(encoding="utf-8", errors="replace") if artifact.exists() else ""
    check_acceptance_evidence(records, artifact_text, errors)
    return errors


def candidate_stores(root: Path) -> list[Path]:
    if root.parent.name == "runs":
        return [root]
    target = root / "runs" / TARGET_RUN_ID
    return [target] if target.is_dir() else []


def analyze(store: Path) -> list[str]:
    if not store.exists():
        return [f"missing store: {store}"]
    if not store.is_dir():
        return [f"store path is not a directory: {store}"]

    candidates = candidate_stores(store)
    if not candidates:
        return [f"missing run-scoped OKRA store under {store / 'runs' / TARGET_RUN_ID}"]

    errors_by_store = [(candidate, analyze_store(candidate)) for candidate in candidates]
    if any(not errors for _, errors in errors_by_store):
        return []

    candidate, errors = errors_by_store[0]
    prefix = display_path(candidate, candidate)
    return [f"{prefix}: {error}" for error in errors]


def workspace_dirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(child for child in path.iterdir() if child.is_dir())


def calibrate(root: Path) -> int:
    pass_dirs = workspace_dirs(root / "pass")
    fail_dirs = workspace_dirs(root / "fail")
    failures: list[str] = []
    if not pass_dirs:
        failures.append(f"{root / 'pass'}: no passing golden workspaces")
    if not fail_dirs:
        failures.append(f"{root / 'fail'}: no failing golden workspaces")

    for workspace in pass_dirs:
        errors = analyze(workspace / ".okra")
        if errors:
            failures.append(f"{workspace}: expected pass, got: {', '.join(errors[:5])}")

    for workspace in fail_dirs:
        errors = analyze(workspace / ".okra")
        if not errors:
            failures.append(f"{workspace}: expected at least one store-governance violation, got pass")
            continue
        expected = EXPECTED_FAIL_PATTERNS.get(workspace.name)
        if expected and not has_pattern(expected, "\n".join(errors)):
            failures.append(
                f"{workspace}: expected violation matching {expected!r}, got: {', '.join(errors[:5])}"
            )

    if failures:
        print("okra store-governance calibration failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"okra store-governance calibration ok: {len(pass_dirs)} pass, {len(fail_dirs)} fail")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, help="Workspace-relative .okra store directory")
    parser.add_argument("--calibrate", type=Path, help="run golden pass/fail calibration under this directory")
    args = parser.parse_args()

    if args.calibrate:
        return calibrate(args.calibrate)
    if not args.path:
        parser.error("path is required unless --calibrate is used")

    errors = analyze(args.path)
    if errors:
        print("store governance violations:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"ok: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
