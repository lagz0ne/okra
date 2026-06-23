#!/usr/bin/env python3
"""Hard-gate checks for OKRA concept violations.

This checker is stricter than the generic Reverse Tornado structural checker. It is intended for
eval cases that must prove the artifact follows OKRA's operating model instead of producing
OKR-looking vocabulary.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


@dataclass(frozen=True)
class Stats:
    dkr_count: int
    ckr_count: int
    pkr_count: int
    task_like_count: int
    has_uncertainty: bool
    has_dkr_budget: bool
    has_probability: bool
    has_direct_metric: bool
    has_human_frame: bool
    has_objective_target: bool
    has_anti_goal_metric: bool
    has_signal_handling: bool
    has_traceability: bool
    has_check_in: bool
    has_ckr_tornado: bool
    has_pkr_signals: bool
    has_orchestrator_loop: bool
    has_subagent_work_split: bool
    has_ckr_context: bool
    has_dkr_learning_checkpoint: bool
    has_candidate_promotion_gate: bool
    has_time_based_checkin: bool
    has_worker_progress_report: bool

    @property
    def has_valid_dkr(self) -> bool:
        return self.dkr_count > 0 and self.has_uncertainty and self.has_dkr_budget and self.has_probability

    @property
    def has_all_units(self) -> bool:
        return self.dkr_count > 0 and self.ckr_count > 0 and self.pkr_count > 0


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None


def count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL))


def count_task_like_lines(text: str) -> int:
    task_line = re.compile(
        r"^\s*(?:[-*]|\d+[.)]|\[[ xX]\])\s+.*"
        r"\b(PKR|task|implement|build|ship|launch|create|add|write|update|deploy|email|change)\b",
        flags=re.IGNORECASE,
    )
    return sum(1 for line in text.splitlines() if task_line.search(line))


def local_context(text: str, start: int, end: int, radius: int = 180) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def line_context(text: str, start: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end == -1:
        line_end = len(text)
    prev_start = text.rfind("\n", 0, max(0, line_start - 1)) + 1
    return text[prev_start:line_end]


def is_describing_forbidden_pattern(text: str, start: int, end: int) -> bool:
    context = (line_context(text, start) + "\n" + local_context(text, start, end, radius=320)).lower()
    return has(
        r"\b(fail when|hard violations?|candidate observable signals?|golden negative|negative cases|"
        r"anti-pattern|anti-patterns|must not accept|should fail|reject outputs|forbidden pattern|"
        r"do not accept|hard gates?|explicitly rejected|rejected by this loop|"
        r"candidate harms?|coverage review|selected guardrails?|reject when|reject artifacts?|reject any|"
        r"anti-goal screen|anti-goal screens|veto moves?|vetoed|veto any|"
        r"forbidden without|requires? [^.\\n]{0,80}approval|human-only decisions?|"
        r"opens? when|flag definitions?|flag lifecycle|authority[_ -]?drift|"
        r"common mistakes?|mistakes? this loop avoids|mistakes? to avoid|"
        r"required positive evidence|forbidden pattern|forbidden patterns)\b",
        context,
    )


def is_negated_context(text: str, start: int, end: int) -> bool:
    return has(
        r"\b(never|not|do not|does not|cannot|must not|not inferred|not proof|not success|"
        r"only direct|direct read|direct metric|pointless|flat after|flat metric|re-aim|reaim|wrong tip)\b",
        local_context(text, start, end, radius=140),
    )


def gather_stats(text: str) -> Stats:
    return Stats(
        dkr_count=count(r"\bDKRs?\b", text),
        ckr_count=count(r"\bCKRs?\b", text),
        pkr_count=count(r"\bPKRs?\b", text),
        task_like_count=count_task_like_lines(text),
        has_uncertainty=has(r"\b(unknown|uncertain|uncertainty|question|hypothesis|probe|discovery|learn|learning)\b", text),
        has_dkr_budget=has(r"\b(budget|turns?|hours?|days?|max[_ -]?age|stopping rule|stop rule|stop when|timebox)\b", text),
        has_probability=has(r"\b(probability|probabilities|confidence|likelihood|odds|expected value|P\s*\(|\d{1,3}\s*%)\b", text),
        has_direct_metric=has(
            r"\b(direct metric|direct read|metric read|source of truth|observed_at|recorded_at|ledger|"
            r"no-cascade|waiting_for_measurement|waiting for measurement|lag window)\b",
            text,
        ),
        has_human_frame=has(
            r"\b(human owns|human-owned|human-only|human ratified|human-ratified|ratification|"
            r"human approval|approver|frame owner)\b",
            text,
        ),
        has_objective_target=has(
            r"\bobjective\b[\s\S]{0,700}"
            r"(>=|<=|from\s+\d[\d,.%]*\s+to\s+\d[\d,.%]*|\d[\d,.%]*\s*(?:%|percent|score|rate|count|users?|teams?)?)",
            text,
        ),
        has_anti_goal_metric=has(
            r"\banti[- ]goal\b[\s\S]{0,800}"
            r"(metric|anti-metric|violation|count|rate|threshold|tripwire|drift)[\s\S]{0,400}"
            r"(>=|<=|==|zero|\b0\b|\d[\d,.%]*)",
            text,
        ),
        has_signal_handling=has(
            r"\b(too easy|too hard|impossible|stale|non[- ]moving|flat metric|disconnected|noisy|gamed|"
            r"signal|orchestrator|human review|human escalation|flag|re-aim|reaim)\b",
            text,
        ),
        has_traceability=has(
            r"\b(source DKR|DKR evidence|traceability|traceable|links? to|linked to|shapes|because|"
            r"therefore|probability-weighted|probability weighted)\b",
            text,
        )
        or has(
            r"\bDKR-\d+\b[\s\S]{0,700}"
            r"\b(linked to|source|preconditions?|requires?|feeds?|after|because|therefore|delivery path)\b"
            r"[\s\S]{0,300}\b(CKR-\d+|PKR-\d+)\b",
            text,
        )
        or has(
            r"\b(CKR-\d+|PKR-\d+|delivery path|preconditions?)\b[\s\S]{0,700}"
            r"\b(linked to|source|requires?|after|from|because|therefore)\b[\s\S]{0,300}\bDKR-\d+\b",
            text,
        )
        or has(
            r"\b(DKR|discovery)\b[\s\S]{0,900}\b(learning checkpoint|checkpoint)\b[\s\S]{0,900}"
            r"\b(promot|candidate CKRs?|candidate PKRs?|CKRs?\s*/\s*PKRs?|CKRs?\s+and\s+PKRs?)\b",
            text,
        )
        or has(
            r"\b(CKRs?\s*/\s*PKRs?|CKRs?\s+and\s+PKRs?|candidate CKRs?|candidate PKRs?)\b"
            r"[\s\S]{0,900}\b(promot|promotion|promoted)\b[\s\S]{0,900}\b(DKR|learning checkpoint|checkpoint)\b",
            text,
        )
        or has(
            r"\b(promote only after|only after [^.\n]{0,120}DKR|before any CKR or PKR candidate can be promoted)\b",
            text,
        ),
        has_check_in=has(
            r"\b(check[- ]?in|cadence|heartbeat|reevaluat|re-evaluat|recollect|learning loop|"
            r"optimi[sz]e (?:process|context)|next[_ -]?check|steering|turn ritual|round)\b",
            text,
        ),
        has_ckr_tornado=has(
            r"\b(CKR[- ]level|per[- ]CKR|each CKR|mini reverse tornado|nested reverse tornado|"
            r"mini reverse[- ]tornado|reverse tornado inside|discovery[- ]delivery balance|discovery and delivery|"
            r"discovery/delivery balance|orchestrator-owned discovery/delivery|"
            r"building up, discovery and delivery)\b",
            text,
        )
        or has(r"\bCKR\b[\s\S]{0,900}\bdiscovery/delivery balance\b", text),
        has_pkr_signals=has(
            r"\b(PKR signal|PKR signals|progress signal|progress signals|delivery signal|execution health|"
            r"off[- ]track|offtrack|steering signal|work health|progress health|quality signal)\b",
            text,
        ),
        has_orchestrator_loop=has(
            r"\b(orchestrator)\b[\s\S]{0,1200}"
            r"(objective checks?|check[- ]?ins?|OKR board|board|steer|steering|subagent)"
            r"[\s\S]{0,1200}"
            r"(objective (?:metric|target) (?:is )?(?:achieved|reached|met)|until the objective|"
            r"objective metric reaches target|until [^.\n]{0,120}metric reaches|"
            r"until [^.\n]{0,160}(?:>=|<=|==)\s*\d|"
            r"metric reaches (?:target|\d)|not stop|does not stop|"
            r"keeps? (?:checking|steering|looping|running))",
            text,
        ),
        has_subagent_work_split=has(
            r"\b(DKR|discovery)\b[\s\S]{0,800}\b(subagent|worker)\b[\s\S]{0,1200}"
            r"\b(PKR|progression|task)\b[\s\S]{0,800}\b(subagent|worker)\b",
            text,
        )
        or has(
            r"\bsubagents?\b[\s\S]{0,1200}\b(DKR|discovery)\b[\s\S]{0,1200}\b(PKR|progression|task)\b",
            text,
        ),
        has_ckr_context=has(
            r"\bCKRs?\b[\s\S]{0,900}\b(context|measurement|metric|measurable contribution)\b"
            r"[\s\S]{0,900}\b(not\s+(?:a\s+)?(?:subagent|worker|task|work)|not\s+dispatched|not\s+executable)\b",
            text,
        )
        or has(
            r"\bCKRs?\b[\s\S]{0,900}\b(not\s+(?:a\s+)?(?:subagent|worker|task|work)|not\s+dispatched|not\s+executable)\b"
            r"[\s\S]{0,900}\b(context|measurement|metric|measurable contribution)\b",
            text,
        ),
        has_dkr_learning_checkpoint=has(
            r"\b(DKR|discovery)\b[\s\S]{0,1200}"
            r"\b(learning checkpoint|discovery checkpoint|checkpoint|learning_collected|evidence collected|"
            r"questions? answered|probability update|confidence update|remaining unknowns?|next unknowns?)\b",
            text,
        )
        or has(
            r"\b(learning checkpoint|discovery checkpoint)\b[\s\S]{0,1200}"
            r"\b(DKR|discovery|evidence|probability|confidence|candidate CKRs?)\b",
            text,
        ),
        has_candidate_promotion_gate=has(
            r"\b(candidate CKRs?|candidate PKRs?)\b[\s\S]{0,1000}"
            r"\b(promot|accepted by the orchestrator|orchestrator accepts?|learning checkpoint|checkpoint accepted)\b",
            text,
        )
        or has(
            r"\b(CKRs?\s*/\s*PKRs?|CKRs?\s+and\s+PKRs?)\s+candidates?\b[\s\S]{0,1000}"
            r"\b(promot|accepted by the orchestrator|orchestrator accepts?|learning checkpoint|checkpoint accepted)\b",
            text,
        )
        or has(
            r"\b(promot|accepted by the orchestrator|orchestrator accepts?|checkpoint accepted)\b[\s\S]{0,1000}"
            r"\b(candidate CKRs?|candidate PKRs?|CKRs?/PKRs?)\b",
            text,
        )
        or has(
            r"\b(not promoted until|remain candidates until)\b[\s\S]{0,500}"
            r"\b(DKR|learning checkpoint|dkr checkpoint|orchestrator accepts?|checkpoint accepted)\b",
            text,
        )
        or has(
            r"\b(promoted[_ -]after[_ -]dkr[_ -]checkpoint|checkpoint[_ -]accepted)\b",
            text,
        )
        or has(
            r"\b(DKR|learning checkpoint|dkr checkpoint|DKR gate)\b[\s\S]{0,500}"
            r"\b(accepted|acceptance)\b[\s\S]{0,500}\bbefore\b[\s\S]{0,300}\b(promot|promotion)\b",
            text,
        ),
        has_time_based_checkin=has(
            r"\b(every\s+(?:10|ten)\s+minutes?|10[- ]minute|ten[- ]minute|timed heartbeat|"
            r"time[- ]based check[- ]?in|time[- ]based heartbeat|next_check_at)\b",
            text,
        ),
        has_worker_progress_report=has(
            r"\b(\.okra/workers|progress\.jsonl|worker-report|worker progress file|worker progress files|"
            r"file[- ]based worker reports?|file[- ]based progress reports?)\b",
            text,
        ),
    )


def solution_rush(text: str, stats: Stats) -> Violation | None:
    if stats.task_like_count >= 5 and not stats.has_valid_dkr:
        return Violation(
            "solution_rush",
            "many PKR/task-like lines appear before there is budgeted, uncertainty-aware, probability-producing DKR",
        )
    if stats.pkr_count > 0 and stats.dkr_count == 0:
        return Violation("solution_rush", "PKR appears without any DKR discovery layer")
    return None


def cascade_scoreboard(text: str, stats: Stats) -> Violation | None:
    bad_patterns = [
        r"\b(task|tasks|PKR|PKRs)\b[^\n]{0,120}\b(done|complete|completed|completion)\b"
        r"[^\n]{0,120}\b(objective|CKR|success|progress)\b"
        r"[^\n]{0,80}\b(complete|completed|success|successful|achieved|met)\b",
        r"\b(task|tasks|PKR|PKRs)\b[^\n]{0,120}\b(done|complete|completed|completion)\b"
        r"[^\n]{0,120}\b(count|counts|prove|proves|mean|means|equals?)\b"
        r"[^\n]{0,120}\b(objective|CKR|success|progress)\b",
        r"\b(rolls? up|cascade[s]? up)\b[^\n]{0,120}\b(objective|CKR|success|progress)\b",
        r"\bcompleted tasks?\b[^\n]{0,120}\b(count|prove|mean|means|equals)\b"
        r"[^\n]{0,120}\b(progress|success|objective|CKR)\b",
    ]
    for pattern in bad_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
            if is_describing_forbidden_pattern(text, match.start(), match.end()):
                continue
            if is_negated_context(text, match.start(), match.end()):
                continue
            window = match.group(0).lower()
            line = line_context(text, match.start()).lower()
            if re.search(r"\b(never|not|do not|does not|cannot|must not)\b", window) or re.search(
                r"\b(never|not|do not|does not|cannot|must not)\b", line
            ):
                continue
            return Violation("cascade_scoreboard", "task or PKR completion is treated as objective/CKR progress")
    if (stats.ckr_count > 0 or stats.pkr_count > 0) and not stats.has_direct_metric:
        return Violation("cascade_scoreboard", "CKR/PKR progress lacks direct metric read or no-cascade evidence")
    return None


def boundary_drift(text: str, stats: Stats) -> Violation | None:
    bad_patterns = [
        r"\b(agent|loop|orchestrator|model)\b[\s\S]{0,120}\b(can|may|should|will)\b"
        r"[\s\S]{0,120}\b(change|adjust|relax|redefine|retune|switch)\b"
        r"[\s\S]{0,120}\b(objective|target|threshold|anti[- ]goal|guardrail|metric|action envelope)\b",
        r"\b(change|adjust|relax|redefine|retune|switch)\b[\s\S]{0,120}"
        r"\b(objective|target|threshold|anti[- ]goal|guardrail|metric|action envelope)\b"
        r"[\s\S]{0,120}\b(if needed|automatically|without approval|when progress is slow)\b",
    ]
    if any(has(pattern, text) for pattern in bad_patterns):
        for pattern in bad_patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
                if is_describing_forbidden_pattern(text, match.start(), match.end()):
                    continue
                line = line_context(text, match.start()).lower()
                if "authority drift" in line and re.search(r"\b(trigger|opens?|when|tries|attempts)\b", line):
                    continue
                if has(
                    r"\b(never|not|do not|does not|cannot|must not)\b",
                    local_context(text, match.start(), match.end(), radius=70),
                ):
                    continue
                return Violation("boundary_drift", "artifact lets the agent alter human-owned frame or guardrails")
    if not stats.has_human_frame:
        return Violation("boundary_drift", "missing human-owned or human-ratified frame")
    return None


def metric_theater(text: str, stats: Stats) -> Violation | None:
    missing = []
    if not stats.has_objective_target:
        missing.append("objective target")
    if not stats.has_anti_goal_metric:
        missing.append("anti-goal metric")
    if not stats.has_signal_handling:
        missing.append("metric signal handling")
    if missing:
        return Violation("metric_theater", "missing " + ", ".join(missing))
    return None


def dkr_abuse(text: str, stats: Stats) -> Violation | None:
    if stats.dkr_count == 0:
        return Violation("dkr_abuse", "missing DKR discovery layer")
    missing = []
    if not stats.has_uncertainty:
        missing.append("uncertainty/probe")
    if not stats.has_dkr_budget:
        missing.append("budget/stopping rule")
    if not stats.has_probability:
        missing.append("probability/confidence output")
    if not stats.has_dkr_learning_checkpoint:
        missing.append("learning checkpoint")
    if not stats.has_candidate_promotion_gate:
        missing.append("candidate promotion gate")
    if missing:
        return Violation("dkr_abuse", "DKR lacks " + ", ".join(missing))
    if stats.dkr_count >= 6 and not has(r"\b(priorit|rank|cap|timebox|stop|budget|confidence)\b", text):
        return Violation("dkr_abuse", "many DKRs appear without prioritization, cap, or convergence rule")
    return None


def disconnected_refinement(text: str, stats: Stats) -> Violation | None:
    if not stats.has_all_units:
        return Violation("disconnected_refinement", "artifact does not contain all DKR, CKR, and PKR layers")
    if not stats.has_traceability:
        return Violation("disconnected_refinement", "DKR, CKR, and PKR layers are present but not causally linked")
    return None


def stale_steering(text: str, stats: Stats) -> Violation | None:
    missing = []
    if not stats.has_check_in:
        missing.append("check-in cadence")
    if not stats.has_ckr_tornado:
        missing.append("CKR-level discovery/delivery balance")
    if not stats.has_pkr_signals:
        missing.append("PKR progress signals")
    if not stats.has_time_based_checkin:
        missing.append("time-based heartbeat")
    if not stats.has_worker_progress_report:
        missing.append("file-based worker progress reports")
    if missing:
        return Violation("stale_steering", "missing " + ", ".join(missing))
    return None


def loop_ownership_drift(text: str, stats: Stats) -> Violation | None:
    bad_patterns = [
        r"(?m)^[^\n]*\b(assign|dispatch|spawn|run)\b[^\n]{0,100}\bCKR\b[^\n]{0,100}\b(worker|subagent)\b[^\n]*$",
        r"(?m)^[^\n]*\bCKR\b[^\n]{0,100}\b(worker|subagent)\b[^\n]{0,100}\b(executes?|does|owns|runs?|work|task|job)\b[^\n]*$",
        r"(?m)^[^\n]*\b(worker|subagent)\b[^\n]{0,100}\bCKR\b[^\n]{0,100}\b(executes?|does|owns|runs?)\b[^\n]*$",
        r"\b(loop|orchestrator)\b[\s\S]{0,180}\b(stop|stops|finish|finishes|end|ends)\b"
        r"[\s\S]{0,180}\b(board|PKR|PKRs|tasks?)\b[\s\S]{0,180}\b(done|complete|completed|empty|all)\b",
    ]
    for pattern in bad_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
            if is_describing_forbidden_pattern(text, match.start(), match.end()):
                continue
            if is_negated_context(text, match.start(), match.end()):
                continue
            return Violation(
                "loop_ownership_drift",
                "artifact treats CKR as executable worker work or stops the loop on board completion",
            )

    missing = []
    if not stats.has_orchestrator_loop:
        missing.append("orchestrator-owned loop until objective target")
    if not stats.has_subagent_work_split:
        missing.append("DKR/PKR subagent work split")
    if not stats.has_ckr_context:
        missing.append("CKR as measurable context, not work")
    if missing:
        return Violation("loop_ownership_drift", "missing " + ", ".join(missing))
    return None


RULES: list[Callable[[str, Stats], Violation | None]] = [
    solution_rush,
    cascade_scoreboard,
    boundary_drift,
    metric_theater,
    dkr_abuse,
    disconnected_refinement,
    stale_steering,
    loop_ownership_drift,
]


def analyze(text: str) -> list[Violation]:
    stats = gather_stats(text)
    return [violation for rule in RULES if (violation := rule(text, stats)) is not None]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_path(path: Path, *, json_output: bool = False) -> int:
    if not path.exists():
        print(f"missing file: {path}", file=sys.stderr)
        return 2
    violations = analyze(read_text(path))
    if json_output:
        print(json.dumps({"path": str(path), "violations": [violation.__dict__ for violation in violations]}, indent=2))
    elif violations:
        print("hard OKRA violations:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation.code}: {violation.detail}", file=sys.stderr)
    else:
        print(f"ok: {path}")
    return 1 if violations else 0


def markdown_files(path: Path) -> list[Path]:
    return sorted(child for child in path.glob("*.md") if child.is_file())


def calibrate(root: Path) -> int:
    pass_files = markdown_files(root / "pass")
    fail_files = markdown_files(root / "fail")
    expected_fail_codes = {
        "boundary-drift.md": "boundary_drift",
        "cascade-scoreboard.md": "cascade_scoreboard",
        "dkr-learning-cycle.md": "dkr_abuse",
        "disconnected-layers.md": "disconnected_refinement",
        "dkr-abuse.md": "dkr_abuse",
        "loop-ownership-drift.md": "loop_ownership_drift",
        "metric-theater.md": "metric_theater",
        "solution-rush.md": "solution_rush",
        "stale-steering.md": "stale_steering",
    }
    failures: list[str] = []
    if not pass_files:
        failures.append(f"{root / 'pass'}: no passing golden artifacts")
    if not fail_files:
        failures.append(f"{root / 'fail'}: no failing golden artifacts")

    for path in pass_files:
        violations = analyze(read_text(path))
        if violations:
            codes = ", ".join(violation.code for violation in violations)
            failures.append(f"{path}: expected pass, got violations: {codes}")

    for path in fail_files:
        violations = analyze(read_text(path))
        if not violations:
            failures.append(f"{path}: expected at least one hard violation, got pass")
            continue
        expected_code = expected_fail_codes.get(path.name)
        if expected_code and expected_code not in {violation.code for violation in violations}:
            codes = ", ".join(violation.code for violation in violations)
            failures.append(f"{path}: expected violation {expected_code}, got: {codes}")

    if failures:
        print("okra hard-gate calibration failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"okra hard-gate calibration ok: {len(pass_files)} pass, {len(fail_files)} fail")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, help="Markdown artifact to check")
    parser.add_argument("--json", action="store_true", help="print machine-readable violation output")
    parser.add_argument("--calibrate", type=Path, help="run golden pass/fail calibration under this directory")
    args = parser.parse_args()

    if args.calibrate:
        return calibrate(args.calibrate)
    if not args.path:
        parser.error("path is required unless --calibrate is used")
    return check_path(args.path, json_output=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
