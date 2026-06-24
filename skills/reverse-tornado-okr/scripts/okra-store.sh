#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  okra-store.sh init [store]
  okra-store.sh init-run <run-id> [store]
  okra-store.sh write-frame <frame.json> [store]
  okra-store.sh write-tree <tree.json> [store]
  okra-store.sh put <file> [store]
  okra-store.sh read-content <sha256> [store]
  okra-store.sh write-content <target> <source-file> [store]
  okra-store.sh worker-report <worker-id> <payload.json> [store]
  okra-store.sh move-result <idempotency-key> <payload.json> [store]
  okra-store.sh metric-read <payload.json> [store]
  okra-store.sh append <ledger|flags|checkins> <payload.json> [store]
  okra-store.sh verify [store]
  okra-store.sh status [store]
USAGE
}

sha_file() {
  sha256sum -- "$1" | awk '{print $1}'
}

reject_path_escape() {
  local label="$1"
  local path="$2"
  case "$path" in
    ""|/*|..|../*|*/..|*/../*)
      printf '%s must be a workspace-relative path without ..: %s\n' "$label" "$path" >&2
      exit 2
      ;;
  esac
}

reject_invalid_sha256() {
  local label="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[0-9a-f]{64}$ ]]; then
    printf '%s must be a 64-character lowercase hex sha256: %s\n' "$label" "$value" >&2
    exit 2
  fi
}

reject_invalid_run_id() {
  local value="$1"
  case "$value" in
    ""|*[!A-Za-z0-9._-]*)
      printf 'run id must use only letters, numbers, dot, underscore, or hyphen: %s\n' "$value" >&2
      exit 2
      ;;
  esac
}

content_dir_for_store() {
  local store="$1"
  case "$store" in
    */runs/*) printf '%s/content/sha256\n' "${store%%/runs/*}" ;;
    *) printf '%s/content/sha256\n' "$store" ;;
  esac
}

cmd_init() {
  local store="${1:-.okra}"
  mkdir -p "$store/frame" "$store/tree" "$store/content/sha256" "$store/moves" "$store/workers" "$store/runs"
  touch "$store/ledger.jsonl" "$store/flags.jsonl" "$store/checkins.jsonl"
  printf 'OKRA store initialized at %s\n' "$store"
}

cmd_init_run() {
  local run_id="$1"
  local root="${2:-.okra}"
  reject_invalid_run_id "$run_id"
  mkdir -p "$root/content/sha256" "$root/runs"
  local run_store="$root/runs/$run_id"
  mkdir -p "$run_store/frame" "$run_store/tree" "$run_store/moves" "$run_store/workers" "$run_store/drafts"
  touch "$run_store/ledger.jsonl" "$run_store/flags.jsonl" "$run_store/checkins.jsonl"
  printf '%s\n' "$run_store"
}

write_versioned_json() {
  local kind="$1"
  local source="$2"
  local store="$3"
  test -f "$source"
  mkdir -p "$store/$kind"
  python3 - "$kind" "$source" "$store" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

kind = sys.argv[1]
source = Path(sys.argv[2])
store = Path(sys.argv[3])
value = json.loads(source.read_text(encoding="utf-8"))
if not isinstance(value, dict):
    print(f"{kind} json must be an object", file=sys.stderr)
    raise SystemExit(2)

text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).lower()
errors = []
if kind == "frame":
    required = ("frame_version", "frame_hash", "objective", "anti_goals", "metric_contracts", "action_envelope")
    for key in required:
        if key not in value:
            errors.append(f"frame missing {key}")
    if "human_approval" not in text and "ratified" not in text:
        errors.append("frame lacks human approval or ratification evidence")
elif kind == "tree":
    required = ("tree_version", "frame_version", "orchestrator", "dkrs", "ckrs", "pkrs")
    for key in required:
        if key not in value:
            errors.append(f"tree missing {key}")
    if "objective checks" not in text:
        errors.append("tree orchestrator entry must include objective checks")
    if "subagent steering" not in text:
        errors.append("tree orchestrator entry must include subagent steering")
else:
    errors.append(f"unknown versioned json kind: {kind}")

if errors:
    for error in errors:
        print(error, file=sys.stderr)
    raise SystemExit(2)

dest = store / kind / f"{kind}.v1.json"
data = json.dumps(value, sort_keys=True, indent=2) + "\n"
if dest.exists():
    if dest.read_text(encoding="utf-8") != data:
        print(f"{dest}: refusing to overwrite existing {kind}.v1.json with different content", file=sys.stderr)
        raise SystemExit(1)
else:
    dest.write_text(data, encoding="utf-8")
(store / kind / "current").write_text(dest.name + "\n", encoding="utf-8")
print(hashlib.sha256(dest.read_bytes()).hexdigest())
PY
}

cmd_write_frame() {
  local source="$1"
  local store="${2:-.okra}"
  write_versioned_json "frame" "$source" "$store"
}

cmd_write_tree() {
  local source="$1"
  local store="${2:-.okra}"
  write_versioned_json "tree" "$source" "$store"
}

cmd_put() {
  local file="$1"
  local store="${2:-.okra}"
  test -f "$file"
  local content_dir
  content_dir="$(content_dir_for_store "$store")"
  mkdir -p "$content_dir"
  local hash
  hash="$(sha_file "$file")"
  local dest="$content_dir/$hash"
  if [ ! -e "$dest" ]; then
    local tmp
    tmp="$(mktemp "$content_dir/.tmp.$hash.XXXXXX")"
    cp -- "$file" "$tmp"
    mv -n -- "$tmp" "$dest"
    rm -f -- "$tmp"
  fi
  printf '%s\n' "$hash"
}

append_inline_payload() {
  local log="$1"
  local store="$2"
  local payload="$3"
  local tmp
  tmp="$(mktemp)"
  printf '%s\n' "$payload" > "$tmp"
  cmd_append "$log" "$tmp" "$store" >/dev/null
  rm -f "$tmp"
}

cmd_read_content() {
  local hash="$1"
  local store="${2:-.okra}"
  reject_invalid_sha256 "content hash" "$hash"
  local content_dir
  content_dir="$(content_dir_for_store "$store")"
  local path="$content_dir/$hash"
  test -f "$path"
  append_inline_payload "checkins" "$store" "{\"type\":\"content_read\",\"content_sha256\":\"$hash\"}"
  cat -- "$path"
}

cmd_write_content() {
  local target="$1"
  local source="$2"
  local store="${3:-.okra}"
  reject_path_escape "target" "$target"
  test -f "$source"
  mkdir -p -- "$(dirname -- "$target")"
  local hash
  hash="$(cmd_put "$source" "$store")"
  cp -- "$source" "$target"
  append_inline_payload "checkins" "$store" "{\"type\":\"content_write\",\"target\":\"$target\",\"content_sha256\":\"$hash\"}"
  printf '%s\n' "$hash"
}

log_path() {
  case "$1" in
    ledger|flags|checkins) printf '%s/%s.jsonl\n' "$2" "$1" ;;
    *) printf 'unknown log: %s\n' "$1" >&2; exit 2 ;;
  esac
}

cmd_append() {
  local log="$1"
  local payload="$2"
  local store="${3:-.okra}"
  local path
  path="$(log_path "$log" "$store")"
  append_record_path "$path" "$payload"
}

append_record_path() {
  local path="$1"
  local payload="$2"
  mkdir -p "$(dirname "$path")"
  touch "$path"
  local lock="$path.lock"
  (
    flock -x 9
    python3 - "$path" "$payload" <<'PY'
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

log_path = Path(sys.argv[1])
payload_path = Path(sys.argv[2])

payload = json.loads(payload_path.read_text(encoding="utf-8"))
payload_canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
payload_hash = hashlib.sha256(payload_canonical.encode("utf-8")).hexdigest()

last_hash = "GENESIS"
seq = 1
lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
if lines:
    last = json.loads(lines[-1])
    last_hash = last["record_hash"]
    seq = int(last["seq"]) + 1

record = {
    "seq": seq,
    "recorded_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "prev_hash": last_hash,
    "payload_sha256": payload_hash,
    "payload": payload,
}
record_canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
record["record_hash"] = hashlib.sha256(record_canonical.encode("utf-8")).hexdigest()
with log_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
print(record["record_hash"])
PY
  ) 9>"$lock"
}

cmd_worker_report() {
  local worker_id="$1"
  local payload="$2"
  local store="${3:-.okra}"
  case "$worker_id" in
    *[!A-Za-z0-9._-]*|"")
      printf 'invalid worker id: %s\n' "$worker_id" >&2
      exit 2
      ;;
  esac
  append_record_path "$store/workers/$worker_id/progress.jsonl" "$payload"
}

cmd_move_result() {
  local key="$1"
  local payload="$2"
  local store="${3:-.okra}"
  if [ -z "$key" ]; then
    printf 'idempotency key is required\n' >&2
    exit 2
  fi
  test -f "$payload"
  mkdir -p "$store/moves"
  python3 - "$store" "$key" "$payload" <<'PY'
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

store = Path(sys.argv[1])
key = sys.argv[2]
payload_path = Path(sys.argv[3])

payload = json.loads(payload_path.read_text(encoding="utf-8"))
payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
record = {
    "idempotency_key": key,
    "key_sha256": key_hash,
    "payload_sha256": payload_hash,
    "committed_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "payload": payload,
}
dest = store / "moves" / f"{key_hash}.json"
data = json.dumps(record, sort_keys=True, indent=2) + "\n"
try:
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
except FileExistsError:
    existing = json.loads(dest.read_text(encoding="utf-8"))
    if existing.get("payload_sha256") != payload_hash:
        print(f"idempotency conflict for key {key_hash}: existing payload differs", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(existing, sort_keys=True, indent=2))
else:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(data)
    print(json.dumps(record, sort_keys=True, indent=2))
PY
}

cmd_metric_read() {
  local payload="$1"
  local store="${2:-.okra}"
  test -f "$payload"
  python3 - "$payload" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
value = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(value, dict):
    print("metric-read payload must be an object", file=sys.stderr)
    raise SystemExit(2)

record_type = str(value.get("type") or value.get("record_type") or value.get("event") or "").lower()
allowed_types = {
    "metric_read",
    "direct_metric_read",
    "objective_metric_read",
    "objective_read",
    "anti_goal_metric_read",
    "anti_goal_read",
}
errors = []
if record_type not in allowed_types:
    errors.append("metric-read payload needs type=metric_read, objective_metric_read, or anti_goal_metric_read")
if "metric_id" not in value and "metric" not in value:
    errors.append("metric-read payload needs metric_id or metric")
if "value" not in value:
    errors.append("metric-read payload needs value")
for key in ("observed_at", "source", "freshness"):
    if key not in value:
        errors.append(f"metric-read payload needs {key}")
payload_text = json.dumps(value, sort_keys=True).lower()
if not ("objective" in payload_text or "anti_goal" in payload_text or "anti-goal" in payload_text or "ckr" in payload_text):
    errors.append("metric-read payload must identify objective, CKR, or anti-goal metric kind")
if errors:
    for error in errors:
        print(error, file=sys.stderr)
    raise SystemExit(2)
PY
  cmd_append "ledger" "$payload" "$store"
}

cmd_verify() {
  local store="${1:-.okra}"
  python3 - "$store" <<'PY'
import hashlib
import json
import os
import re
import sys
from pathlib import Path

store = Path(sys.argv[1])
errors = []

def content_dir_for(store):
    if store.parent.name == "runs":
        return store.parent.parent / "content" / "sha256"
    return store / "content" / "sha256"

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

def payload_text(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).lower()

def load_json_object(path, label):
    if not path.exists():
        errors.append(f"missing {label}: {path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid json: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path}: {label} must be an object")
        return None
    return value

def verify_frame_tree():
    require_frame_tree = (
        store.parent.name == "runs"
        or (store / "frame" / "frame.v1.json").exists()
        or (store / "tree" / "tree.v1.json").exists()
    )
    if not require_frame_tree:
        return

    frame = load_json_object(store / "frame" / "frame.v1.json", "ratified frame")
    tree = load_json_object(store / "tree" / "tree.v1.json", "OKR tree")

    if frame is not None:
        for key in ("frame_version", "frame_hash", "objective", "anti_goals", "metric_contracts", "action_envelope"):
            if key not in frame:
                errors.append(f"frame missing {key}")
        if "human_approval" not in payload_text(frame) and "ratified" not in payload_text(frame):
            errors.append("frame lacks human approval or ratification evidence")
        if not (store / "frame" / "current").exists():
            errors.append("frame lacks frame/current pointer")

    if tree is not None:
        tree_text = payload_text(tree)
        for key in ("tree_version", "frame_version", "orchestrator", "dkrs", "ckrs", "pkrs"):
            if key not in tree:
                errors.append(f"tree missing {key}")
        if "objective checks" not in tree_text:
            errors.append("tree lacks orchestrator ownership of objective checks")
        if "subagent steering" not in tree_text:
            errors.append("tree lacks orchestrator ownership of subagent steering")
        if not (store / "tree" / "current").exists():
            errors.append("tree lacks tree/current pointer")

def verify_log_path(path):
    if not path.exists():
        errors.append(f"missing log: {path}")
        return
    prev = "GENESIS"
    expected_seq = 1
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{lineno}: invalid json: {exc}")
            continue
        if record.get("seq") != expected_seq:
            errors.append(f"{path}:{lineno}: expected seq {expected_seq}, got {record.get('seq')}")
        if record.get("prev_hash") != prev:
            errors.append(f"{path}:{lineno}: prev_hash mismatch")
        payload = record.get("payload")
        payload_hash = canonical_hash(payload)
        if record.get("payload_sha256") != payload_hash:
            errors.append(f"{path}:{lineno}: payload_sha256 mismatch")
        without_hash = {key: value for key, value in record.items() if key != "record_hash"}
        record_hash = canonical_hash(without_hash)
        if record.get("record_hash") != record_hash:
            errors.append(f"{path}:{lineno}: record_hash mismatch")
        prev = record.get("record_hash", "")
        expected_seq += 1

for name in ("ledger", "flags", "checkins"):
    verify_log_path(store / f"{name}.jsonl")

verify_frame_tree()

workers = store / "workers"
if workers.exists():
    for path in sorted(workers.glob("*/progress.jsonl")):
        verify_log_path(path)

content_dir = content_dir_for(store)
if content_dir.exists():
    for path in content_dir.iterdir():
        if path.is_file():
            if path.name.startswith(".tmp."):
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != path.name:
                errors.append(f"content hash mismatch: {path}")

moves = store / "moves"
if moves.exists():
    for path in sorted(moves.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid json: {exc}")
            continue
        key = record.get("idempotency_key")
        payload = record.get("payload")
        if not isinstance(key, str) or not key:
            errors.append(f"{path}: missing idempotency_key")
            continue
        key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
        if path.stem != key_hash or record.get("key_sha256") != key_hash:
            errors.append(f"{path}: idempotency key hash mismatch")
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if record.get("payload_sha256") != payload_hash:
            errors.append(f"{path}: payload_sha256 mismatch")

def hash_refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"content_sha256", "source_content_sha256", "target_content_sha256"} and isinstance(child, str):
                yield child
            yield from hash_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from hash_refs(child)

log_paths = [store / f"{name}.jsonl" for name in ("ledger", "flags", "checkins")]
if workers.exists():
    log_paths.extend(sorted(workers.glob("*/progress.jsonl")))

for path in log_paths:
    if not path.exists():
        continue
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        for ref in hash_refs(record.get("payload")):
            if not (content_dir / ref).is_file():
                errors.append(f"{path}:{lineno}: missing referenced content hash: {ref}")

def log_status_summary(path):
    if not path.exists():
        return 0, "-"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return 0, "-"
    try:
        record = json.loads(lines[-1])
    except json.JSONDecodeError:
        return len(lines), "<invalid-json>"
    return len(lines), str(record.get("record_hash", "-"))

def status_row_present(text, name, count, last_hash):
    pattern = rf"\|\s*{re.escape(name)}\s*\|\s*{count}\s*\|\s*`{re.escape(last_hash)}`\s*\|"
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None

status = store / "status.md"
if status.exists():
    status_text = status.read_text(encoding="utf-8")
    for name in ("ledger", "flags", "checkins"):
        count, last_hash = log_status_summary(store / f"{name}.jsonl")
        if not status_row_present(status_text, name, count, last_hash):
            errors.append(f"generated status is stale for {name} log: {status}")
    worker_count = 0
    if workers.exists():
        for source in sorted(workers.glob("*/progress.jsonl")):
            worker_count += len([line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()])
    if not status_row_present(status_text, "worker progress", worker_count, "per-worker logs"):
        errors.append(f"generated status is stale for worker progress logs: {status}")

if errors:
    for error in errors:
        print(error, file=sys.stderr)
    raise SystemExit(1)
print(f"OKRA store verified: {store}")
PY
}

cmd_status() {
  local store="${1:-.okra}"
  mkdir -p "$store"
  python3 - "$store" <<'PY'
import json
import sys
from pathlib import Path

store = Path(sys.argv[1])

def read_last(name):
    path = store / f"{name}.jsonl"
    if not path.exists():
        return 0, "-"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return 0, "-"
    record = json.loads(lines[-1])
    return len(lines), record.get("record_hash", "-")

ledger_count, ledger_hash = read_last("ledger")
flag_count, flag_hash = read_last("flags")
checkin_count, checkin_hash = read_last("checkins")
worker_count = 0
workers = store / "workers"
if workers.exists():
    for path in workers.glob("*/progress.jsonl"):
        worker_count += len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])

status = f"""# OKRA Store Status

Generated from append-only source records.

| Log | Records | Last Hash |
| --- | ---: | --- |
| ledger | {ledger_count} | `{ledger_hash}` |
| flags | {flag_count} | `{flag_hash}` |
| checkins | {checkin_count} | `{checkin_hash}` |
| worker progress | {worker_count} | `per-worker logs` |

This file is a generated view. Do not edit it by hand.
"""
(store / "status.md").write_text(status, encoding="utf-8")
print(store / "status.md")
PY
}

main() {
  local cmd="${1:-}"
  if [ -z "$cmd" ]; then
    usage
    exit 2
  fi
  shift || true
  case "$cmd" in
    init) cmd_init "${1:-.okra}" ;;
    init-run)
      [ "$#" -ge 1 ] || { usage; exit 2; }
      cmd_init_run "$@"
      ;;
    write-frame)
      [ "$#" -ge 1 ] || { usage; exit 2; }
      cmd_write_frame "$@"
      ;;
    write-tree)
      [ "$#" -ge 1 ] || { usage; exit 2; }
      cmd_write_tree "$@"
      ;;
    put)
      [ "$#" -ge 1 ] || { usage; exit 2; }
      cmd_put "$@"
      ;;
    read-content)
      [ "$#" -ge 1 ] || { usage; exit 2; }
      cmd_read_content "$@"
      ;;
    write-content)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      cmd_write_content "$@"
      ;;
    worker-report)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      cmd_worker_report "$@"
      ;;
    move-result)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      cmd_move_result "$@"
      ;;
    metric-read)
      [ "$#" -ge 1 ] || { usage; exit 2; }
      cmd_metric_read "$@"
      ;;
    append)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      cmd_append "$@"
      ;;
    verify) cmd_verify "${1:-.okra}" ;;
    status) cmd_status "${1:-.okra}" ;;
    *) usage; exit 2 ;;
  esac
}

main "$@"
