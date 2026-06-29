#!/usr/bin/env python3
"""Check whether an OKRA artifact terminalizes completed-run memory before reuse."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


REQUIRED_ARTIFACTS = (
    "run-terminal.v1.json",
    "completed-run-consolidation.v1.json",
    "continuation-packet.v1.json",
    "trace-manifest.v1.jsonl",
)


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None


def count_hits(patterns: tuple[str, ...], text: str) -> int:
    return sum(1 for pattern in patterns if has(pattern, text))


def sentence_context(text: str, start: int, end: int) -> str:
    left = max(text.rfind(boundary, 0, start) for boundary in ("\n", ".", ";", "|"))
    rights = [text.find(boundary, end) for boundary in ("\n", ".", ";", "|")]
    right = min(position for position in rights if position != -1) if any(position != -1 for position in rights) else len(text)
    return text[left + 1 : right]


def negated_context(context: str) -> bool:
    return has(
        r"\b(?:no|not|never|without|missing|omits?|lacks?|do not|does not|cannot|must not|"
        r"not required|not need|no need)\b",
        context,
    )


def has_positive(pattern: str, text: str) -> bool:
    for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
        if not negated_context(sentence_context(text, match.start(), match.end())):
            return True
    return False


def local_context(text: str, start: int, end: int, radius: int = 180) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def artifact_negated(context: str) -> bool:
    return has(
        r"\b(?:do not|does not|not|never|without|missing|omits?|lacks?|no need|not need)\b"
        r"[^\n.;|]{0,160}\b(write|need|required|include|create|produce|persist|run-terminal|"
        r"completed-run-consolidation|continuation-packet|trace-manifest)\b",
        context,
    )


def artifact_is_committed(text: str, artifact: str) -> bool:
    pattern = re.escape(artifact)
    commitment = (
        r"\b(write|writes|written|record|records|recorded|create|creates|created|produce|produces|"
        r"persist|persists|include|includes|included|must|should|required|proof|bridge|prep|retention|"
        r"generated|terminal)\b"
    )
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        context = local_context(text, match.start(), match.end())
        if artifact_negated(context):
            continue
        if has(commitment, context):
            return True
    return False


def terminal_artifacts(text: str) -> Violation | None:
    missing = [artifact for artifact in REQUIRED_ARTIFACTS if not artifact_is_committed(text, artifact)]
    if missing:
        return Violation("terminal_artifacts", "missing committed " + ", ".join(missing))

    required_terminal = (
        (r"\b(objective[_ -]?metric|objective\s+metric)\b[\s\S]{0,260}\b(ref|refs|reference|references|ledger)\b", "objective metric refs"),
        (r"\banti[-_ ]?goal[_ -]?metric\b[\s\S]{0,260}\b(ref|refs|reference|references|ledger)\b", "anti-goal metric refs"),
        (r"\bunresolved\s+flags?\b|\bopen\s+flags?\b", "unresolved flags"),
        (r"\baccepted\s+DKR\b[\s\S]{0,160}\b(checkpoint|checkpoints)\b", "accepted DKR checkpoints"),
        (r"\b(second[- ]opinion|review_set|independent review)\b", "second-opinion evidence"),
        (
            r"\b(final\s+)?single_llm_truth_acceptance_count\b[\s\S]{0,120}\b(==|<=|target|final|\b0\b)\b"
            r"|\bfinal\b[\s\S]{0,80}\bsingle_llm_truth_acceptance_count\b",
            "single LLM truth read",
        ),
    )
    missing_fields = [label for pattern, label in required_terminal if not has_positive(pattern, text)]
    if missing_fields:
        return Violation("terminal_artifacts", "terminal proof missing " + ", ".join(missing_fields))
    return None


def consolidation_shape(text: str) -> Violation | None:
    missing = []
    for pattern, label in (
        (r"\btrap|traps|near[- ]miss|failure mode\b", "traps"),
        (r"\bavoidance|avoidances|veto|vetoes|guardrail screen\b", "avoidances"),
        (r"\bmisconception|misconceptions|wrong assumption|assumption corrected\b", "misconceptions"),
        (r"\boptimi[sz]ation|optimi[sz]ations|steering improvement|better allocation\b", "optimizations"),
        (r"\bcandidate[_ -]?anti[-_ ]goals?\b|\bcandidate\s+anti[- ]goals?\b", "candidate anti-goals"),
        (r"\brejected\b|\bdeferred\b|\bdo_not_assume\b|\bdo not assume\b", "rejected/deferred claims"),
        (r"\bno[- ]regression\b|\beval_regression_count\s*==\s*0\b|\bevals?\s+must\s+not\s+be\s+worse\b", "no-regression evidence"),
        (r"\breview_set\b|\bsecond[- ]opinion\b|\bindependent review\b", "review set"),
    ):
        if not has(pattern, text):
            missing.append(label)
    if missing:
        return Violation("consolidation_shape", "missing " + ", ".join(missing))
    return None


def trace_retention(text: str) -> Violation | None:
    missing = []
    if not has(r"\btrace[- ]manifest\b|\btrace-manifest\.v1\.jsonl\b", text):
        missing.append("trace manifest")
    if not has(r"\bsha256\b|\bcontent hash(?:es)?\b|\bhash(?:es)?\b", text):
        missing.append("content hashes")
    if not has(r"\bcausal\b[\s\S]{0,160}\b(decision|lesson|path|why)\b|\bwhy\b[\s\S]{0,160}\b(learned|lesson|trap|avoidance)\b", text):
        missing.append("causal decision path")
    if not has(r"\bsensitivity\b|\bredaction\b|\bretention\b|\bexpire|expiry|tombstone\b", text):
        missing.append("sensitivity/redaction/retention")
    if not has(r"\bmemory records?\b[\s\S]{0,180}\bdepend|depends|dependency|dependencies\b", text):
        missing.append("memory dependencies")
    if missing:
        return Violation("trace_retention", "missing " + ", ".join(missing))
    return None


def continuation_candidate_gate(text: str) -> Violation | None:
    missing = []
    if not has(r"\bcontinuation[- ]packet\b|\bcontinuation-packet\.v1\.json\b", text):
        missing.append("continuation packet")
    if not has(r"\b(candidate[- ]only|candidate only|candidate inputs?|unpromoted|not authority)\b", text):
        missing.append("candidate-only status")
    if not has(r"\b(current[- ]run evidence|current evidence|re-check|recheck|freshness|context fit)\b", text):
        missing.append("current-run recheck")
    if not has(r"\bhuman ratif(?:y|ies|ied|ication)|human approval\b", text):
        missing.append("human ratification")
    if missing:
        return Violation("continuation_candidate_gate", "missing " + ", ".join(missing))
    return None


def auto_authority(text: str) -> Violation | None:
    bad_patterns = (
        r"\b(?:prior|previous|completed)[- ]run\b[^\n.]{0,220}\b(?:automatically|auto[- ]?)"
        r"[^\n.]{0,160}\b(promot(?:e|es|ed|ing)|ratif(?:y|ies|ied)|chang(?:e|es|ed|ing)|rewrit(?:e|es|ten|ing)|relax(?:es|ed|ing)?|retun(?:e|es|ed|ing)|adopt(?:s|ed|ing)?|become|becomes)\b"
        r"[^\n.]{0,160}\b(frame|guardrails?|anti[- ]goals?|thresholds?|metrics?|action[- ]envelope)\b",
        r"\bcontinuation[- ]packet\b[^\n.]{0,220}\b(?:is|becomes|as)\b[^\n.]{0,80}\b(authority|source of truth)\b",
        r"\bmemory\b[^\n.]{0,220}\b(?:automatically|auto[- ]?)"
        r"[^\n.]{0,160}\b(promot(?:e|es|ed|ing)|ratif(?:y|ies|ied)|adopt(?:s|ed|ing)?|become|becomes)\b"
        r"[^\n.]{0,160}\b(frame|guardrails?|anti[- ]goals?|thresholds?|metrics?|action[- ]envelope)\b",
    )
    negated_authority = (
        r"\b(?:not|never|do not|does not|cannot|must not|reject)\b[^\n.;|]{0,140}"
        r"\b(?:automatically|auto[- ]?)?[^\n.;|]{0,80}"
        r"\b(promot(?:e|es|ed|ing)|ratif(?:y|ies|ied)|chang(?:e|es|ed|ing)|rewrit(?:e|es|ten|ing)|"
        r"relax(?:es|ed|ing)?|retun(?:e|es|ed|ing)|adopt(?:s|ed|ing)?|become|becomes)\b"
    )
    for pattern in bad_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
            if has(negated_authority, sentence_context(text, match.start(), match.end())):
                continue
            return Violation("auto_authority", "completed-run memory is treated as automatic authority")
    return None


def missing_review_fields(text: str) -> list[str]:
    if not has(r"\breview_set\b|\bstructured independent review\b|\bsecond[- ]opinion\b", text):
        return ["review_set"]
    fields = (
        ("reviewer kind", r"\breviewer (?:kind|identity)|\breviewer\b"),
        ("tool/model", r"\btool/model\b|\bmodel\b"),
        ("prompt hash", r"\bprompt hash\b"),
        ("source/content hash", r"\bsource (?:content )?hash\b|\bcontent hash\b"),
        ("verdict", r"\bverdict\b"),
        ("objections/dissent", r"\bobjections?\b|\bdissent\b"),
        ("confidence", r"\bconfidence\b"),
        ("independence basis", r"\bindependence basis\b|\bindependent basis\b"),
        ("conflict status", r"\bconflict status\b|\bconflict\b"),
        ("path/hash", r"\bpath/hash\b|\bpath and hash\b|\b(?:artifact|review)?\s*path\b[\s\S]{0,120}\b(?:artifact|review)?\s*hash\b"),
    )
    return [label for label, pattern in fields if not has_positive(pattern, text)]


def evidence_gate(text: str) -> Violation | None:
    missing = []
    if not has(r"\bsingle_llm_truth_acceptance_count\s*==\s*0\b|\bsingle[- ]LLM truth\b[\s\S]{0,120}\b(0|zero|not enough|not itself evidence)\b", text):
        missing.append("single_llm_truth_acceptance_count == 0")
    if single_model_sufficiency_violation(text):
        missing.append("reject single-LLM sufficiency")
    evidence_kinds = count_hits(
        (
            r"\bdeterministic (?:check|checker|eval|evidence|output)\b",
            r"\bstore verification\b|\bappend-only\b",
            r"\bcontent hashes?\b|\bsha256\b",
            r"\bmetric reads?\b|\bledger\b",
            r"\bchanged-path\b|\ballowed paths?\b",
            r"\bindependent review\b|\breview_set\b|\bsecond[- ]opinion\b",
            r"\bhuman ratification\b|\bhuman approval\b",
        ),
        text,
    )
    if evidence_kinds < 3:
        missing.append("at least three evidence kinds")
    missing_review = missing_review_fields(text)
    if missing_review:
        missing.append("structured review_set fields: " + ", ".join(missing_review))
    if missing:
        return Violation("evidence_gate", "missing " + ", ".join(missing))
    return None


def single_model_sufficiency_violation(text: str) -> bool:
    bad_pattern = r"\b(single|one)\s+(?:LLM|model)\b[^\n.]{0,180}\b(enough|sufficient|proof|source of truth|accepted)\b"
    local_rejection = (
        r"\bnot\s+(?:enough|sufficient|proof|accepted)\b|"
        r"\bnot itself evidence\b|"
        r"\breject\b[^\n.;|]{0,120}\b(single|one)\s+(?:LLM|model)\b|"
        r"\bno\s+single[- ]LLM\b[^\n.;|]{0,120}\baccepted\b"
    )
    for match in re.finditer(bad_pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
        context = sentence_context(text, match.start(), match.end())
        if has(local_rejection, context):
            continue
        return True
    return False


def value_verification(text: str) -> Violation | None:
    missing = []
    required_methods = (
        ("reset replay", r"\breset\b[\s\S]{0,200}\b(replay|simulation|fresh agent|next run|continuation)\b"),
        ("counterfactual or negative eval", r"\bcounterfactual\b|\bnegative eval\b|\bfailing fixture\b"),
        ("scored blindbox eval", r"\bscored (?:blindbox )?eval\b|\breal eval\b|\bblindbox\b[\s\S]{0,80}\bscored\b"),
        ("repeated-mistake metric", r"\brepeated[- ]mistake\b|\bsame mistakes?\b|\bmistake recurrence\b"),
    )
    for label, pattern in required_methods:
        if not has_positive(pattern, text):
            missing.append(label)
    for metric in (
        "prior_run_scan_miss_count",
        "trace_loss_reuse_count",
        "stale_learning_reuse_count",
        "unratified_memory_promotion_count",
    ):
        if not has(rf"\b{metric}\b[\s\S]{{0,140}}\b(==|<=|>=|\b0\b|zero|target|threshold)\b", text):
            missing.append(metric)
    if missing:
        return Violation("value_verification", "missing " + ", ".join(missing))
    return None


RULES: list[Callable[[str], Violation | None]] = [
    auto_authority,
    terminal_artifacts,
    consolidation_shape,
    trace_retention,
    continuation_candidate_gate,
    evidence_gate,
    value_verification,
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
        print("OKRA terminal-memory violations:", file=sys.stderr)
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
        "auto-authority.md": "auto_authority",
        "local-single-model-sufficiency.md": "evidence_gate",
        "missing-terminal.md": "terminal_artifacts",
        "missing-trace.md": "trace_retention",
        "negated-terminal.md": "terminal_artifacts",
        "negated-terminal-fields.md": "terminal_artifacts",
        "no-value-verification.md": "value_verification",
        "partial-review-set.md": "evidence_gate",
        "unrelated-negation-auto-authority.md": "auto_authority",
        "weak-evidence.md": "evidence_gate",
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
            failures.append(f"{path}: expected at least one terminal-memory violation, got pass")
            continue
        expected_code = expected_fail_codes.get(path.name)
        if expected_code and expected_code not in {violation.code for violation in violations}:
            failures.append(
                f"{path}: expected violation {expected_code}, got: {', '.join(v.code for v in violations)}"
            )

    if auto_authority("Do not automatically promote previous-run memory into guardrails.") is not None:
        failures.append("probe: negated automatic promotion should not trip auto_authority")
    if auto_authority("Previous-run memory automatically promotes guardrails.") is None:
        failures.append("probe: automatic promotion should trip auto_authority")
    if auto_authority("Do not accept stale traces. Previous-run memory automatically promotes guardrails.") is None:
        failures.append("probe: unrelated previous-sentence negation must not hide auto_authority")
    negated_terminal = (
        "Completed runs do not need to write run-terminal.v1.json. "
        "They still include objective metric refs and anti-goal metric refs."
    )
    terminal_violation = terminal_artifacts(negated_terminal)
    if terminal_violation is None or terminal_violation.code != "terminal_artifacts":
        failures.append("probe: negated terminal filename mention must not satisfy terminal_artifacts")
    negated_fields = (
        "The run writes run-terminal.v1.json, completed-run-consolidation.v1.json, "
        "continuation-packet.v1.json, and trace-manifest.v1.jsonl. "
        "The terminal proof does not include objective metric refs, anti-goal metric refs, "
        "unresolved flags, accepted DKR checkpoints, second-opinion evidence, or final "
        "single_llm_truth_acceptance_count == 0."
    )
    field_violation = terminal_artifacts(negated_fields)
    if field_violation is None or field_violation.code != "terminal_artifacts":
        failures.append("probe: negated terminal-proof fields must not satisfy terminal_artifacts")
    if not single_model_sufficiency_violation(
        "single_llm_truth_acceptance_count == 0. Later, one model report is sufficient proof."
    ):
        failures.append("probe: earlier rejection language must not hide later single-model sufficiency")
    if single_model_sufficiency_violation("A single LLM report is not enough proof."):
        failures.append("probe: local single-model rejection should not trip evidence_gate")

    if failures:
        print("okra terminal-memory calibration failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"okra terminal-memory calibration ok: {len(pass_files)} pass, {len(fail_files)} fail")
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
