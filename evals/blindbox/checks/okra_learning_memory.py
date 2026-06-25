#!/usr/bin/env python3
"""Check whether an OKRA artifact uses prior-run learning as governed OKR memory."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


RUN_REF = (
    r"(?:previous|prior|past|earlier)"
    r"(?:[- ](?:OKRA\s+|OKR\s+)?runs?|[- ]run(?:\s+(?:notes|memory|memories|learning|records|signals))?)"
)
LOAD_ACTION = r"(?:scan(?:s|ned|ning)?|load(?:s|ed|ing)?|bootstrap(?:s|ped|ping)?|seed(?:s|ed|ing)?|import(?:s|ed|ing)?)"
LOAD_VERB = LOAD_ACTION
AUTH_VERB = (
    r"(?:ratif(?:y|ies|ied|ying)|promot(?:e|es|ed|ing)|appl(?:y|ies|ied|ying)|"
    r"chang(?:e|es|ed|ing)|rewrit(?:e|es|ten|ing)|relax(?:es|ed|ing)?|retun(?:e|es|ed|ing)|"
    r"adopt(?:s|ed|ing)?|becom(?:e|es|ing)|became|turn(?:s|ed|ing)?\s+into)"
)
AUTH_TARGET = r"(?:frame|guardrails?|anti[- ]goals?|thresholds?|metrics?|action[- ]envelope)"


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None


def local_context(text: str, start: int, end: int, radius: int = 180) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def clause_context(text: str, start: int, end: int) -> str:
    left = max(text.rfind(boundary, 0, start) for boundary in ("\n", ".", ";", "|"))
    rights = [text.find(boundary, end) for boundary in ("\n", ".", ";", "|")]
    right = min(position for position in rights if position != -1) if any(position != -1 for position in rights) else len(text)
    return text[left + 1 : right]


def is_negated_load_context(context: str) -> bool:
    return has(
        rf"\b(?:not|never|without|no)\b[^\n.]{{0,100}}\b(?:automatically\s+)?{LOAD_ACTION}\b",
        context,
    )


def is_automatic_load_context(context: str) -> bool:
    return has(
        r"\b(automatic(?:ally)?|auto[- ]?(?:load|scan|input)|bootstrap(?:s|ped|ping)?|seed(?:s|ed|ing)?|"
        r"start of turn|run start|before (?:candidate framing|candidate frame|DKR allocation|proposing))\b",
        context,
    )


def has_prior_run_load(text: str) -> bool:
    patterns = [
        rf"\b{RUN_REF}\b[^\n.]{{0,240}}\b{LOAD_VERB}\b",
        rf"\b{LOAD_VERB}\b[^\n.]{{0,240}}\b{RUN_REF}\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            context = clause_context(text, match.start(), match.end())
            if is_negated_load_context(context):
                continue
            if not is_automatic_load_context(context + local_context(text, match.start(), match.end(), radius=180)):
                continue
            return True
    return False


def is_negated_authority_context(context: str) -> bool:
    return has(
        rf"\b(?:must\s+not|not|never|do not|does not|cannot|reject)\b[^\n.]{{0,100}}"
        rf"\b(?:auto[- ]?{AUTH_VERB}|{AUTH_VERB})\b"
        rf"|\b(?:must\s+not|not|never|do not|does not|cannot|reject)\b[^\n.]{{0,160}}"
        rf"\b{AUTH_VERB}\b[^\n.]{{0,120}}\bautomatically\b",
        context,
    )


def prior_run_auto_load(text: str) -> Violation | None:
    if not has(rf"\b{RUN_REF}\b", text):
        return Violation("prior_run_auto_load", "missing previous-run learning input")
    if not has_prior_run_load(text):
        return Violation("prior_run_auto_load", "previous-run learning is not automatically scanned or loaded")
    return None


def context_specific_memory(text: str) -> Violation | None:
    missing = []
    if not has(r"\b(OKRA|OKR)\b[\s\S]{0,300}\b(memory|learning memory)\b", text):
        missing.append("OKRA-specific memory")
    if not has(r"\b(context[-_ ]?key|project context|same project|particular context|context fit|applies_when)\b", text):
        missing.append("context fit")
    if missing:
        return Violation("context_specific_memory", "missing " + ", ".join(missing))
    return None


def prior_run_signal_grounding(text: str) -> Violation | None:
    signals = (
        "storage-governance",
        "check-in steering",
        "stale metrics",
        "eval harness",
        "observed_at",
        "recorded_at",
        "dkr_budget_overrun_count",
        "unsteered_worker_edge_count",
        "store verification",
        "content hashes",
    )
    hits = [signal for signal in signals if has(r"\b" + re.escape(signal) + r"\b", text)]
    if len(hits) < 3:
        return Violation("prior_run_signal_grounding", "missing fixture-specific prior-run signals")
    return None


def extraction_shape(text: str) -> Violation | None:
    missing = []
    for pattern, label in (
        (r"\b(trap|traps|near[- ]miss|failure mode)\b", "traps"),
        (r"\b(avoidance|avoidances|veto|vetoes|dry[- ]run|guardrail screen)\b", "avoidances"),
        (r"\b(misconception|misconceptions|wrong assumption|assumption corrected)\b", "misconceptions"),
        (r"\b(optimi[sz]ations?|optimizer|better allocation|steering improvement)\b", "optimizations"),
    ):
        if not has(pattern, text):
            missing.append(label)
    if missing:
        return Violation("extraction_shape", "missing learning extraction for " + ", ".join(missing))
    return None


def candidate_anti_goal_gate(text: str) -> Violation | None:
    missing = []
    if not has(r"\bcandidate[_ -]?anti[-_ ]goals?\b|\bcandidate\s+anti[- ]goals?\b", text):
        missing.append("candidate anti-goals")
    if not has(
        r"\b(candidate[_ -]?anti[-_ ]goals?|anti[-_ ]goals?)\b[\s\S]{0,700}"
        r"\b(metrics?|threshold|<=|>=|==|count|rate|zero|0)\b",
        text,
    ):
        missing.append("anti-goal metrics")
    if not has(r"\b(ratified|ratification|human ratifies|human approval|candidate-only|candidate only)\b", text):
        missing.append("human ratification or candidate-only status")
    if missing:
        return Violation("candidate_anti_goal_gate", "missing " + ", ".join(missing))
    return None


def named_anti_goal_metrics(text: str) -> Violation | None:
    missing = []
    for metric in (
        "prior_run_scan_miss_count",
        "unratified_memory_promotion_count",
        "eval_regression_count",
        "single_llm_truth_acceptance_count",
        "stale_learning_reuse_count",
    ):
        if not has(rf"\b{metric}\b[\s\S]{{0,160}}\b(==|<=|>=|zero|\b0\b|tripwire|threshold)\b", text):
            missing.append(metric)
    if missing:
        return Violation("named_anti_goal_metrics", "missing metric threshold for " + ", ".join(missing))
    return None


def evidence_kind_count(text: str) -> int:
    evidence_patterns = (
        r"\bindependent review\b",
        r"\bdeterministic (?:eval|check|checker|evidence|output)\b",
        r"\bcontent hashes?\b|\bsha256\b",
        r"\bmetric reads?\b",
        r"\bappend-only (?:store )?verification\b|\bstore verification\b",
        r"\bchanged-path evidence\b|\bchanged-path hashes?\b",
        r"\bhuman ratification\b|\bhuman approval\b",
    )
    return sum(1 for pattern in evidence_patterns if has(pattern, text))


def evidence_gate(text: str) -> Violation | None:
    missing = []
    if not has(
        r"\b(evidence|source_refs?|hash|sha256|ledger|append-only|metric read|deterministic check|"
        r"changed-path|eval result|review)\b",
        text,
    ):
        missing.append("evidence source")
    if not has(r"\b(evals? (?:must )?not be worse|no[- ]regression|not make evals? worse)\b", text):
        missing.append("eval no-regression metric")
    if not has(r"\bsingle[-_ ]?llm[-_ ]?truth[_ -]?acceptance[_ -]?count\s*==\s*0\b", text):
        missing.append("single_llm_truth_acceptance_count == 0")
    if evidence_kind_count(text) < 2:
        missing.append("at least two independent/deterministic evidence kinds")
    if missing:
        return Violation("evidence_gate", "missing " + ", ".join(missing))
    return None


def stress_allocation(text: str) -> Violation | None:
    missing = []
    if not has(r"\bstress\b[\s\S]{0,500}\b(time|turn|budget|anti[- ]goal|objective|pressure)\b", text):
        missing.append("stress as time/turn/budget pressure")
    if not has(
        r"\borchestrator\b[\s\S]{0,900}\b(allocate|allocation|fund|budget|rank|hold|promote|pause|veto|dispatch)\b",
        text,
    ):
        missing.append("orchestrator allocation")
    if not has(
        r"\bDKR\b[\s\S]{0,900}\b(allocator|allocation|steering decision|promote|fund|dry[- ]run|veto|pause|cannot|budget)\b",
        text,
    ):
        missing.append("DKR as learning allocator")
    if not has(r"\b(objective\b[\s\S]{0,600}\b(unachievable|cannot|clear signal|evidence)|cannot\b[\s\S]{0,500}\bobjective)\b", text):
        missing.append("clear cannot/unachievable signal")
    if missing:
        return Violation("stress_allocation", "missing " + ", ".join(missing))
    return None


def self_healing(text: str) -> Violation | None:
    if not has(r"\b(self[- ]?heal|heal|repair|recovery|corrective|pause|re-aim|reaim)\b", text):
        return Violation("self_healing", "missing repair or self-healing behavior")
    missing = []
    for pattern, label in (
        (r"\bcannot\b", "cannot"),
        (r"\bbreaking\b", "breaking"),
        (r"\bpointless\b", "pointless"),
        (r"\bauthority[_ -]?drift\b", "authority_drift"),
    ):
        if not has(pattern, text):
            missing.append(label)
    if missing:
        return Violation("self_healing", "missing flag-driven healing inputs: " + ", ".join(missing))
    return None


def auto_authority(text: str) -> Violation | None:
    bad_patterns = [
        rf"\b{RUN_REF}\b[^\n.]{{0,220}}"
        rf"\b(?:automatically\s+|auto[- ]?){AUTH_VERB}\b"
        rf"[^\n.]{{0,220}}\b{AUTH_TARGET}\b",
        rf"\b{RUN_REF}\b[^\n.]{{0,220}}\b{AUTH_VERB}\b[^\n.]{{0,120}}"
        rf"\b{AUTH_TARGET}\b"
        r"[^\n.]{0,120}\bautomatically\b",
        r"\b(memory|learning memory)\b[^\n.]{0,220}"
        rf"\b(?:automatically\s+|auto[- ]?){AUTH_VERB}\b"
        rf"[^\n.]{{0,220}}\b{AUTH_TARGET}\b",
        rf"\b(memory|learning memory)\b[^\n.]{{0,220}}\b{AUTH_VERB}\b[^\n.]{{0,120}}"
        rf"\b{AUTH_TARGET}\b"
        r"[^\n.]{0,120}\bautomatically\b",
        rf"\b(?:automatically\s+|auto[- ]?){AUTH_VERB}\b[^\n.]{{0,140}}"
        rf"\b(?:{RUN_REF}|memory|learning memory)\b[^\n.]{{0,220}}\b{AUTH_TARGET}\b",
    ]
    for pattern in bad_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
            if is_negated_authority_context(clause_context(text, match.start(), match.end())):
                continue
            return Violation("auto_authority", "prior-run memory is treated as automatic authority")
    return None


def explicit_single_llm_truth(text: str) -> Violation | None:
    bad_patterns = [
        r"\bone\s+LLM\s+final\s+answer\s+is\s+enough\b",
        r"\bsingle\s+LLM\s+truth\s+is\s+enough\b",
        r"\bone\s+LLM\s+(?:truth|final answer|narrative|self[- ]?report|claim|verdict|judg(?:e)?ment|assessment|decision)"
        r"\s+counts?\s+as\s+sufficient\s+evidence\b",
        r"\b(one|single)\s+LLM\b[^\n.]{0,180}\b(truth|final answer|narrative|self[- ]?report|claim)\b"
        r"[^\n.]{0,120}\b(?:is|are|as|counts? as|treat(?:ed)? as|accepted as)\b"
        r"[^\n.]{0,120}\b(enough|sufficient|proof|evidence)\b",
        r"\b(truth|final answer|narrative|self[- ]?report|claim)\b[^\n.]{0,180}\b(one|single)\s+LLM\b"
        r"[^\n.]{0,120}\b(?:is|are|as|counts? as|treat(?:ed)? as|accepted as)\b"
        r"[^\n.]{0,120}\b(enough|sufficient|proof|evidence)\b",
        r"\b(one|single)\s+(?:LLM|models?'?s?)\b[^\n.]{0,120}"
        r"\b(report|narrative|answer|claim|word|verdict|judg(?:e)?ment|assessment|decision)\b"
        r"[^\n.]{0,120}\b(enough|sufficient|suffices?|acceptable|proof|evidence|accepted)\b",
        r"\baccept(?:s|ed|ing)?\b[^\n.]{0,120}\b(one|single)\s+LLM\b"
        r"[^\n.]{0,120}\b(truth|final answer|narrative|self[- ]?report|claim)\b",
        r"\b(one|single)\s+(?:LLM|model)\b[^\n.]{0,160}\bsource of truth\b",
        r"\bthe model\b[^\n.]{0,80}\b(?:is|as|becomes?)\b[^\n.]{0,80}\bsource of truth\b",
    ]
    for pattern in bad_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
            match_text = match.group(0)
            clause = re.split(r"[.;\n|]", match_text, maxsplit=1)[0]
            prefix = text[max(0, match.start() - 80) : match.start()]
            suffix = text[match.end() : min(len(text), match.end() + 120)]
            guard_context = prefix + match_text
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end == -1:
                line_end = len(text)
            line = text[line_start:line_end]
            heading_context = text[max(0, match.start() - 260) : match.start()]
            if has(
                r"\bnot\s+(?:enough|sufficient|proof|evidence|accepted|acceptance)\b"
                r"|\bnot\s+[^\n.]{0,80}\b(one|single)\s+LLM\b",
                match_text,
            ) or has(
                r"\b(?:no|not|never|do not|does not|cannot|must not)\b[^\n.;:|]{0,80}$",
                prefix,
            ) or has(
                r"\bnever\s+enough\b|\bnot\s+itself\s+evidence\b",
                match_text + suffix,
            ) or has(
                r"\bforbidden moves\s*:\s*$",
                heading_context,
            ) and has(
                r"^\s*[-*]\s*accept(?:s|ed|ing)?\b",
                line,
            ) or has(
                r"\b(prevents?|rejects?|rejected|forbids?|disallows?|blocks?|tripwire|metric|count)\b"
                r"[^\n.;|]{0,120}\b(accept|accepting|accepted|sufficient|proof|evidence|narrative|claim|report)\b",
                guard_context,
            ):
                continue
            return Violation("evidence_gate", "single LLM narrative is accepted as evidence")
    return None


RULES: list[Callable[[str], Violation | None]] = [
    auto_authority,
    explicit_single_llm_truth,
    prior_run_auto_load,
    context_specific_memory,
    prior_run_signal_grounding,
    extraction_shape,
    candidate_anti_goal_gate,
    named_anti_goal_metrics,
    evidence_gate,
    stress_allocation,
    self_healing,
]


def analyze(text: str) -> list[Violation]:
    return [violation for rule in RULES if (violation := rule(text)) is not None]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_path(path: Path, *, json_output: bool = False) -> int:
    if not path.exists():
        print(f"missing file: {path}", file=sys.stderr)
        return 2
    violations = analyze(read_text(path))
    if json_output:
        import json

        print(json.dumps({"path": str(path), "violations": [violation.__dict__ for violation in violations]}, indent=2))
    elif violations:
        print("OKRA learning-memory violations:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation.code}: {violation.detail}", file=sys.stderr)
    else:
        print(f"ok: {path}")
    return 1 if violations else 0


def markdown_files(path: Path) -> list[Path]:
    return sorted(child for child in path.glob("*.md") if child.is_file()) if path.exists() else []


def calibrate(root: Path) -> int:
    pass_files = markdown_files(root / "pass")
    fail_files = markdown_files(root / "fail")
    expected_fail_codes = {
        "auto-ratifies.md": "auto_authority",
        "generic-memory.md": "context_specific_memory",
        "no-eval-guard.md": "evidence_gate",
        "no-prior-runs.md": "prior_run_auto_load",
        "single-llm-truth.md": "evidence_gate",
    }
    failures: list[str] = []
    if not pass_files:
        failures.append(f"{root / 'pass'}: no passing golden artifacts")
    if not fail_files:
        failures.append(f"{root / 'fail'}: no failing golden artifacts")

    for path in pass_files:
        violations = analyze(read_text(path))
        if violations:
            failures.append(f"{path}: expected pass, got violations: {', '.join(v.code for v in violations)}")

    for path in fail_files:
        violations = analyze(read_text(path))
        if not violations:
            failures.append(f"{path}: expected at least one learning-memory violation, got pass")
            continue
        expected_code = expected_fail_codes.get(path.name)
        if expected_code and expected_code not in {violation.code for violation in violations}:
            failures.append(
                f"{path}: expected violation {expected_code}, got: {', '.join(v.code for v in violations)}"
            )

    if has_prior_run_load("Previous-run notes are not automatically loaded; an operator can manually scan them later."):
        failures.append("probe: manual later prior-run scan must not satisfy automatic input loading")
    if not has_prior_run_load("Previous-run notes are automatic inputs; scan/load them before DKR allocation."):
        failures.append("probe: automatic prior-run load wording should satisfy prior-run input loading")
    if auto_authority("Do not automatically promote prior-run notes into guardrails.") is not None:
        failures.append("probe: negated automatic promotion should not trip auto_authority")
    if auto_authority("Automatically promote prior-run notes into guardrails.") is None:
        failures.append("probe: automatic promotion should trip auto_authority")
    if auto_authority("Prior-run memories automatically become current guardrails.") is None:
        failures.append("probe: automatic become guardrails should trip auto_authority")
    if auto_authority("Prior-run notes are automatically adopted as action-envelope rules.") is None:
        failures.append("probe: automatic adopted action-envelope rules should trip auto_authority")
    if explicit_single_llm_truth(
        "No single LLM truth rule: single LLM truth is enough evidence to accept a learned anti-goal."
    ) is None:
        failures.append("probe: colon-prefixed single-LLM acceptance should trip evidence_gate")
    if explicit_single_llm_truth("A single LLM verdict suffices for memory acceptance.") is None:
        failures.append("probe: single-LLM verdict should trip evidence_gate")
    if explicit_single_llm_truth("The model is the source of truth for learning acceptance.") is None:
        failures.append("probe: model source-of-truth should trip evidence_gate")
    if explicit_single_llm_truth(
        "No single LLM truth is accepted: a model final answer can point to evidence, but it is not itself evidence."
    ) is not None:
        failures.append("probe: explicit rejection of single-LLM truth should not trip evidence_gate")

    if failures:
        print("okra learning-memory calibration failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"okra learning-memory calibration ok: {len(pass_files)} pass, {len(fail_files)} fail")
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
