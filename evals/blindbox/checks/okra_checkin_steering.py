#!/usr/bin/env python3
"""Check whether OKRA steering check-ins are operational, budgeted, and evidence-backed."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


TARGET_RUN_ID = "checkin-steering"
EXPECTED_FAIL_PATTERNS = {
    "budget-overrun": r"(DKR budget anti-goal is not zero|DKR progress exceeds budget)",
    "flat-store": r"missing run-scoped OKRA store",
    "low-health-rate": r"healthy_checkin_rate is below 0\.90",
    "no-dkr-budget": r"ledger lacks DKR budget anti-goal read|DKR progress lacks explicit budget",
    "no-pkr-signals": r"check-ins lack PKR progress signals",
    "no-steering-value": r"(ledger lacks steering value metric read|check-ins lack steering value evidence)",
    "passive-steering": r"check-ins lack nontrivial steering intervention",
}

DKR_RISK_PATTERN = (
    r"\b(risk(?: if skipped)?|risk_if_skipped|"
    r"risk[_ -]?or[_ -]?anti[_ -]?goal[_ -]?uncertainty(?:[_ -]?reduced)?|"
    r"anti[_ -]?goal[_ -]?uncertainty(?:[_ -]?reduced)?|anti[- ]goal risk|guardrail[_ -]?uncertainty|"
    r"trap|traps|safe|safety|unsafe|harm|wall|veto|admissibility|"
    r"avoid wasting|not wasting|waste)\b"
)

VALUE_EFFECT_PATTERN = (
    r"\b((?:expected|direct)?[_ -]?(?:metric|risk|uncertainty|waste)?[_ -]?effect|"
    r"risk[_ -]?reduction|waste[_ -]?reduction[_ -]?effect|expected[_ -]?direct[_ -]?effect|"
    r"objective[_ -]?effect|anti[_ -]?goal[_ -]?effect|waste[_ -]?avoided|"
    r"uncertainty[_ -]?reduction|saved[_ -]?turns|avoided[_ -]?overrun)\b"
)
SIGNAL_SOURCE_PATTERN = (
    r"\b(worker[_ -]?signal|metric[_ -]?signal|risk[_ -]?signal|progress[_ -]?signal|"
    r"budget[_ -]?signal|inbound[_ -]?signal|stale[_ -]?metric|late[_ -]?discovery|"
    r"quality[_ -]?drift|off[_ -]?track|worker[_ -]?progress[_ -]?refs)\b"
)
DECISION_DELTA_PATTERN = (
    r"\b(decision[_ -]?delta|state[_ -]?delta|allocation[_ -]?delta|board[_ -]?delta|"
    r"changed[_ -]?state|promote|promoted|hold|held|pause|paused|spawn|spawned|"
    r"veto|vetoed|rerank|reranked|fund|funded|stop|stopped|closed[_ -]?dkr[_ -]?budget)\b"
)
AFFECTED_SCOPE_PATTERN = r"\baffected[_ -]?(?:scopes?|dkr|ckr|pkr|allocations?)\b"
EVIDENCE_REF_PATTERN = r"\bevidence[_ -]?refs?\b"
NONTRIVIAL_DECISION_PATTERN = (
    r"\b(promote|promoted|promote_candidates|hold|held|pause|paused|spawn|spawned|veto|vetoed|"
    r"rerank|reranked|fund|funded|stop|stopped|closed[_ -]?dkr[_ -]?budget(?:[_ -]?lane)?|"
    r"reallocate|reallocated|reallocation|allocation[_ -]?delta|allocation[_ -]?change|"
    r"state[_ -]?delta|state[_ -]?change|board[_ -]?delta|board[_ -]?change|changed[_ -]?state)\b"
)
NEGATIVE_VALUE_PATTERN = (
    r"\b(no[_ -]?direct(?:[_ -]?steering)?[_ -]?change|not[_ -]?demonstrated|"
    r"none[_ -]?continue|no[_ -]?(?:allocation|state|board)[_ -]?change|"
    r"without[_ -]?(?:allocation|state|board)[_ -]?change)\b"
)
NEGATED_DECISION_PATTERN = (
    r"\b(?:not|no|do[_ -]?not|dont|don't)[\s_:-]{0,30}"
    r"(?:promote|hold|pause|spawn|veto|rerank|fund|stop|allocat|chang(?:e|ing))\b|"
    r"\b(?:no|without)[_ -]?(?:allocation|state|board|allocation[_ -]or[_ -]state)[_ -]?change\b|"
    r"\bnone(?:[_ -]?continue)?(?:[_ -]?without[_ -]?(?:allocation|state|board)[_ -]?change)?\b"
)
PASSIVE_DELTA_PATTERN = r"\b(continue|monitor|observe|unchanged|same|none|no[_ -]?change)\b"
SUBSTANTIVE_DELTA_PATTERN = (
    r"\b(from\b[\s\S]{0,80}\bto\b|[-=]>|increase|increased|decrease|decreased|"
    r"opened|closed|active|inactive|accepted|rejected)\b"
)
SIGNAL_KEYS = {
    "inbound_signal",
    "worker_signal",
    "metric_signal",
    "risk_signal",
    "progress_signal",
    "budget_signal",
}
AFFECTED_KEYS = {
    "affected_scope",
    "affected_scopes",
    "affected_dkr",
    "affected_ckr",
    "affected_pkr",
    "affected_allocation",
    "affected_allocations",
}
EVIDENCE_KEYS = {"evidence_ref", "evidence_refs", "evidence_reference", "evidence_references"}
DELTA_KEYS = {"decision_delta", "state_delta", "allocation_delta", "board_delta", "changed_state"}
EFFECT_KEYS = {
    "expected_metric_effect",
    "expected_direct_effect",
    "direct_metric_effect",
    "direct_risk_effect",
    "direct_uncertainty_effect",
    "direct_waste_effect",
    "metric_effect",
    "risk_effect",
    "uncertainty_effect",
    "waste_effect",
    "waste_reduction_effect",
    "objective_effect",
    "anti_goal_effect",
    "risk_reduction",
    "uncertainty_reduction",
    "waste_avoided",
    "saved_turns",
    "avoided_overrun",
}
DECISION_KEYS = {
    "steering_decision",
    "outbound_steering",
    "decision",
    *DELTA_KEYS,
}


def canonical_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


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
        for identity_key in ("metric", "metric_id", "metric_name", "anti_goal", "anti_goal_metric", "name"):
            metric_name = str(payload.get(identity_key, "")).lower()
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


def require_zero_metric(
    ledger: list[dict[str, Any]],
    name_patterns: tuple[str, ...],
    label: str,
    errors: list[str],
) -> None:
    values: list[Any] = []
    for payload in ledger:
        values.extend(metric_values(payload, name_patterns))
    if not values:
        errors.append(f"ledger lacks anti-goal read: {label}")
    elif not all(is_zero(value) for value in values):
        errors.append(f"anti-goal metric is not zero: {label}")


def metric_values_from_records(records: list[dict[str, Any]], name_patterns: tuple[str, ...]) -> list[Any]:
    values: list[Any] = []
    for payload in records:
        values.extend(metric_values(payload, name_patterns))
    return values


def require_positive_metric(
    ledger: list[dict[str, Any]],
    name_patterns: tuple[str, ...],
    *,
    minimum: float,
    label: str,
    errors: list[str],
) -> None:
    values = metric_values_from_records(ledger, name_patterns)
    numeric_values = [numeric_value(value) for value in values]
    if not values:
        errors.append(f"ledger lacks steering value metric read: {label}")
    elif not any(value is not None and value >= minimum for value in numeric_values):
        errors.append(f"steering value metric is below {minimum:g}: {label}")


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


def record_payload(line: str, *, label: str, errors: list[str], expected_seq: int, prev: str) -> tuple[dict[str, Any] | None, str]:
    if not line.strip():
        return None, prev
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        errors.append(f"{label}: invalid json")
        return None, prev
    if not isinstance(record, dict):
        errors.append(f"{label}: record is not an object")
        return None, prev

    if record.get("seq") != expected_seq:
        errors.append(f"{label}: expected seq {expected_seq}, got {record.get('seq')}")
    if record.get("prev_hash") != prev:
        errors.append(f"{label}: prev_hash mismatch")

    payload = record.get("payload")
    if not isinstance(payload, dict):
        errors.append(f"{label}: missing object payload")
        return None, prev
    if record.get("payload_sha256") != canonical_hash(payload):
        errors.append(f"{label}: payload_sha256 mismatch")

    without_hash = {key: value for key, value in record.items() if key != "record_hash"}
    record_hash = canonical_hash(without_hash)
    if record.get("record_hash") != record_hash:
        errors.append(f"{label}: record_hash mismatch")
    return payload, str(record.get("record_hash", ""))


def load_payloads(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payloads: list[dict[str, Any]] = []
    prev = "GENESIS"
    expected_seq = 1
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        payload, prev = record_payload(
            line,
            label=f"{path}:{lineno}",
            errors=errors,
            expected_seq=expected_seq,
            prev=prev,
        )
        expected_seq += 1
        if payload is not None:
            payloads.append(payload)
    return payloads


def worker_progress_record_refs(path: Path, store: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        rel_store_path = path.relative_to(store).as_posix()
    except ValueError:
        rel_store_path = path.name
    bases = {
        rel_store_path,
        f".okra/runs/{TARGET_RUN_ID}/{rel_store_path}",
    }
    refs = set(bases)
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        seq = record.get("seq", lineno) if isinstance(record, dict) else lineno
        for base in bases:
            refs.add(f"{base}#seq={seq}")
    return refs


def run_stores(root: Path) -> list[Path]:
    target = root / "runs" / TARGET_RUN_ID
    return [target] if target.is_dir() else []


def has_pattern(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None


def normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def keyed_values(payload: Any, keys: set[str]) -> list[tuple[str, Any]]:
    values: list[tuple[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_name = normalized_key(key)
            if key_name in keys:
                values.append((key_name, value))
            values.extend(keyed_values(value, keys))
    elif isinstance(payload, list):
        for child in payload:
            values.extend(keyed_values(child, keys))
    return values


def leaf_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        values: list[Any] = []
        for child in value.values():
            values.extend(leaf_values(child))
        return values
    if isinstance(value, list):
        values: list[Any] = []
        for child in value:
            values.extend(leaf_values(child))
        return values
    return [value]


def value_has_content(value: Any, *, reject_negative: bool = False) -> bool:
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict)) and not value:
        return False
    text = payload_text(value)
    if text in {"", "null", "[]", "{}"}:
        return False
    if reject_negative and has_pattern(NEGATIVE_VALUE_PATTERN, text):
        return False
    return True


def has_resolved_evidence_ref(payload: dict[str, Any], valid_refs: set[str]) -> bool:
    if not valid_refs:
        return False
    ref_values = keyed_values(payload, EVIDENCE_KEYS)
    for _, value in ref_values:
        for leaf in leaf_values(value):
            if not isinstance(leaf, (str, int, float)):
                continue
            ref = str(leaf).strip()
            if ref in valid_refs:
                return True
    return False


def has_complete_steering_value_evidence(payload: dict[str, Any]) -> bool:
    effect_values = [value for _, value in keyed_values(payload, EFFECT_KEYS)]
    signal_values = [value for _, value in keyed_values(payload, SIGNAL_KEYS)]
    affected_values = [value for _, value in keyed_values(payload, AFFECTED_KEYS)]
    evidence_values = [value for _, value in keyed_values(payload, EVIDENCE_KEYS)]
    delta_values = [value for _, value in keyed_values(payload, DELTA_KEYS | DECISION_KEYS)]

    return (
        any(value_has_content(value, reject_negative=True) for value in effect_values)
        and any(value_has_content(value) for value in signal_values)
        and any(value_has_content(value) for value in affected_values)
        and any(value_has_content(value) for value in evidence_values)
        and any(value_has_content(value) for value in delta_values)
    )


def has_nontrivial_steering_intervention(payload: dict[str, Any]) -> bool:
    for key, value in keyed_values(payload, DECISION_KEYS):
        text = payload_text(value)
        if not value_has_content(value) or has_pattern(NEGATED_DECISION_PATTERN, text):
            continue
        if key in DELTA_KEYS:
            if (
                not has_pattern(PASSIVE_DELTA_PATTERN, text)
                and (
                    has_pattern(NONTRIVIAL_DECISION_PATTERN, text)
                    or has_pattern(SUBSTANTIVE_DELTA_PATTERN, text)
                )
            ):
                return True
            continue
        if has_pattern(NONTRIVIAL_DECISION_PATTERN, text):
            return True
    return False


def steering_value_patterns_stay_reachable() -> bool:
    probe_text = payload_text(
        {
            "direct_metric_effect": "increase healthy_checkin_rate",
            "affected_pkr": "pkr-checkin-delivery",
            "evidence_ref": "workers/pkr/progress.jsonl#seq=1",
        }
    )
    return (
        has_pattern(VALUE_EFFECT_PATTERN, probe_text)
        and has_pattern(AFFECTED_SCOPE_PATTERN, probe_text)
        and has_pattern(EVIDENCE_REF_PATTERN, probe_text)
    )


def load_json_object(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing {label}: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid json: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: {label} must be an object")
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


def check_one_run(store: Path) -> list[str]:
    errors: list[str] = []
    check_frame_tree(store, errors)
    ledger = load_payloads(store / "ledger.jsonl", errors)
    checkins = load_payloads(store / "checkins.jsonl", errors)
    flags = load_payloads(store / "flags.jsonl", errors)
    worker_payloads: list[dict[str, Any]] = []
    valid_worker_refs: set[str] = set()
    workers = store / "workers"
    if workers.exists():
        for path in sorted(workers.glob("*/progress.jsonl")):
            worker_payloads.extend(load_payloads(path, errors))
            valid_worker_refs.update(worker_progress_record_refs(path, store))

    all_text = "\n".join(payload_text(payload) for payload in ledger + checkins + flags + worker_payloads)
    ledger_text = "\n".join(payload_text(payload) for payload in ledger)
    checkin_text = "\n".join(payload_text(payload) for payload in checkins)
    flags_text = "\n".join(payload_text(payload) for payload in flags)
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

    require_zero_metric(
        ledger,
        ("unsteered_worker_edge_count", "unsteered_worker_edge"),
        "unsteered_worker_edge_count",
        errors,
    )
    require_zero_metric(
        ledger,
        ("no_progress_loop_continuation_count", "no_progress_loop_continuation"),
        "no_progress_loop_continuation_count",
        errors,
    )

    if not flags:
        errors.append("missing flag lifecycle records")
    else:
        for pattern, label in (
            (r"\bcannot\b", "cannot"),
            (r"\bbreaking\b", "breaking"),
            (r"\bpointless\b", "pointless"),
            (r"\bauthority[_ -]?drift\b", "authority drift"),
        ):
            if not has_pattern(pattern, flags_text):
                errors.append(f"flag lifecycle lacks {label} flag class")
        for state in ("open", "acknowledged", "resolved", "waived"):
            if not has_pattern(rf"\b{state}\b", flags_text):
                errors.append(f"flag lifecycle lacks {state} state")
        if not has_pattern(r"\b(pause|stop|blocked|resume)\b", flags_text):
            errors.append("flag lifecycle lacks pause/stop/resume behavior")

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
    if dkr_payloads and not has_pattern(
        r"\b(decision(?: target)?|decision[_ -]?target|decision to (?:unlock|unblock|improve)|"
        r"steering decision|promotion decision|next steering decision|"
        r"whether to (?:promote|fund|spawn|continue|pause|admit|veto|re-aim|reaim)|"
        r"decide whether to (?:promote|fund|spawn|continue|pause|admit|veto|re-aim|reaim))\b",
        dkr_text,
    ):
        errors.append("DKR progress lacks decision target/unlock")
    if dkr_payloads and not has_pattern(DKR_RISK_PATTERN, dkr_text):
        errors.append("DKR progress lacks risk or anti-goal uncertainty")
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

    require_positive_metric(
        ledger,
        (
            "steering_value_score",
            "steering_value_rate",
            "decision_value_score",
            "checkin_value_score",
            "valuable_steering_decision_count",
            "steering_intervention_count",
            "risk_reduction_event_count",
            "allocation_change_count",
        ),
        minimum=0.75,
        label="steering_value_score",
        errors=errors,
    )
    require_zero_metric(
        ledger,
        (
            "no_value_checkin_count",
            "unvaluable_checkin_count",
            "steering_theater_count",
        ),
        "no_value_checkin_count",
        errors,
    )

    value_steering_checkins = [
        payload
        for payload in checkins
        if has_complete_steering_value_evidence(payload)
        and has_nontrivial_steering_intervention(payload)
        and has_resolved_evidence_ref(payload, valid_worker_refs)
    ]
    if not value_steering_checkins:
        errors.append("check-ins lack steering value evidence")

    if not any(has_nontrivial_steering_intervention(payload) for payload in checkins):
        errors.append("check-ins lack nontrivial steering intervention")

    if not has_pattern(r"\b(cannot|budget_exhausted|budget exhausted|stop rule|stop_rule|pause)\b", all_text):
        errors.append("run lacks DKR budget exhaustion stop/escalation rule")

    return errors


def analyze(root: Path) -> list[str]:
    if not root.exists():
        return [f"missing store: {root}"]
    stores = run_stores(root)
    if not stores:
        return [f"missing run-scoped OKRA store under .okra/runs/{TARGET_RUN_ID}"]

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
            continue
        expected = EXPECTED_FAIL_PATTERNS.get(workspace.name)
        if expected and not has_pattern(expected, "\n".join(errors)):
            failures.append(
                f"{workspace}: expected violation matching {expected!r}, got: {', '.join(errors[:5])}"
            )

    metric_probe = {"metric_id": "opaque-record-id", "metric_name": "unsteered_worker_edge_count", "value": 0}
    if metric_values(metric_probe, ("unsteered_worker_edge_count",)) != [0]:
        failures.append("probe: metric_name should be considered when metric_id is opaque")
    generic_id_probe = {"id": "unsteered_worker_edge_count", "value": 0}
    if metric_values(generic_id_probe, ("unsteered_worker_edge_count",)):
        failures.append("probe: generic id should not be treated as a metric identity")

    dkr_schema_probe = {
        "type": "dkr_worker_progress",
        "risk_or_anti_goal_uncertainty_reduced": "open question",
    }
    if not has_pattern(DKR_RISK_PATTERN, payload_text(dkr_schema_probe)):
        failures.append("probe: DKR risk_or_anti_goal_uncertainty_reduced should satisfy risk evidence")

    value_schema_probe = {
        "type": "steering_checkin",
        "worker_progress_refs": [{"worker_id": "dkr-1"}],
        "steering_value_evidence": {
            "affected_scope": ["ckr-a", "pkr-a"],
            "inbound_signal": "DKR confidence crossed threshold",
            "decision_delta": "promoted CKR and funded PKR",
            "expected_direct_effect": "reduced uncertainty and avoided wasted work",
            "evidence_ref": "workers/dkr-1/progress.jsonl#seq=1",
        },
    }
    if not has_complete_steering_value_evidence(value_schema_probe):
        failures.append("probe: steering_value_evidence should satisfy value evidence")
    if not steering_value_patterns_stay_reachable():
        failures.append("probe: direct effect and affected PKR variants should satisfy value regexes")

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
