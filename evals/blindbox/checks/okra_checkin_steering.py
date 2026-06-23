#!/usr/bin/env python3
"""Check whether OKRA steering check-ins are operational, budgeted, and evidence-backed."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def payload_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).lower()


def payload_type(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("record_type", "record_kind", "kind", "event", "type"):
        value = payload.get(key)
        if value is not None:
            return str(value).lower()
    return ""


def is_zero(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, str):
        return value.strip().lower() in {"0", "0.0", "zero"}
    return False


def is_metric_scalar(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized == "zero" or re.fullmatch(r"[+-]?\d+(?:\.\d+)?", normalized) is not None
    return False


def numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "zero":
            return 0.0
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", normalized):
            return float(normalized)
    return None


def metric_values(payload: Any, name_patterns: tuple[str, ...]) -> list[Any]:
    values: list[Any] = []
    if isinstance(payload, dict):
        metric_name = next(
            (
                str(payload.get(key)).lower()
                for key in ("metric", "name", "metric_name", "anti_goal", "anti_goal_metric")
                if payload.get(key) is not None
            ),
            "",
        )
        if metric_name and any(pattern in metric_name for pattern in name_patterns):
            value = payload.get("value")
            if is_metric_scalar(value):
                values.append(value)
        for key, value in payload.items():
            key_lower = key.lower()
            if any(pattern in key_lower for pattern in name_patterns):
                if isinstance(value, dict) and "value" in value and is_metric_scalar(value["value"]):
                    values.append(value["value"])
                elif is_metric_scalar(value):
                    values.append(value)
            values.extend(metric_values(value, name_patterns))
    elif isinstance(payload, list):
        for child in payload:
            values.extend(metric_values(child, name_patterns))
    return values


def numeric_at(payload: Any, names: set[str]) -> float | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in names and isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            found = numeric_at(value, names)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for child in payload:
            found = numeric_at(child, names)
            if found is not None:
                return found
    return None


def record_payload(line: str) -> dict[str, Any] | None:
    if not line.strip():
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict):
        return None
    payload = record.get("payload", record)
    return payload if isinstance(payload, dict) else None


def load_payloads(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payloads: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        payload = record_payload(line)
        if payload is not None:
            payloads.append(payload)
    return payloads


def run_stores(root: Path) -> list[Path]:
    runs = root / "runs"
    if runs.is_dir():
        stores = sorted(child for child in runs.iterdir() if child.is_dir())
        if stores:
            return stores
    return []


def has_pattern(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None


def check_one_run(store: Path) -> list[str]:
    errors: list[str] = []
    ledger = load_payloads(store / "ledger.jsonl")
    checkins = load_payloads(store / "checkins.jsonl")
    worker_payloads: list[dict[str, Any]] = []
    workers = store / "workers"
    if workers.exists():
        for path in sorted(workers.glob("*/progress.jsonl")):
            worker_payloads.extend(load_payloads(path))

    all_text = "\n".join(payload_text(payload) for payload in ledger + checkins + worker_payloads)
    ledger_text = "\n".join(payload_text(payload) for payload in ledger)
    checkin_text = "\n".join(payload_text(payload) for payload in checkins)
    worker_text = "\n".join(payload_text(payload) for payload in worker_payloads)

    health_values: list[Any] = []
    for payload in ledger:
        health_values.extend(metric_values(payload, ("healthy_checkin_rate",)))
    if not has_pattern(r"\b(healthy_checkin_rate|checkin_health|steering_checkin_quality)\b", ledger_text):
        errors.append("ledger lacks objective metric for healthy steering/check-ins")
    elif health_values and not any((value := numeric_value(raw_value)) is not None and value >= 0.9 for raw_value in health_values):
        errors.append("healthy_checkin_rate is below 0.90")

    dkr_budget_values: list[Any] = []
    for payload in ledger:
        dkr_budget_values.extend(
            metric_values(
                payload,
                (
                    "dkr_budget_overrun_count",
                    "dkr_budget_overrun",
                    "unbounded_dkr_spend",
                    "runaway_dkr_spend",
                ),
            )
        )

    legacy_budget_reads = [
        payload
        for payload in ledger
        if "budget" in payload_text(payload)
        and has_pattern(r"(overrun|unbounded|runaway|spend)", payload_text(payload))
    ]
    if not dkr_budget_values and not legacy_budget_reads:
        errors.append("ledger lacks DKR budget anti-goal read")
    elif dkr_budget_values and not all(is_zero(value) for value in dkr_budget_values):
        errors.append("DKR budget anti-goal is not zero")
    elif not dkr_budget_values and not any(is_zero(payload.get("value")) for payload in legacy_budget_reads):
        errors.append("DKR budget anti-goal is not zero")

    if not checkins:
        errors.append("missing steering check-in records")
    if len(checkins) < 2:
        errors.append("need at least two check-ins to prove steering over time")

    if not worker_payloads:
        errors.append("missing worker progress reports")

    dkr_payloads = [
        payload
        for payload in worker_payloads
        if has_pattern(r"\b(DKR|discovery)\b", payload_text(payload))
    ]
    pkr_payloads = [
        payload
        for payload in worker_payloads
        if has_pattern(r"\b(PKR|progression)\b", payload_text(payload))
    ]

    if not dkr_payloads:
        errors.append("missing DKR worker progress report")
    if not pkr_payloads:
        errors.append("missing PKR worker progress report")

    dkr_text = "\n".join(payload_text(payload) for payload in dkr_payloads)
    if dkr_payloads and not has_pattern(r"\bbudget\b", dkr_text):
        errors.append("DKR progress lacks explicit budget")
    if dkr_payloads and not has_pattern(r"\b(spent|remaining|used|turn_budget|max_turns|time_budget)\b", dkr_text):
        errors.append("DKR progress lacks spent/remaining budget state")
    if dkr_payloads and not has_pattern(r"\b(learning|evidence|answered|unanswered)\b", dkr_text):
        errors.append("DKR progress lacks learning/evidence content")
    if dkr_payloads and not has_pattern(r"\b(probability|confidence|posterior|prior)\b", dkr_text):
        errors.append("DKR progress lacks probability/confidence update")
    if dkr_payloads and not has_pattern(
        r"\b(next_unknowns?|next unknowns?|remaining_unknowns?|remaining unknowns?)\b",
        dkr_text,
    ):
        errors.append("DKR progress lacks next unknowns")
    if dkr_payloads and not has_pattern(r"\b(next_report_at|10[- ]?minute|ten[- ]minute|\+10m)\b", dkr_text):
        errors.append("DKR progress lacks timed heartbeat / next_report_at")

    for payload in dkr_payloads:
        turn_budget = numeric_at(payload, {"turn_budget", "budget_turns", "max_turns", "turns_total"})
        turn_spent = numeric_at(payload, {"spent_turns", "turns_spent", "used_turns"})
        minute_budget = numeric_at(payload, {"time_budget_minutes", "budget_minutes", "minutes_total"})
        minute_spent = numeric_at(payload, {"spent_minutes", "time_spent_minutes", "minutes_spent"})
        if (
            (turn_budget is not None and turn_spent is not None and turn_spent > turn_budget)
            or (minute_budget is not None and minute_spent is not None and minute_spent > minute_budget)
        ):
            errors.append("DKR progress exceeds budget")
            break

    if not has_pattern(r"\b(worker_progress_refs|progress\.jsonl|workers/)\b", checkin_text):
        errors.append("check-ins do not consume worker progress refs")
    if not has_pattern(r"\b(pkr_signals?|progress_signals?|off_track|quality_drift|late_discovery|stale_metric)\b", checkin_text):
        errors.append("check-ins lack PKR progress signals")
    if not has_pattern(
        r"\b(inbound_steering|inbound_steering_input|steering_input|human_steering|worker_signal|metric_signal)\b",
        checkin_text,
    ):
        errors.append("check-ins lack inbound steering slot")
    if not has_pattern(r"\b(outbound_steering|steering_decision|decision|dispatch|pause|promote|spawn)\b", checkin_text):
        errors.append("check-ins lack outbound steering decision")
    if not has_pattern(r"\b(next_check_at|next_report_at|heartbeat|10[- ]?minute|ten[- ]minute)\b", checkin_text):
        errors.append("check-ins lack next check / heartbeat")
    if not has_pattern(r"\b(accepted|promot|hold|cannot|pause)\b", checkin_text) or not has_pattern(
        r"\b(DKR|learning_checkpoint|checkpoint)\b", checkin_text
    ):
        errors.append("check-ins do not gate CKR/PKR promotion on DKR learning")

    if not has_pattern(r"\b(cannot|budget_exhausted|budget exhausted|stop rule|stop_rule|pause)\b", all_text):
        errors.append("run lacks DKR budget exhaustion stop/escalation rule")

    return errors


def analyze(root: Path) -> list[str]:
    if not root.exists():
        return [f"missing store: {root}"]
    stores = run_stores(root)
    if not stores:
        return ["missing run-scoped OKRA store under .okra/runs/<run-id>"]

    errors_by_run = [(store, check_one_run(store)) for store in stores]
    if any(not errors for _, errors in errors_by_run):
        return []

    store, errors = errors_by_run[0]
    return [f"{store.relative_to(root.parent)}: {error}" for error in errors]


def workspace_dirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(child for child in path.iterdir() if child.is_dir())


def calibrate(root: Path) -> int:
    failures: list[str] = []
    pass_dirs = workspace_dirs(root / "pass")
    fail_dirs = workspace_dirs(root / "fail")
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
            failures.append(f"{workspace}: expected at least one check-in steering violation, got pass")

    if failures:
        print("okra check-in steering calibration failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"okra check-in steering calibration ok: {len(pass_dirs)} pass, {len(fail_dirs)} fail")
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
        print("OKRA check-in steering violations:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"ok: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
