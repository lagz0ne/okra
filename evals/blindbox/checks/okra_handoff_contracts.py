#!/usr/bin/env python3
"""Check OKRA handoff contracts between DKR, CKR, PKR, and learning memory.

This checker targets the transition surfaces that are easy to blur in prose:
worker prompt packets, in-progress evidence gates, DKR-to-DKR follow-up, CKR-to-PKR
traceability, PKR hand-back on uncertainty, and accumulated anti-goal reuse.
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


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None


def has_unrejected(pattern: str, text: str, *, prefix_chars: int = 80) -> bool:
    rejection_pattern = r"\b(reject|block|fail|veto|forbid|disallow)\b"
    for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
        prefix = text[max(0, match.start() - prefix_chars) : match.start()]
        sentence_prefix = re.split(r"[.\n]", prefix)[-1]
        if not has(rejection_pattern, sentence_prefix):
            return True
    return False


def markdown_files(path: Path) -> list[Path]:
    return sorted(child for child in path.glob("*.md") if child.is_file())


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def heading_section(text: str, heading_patterns: list[str], *, max_chars: int = 5000) -> str:
    for pattern in heading_patterns:
        heading = re.search(rf"^(#{{1,6}})\s+[^\n]*{pattern}[^\n]*$", text, flags=re.IGNORECASE | re.MULTILINE)
        if not heading:
            continue
        level = len(heading.group(1))
        following = text[heading.end() :]
        next_heading = re.search(rf"^#{{1,{level}}}\s+", following, flags=re.MULTILINE)
        end = heading.end() + next_heading.start() if next_heading else len(text)
        return text[heading.start() : min(end, heading.start() + max_chars)]
    return ""


def anchored_scope(text: str, anchor_patterns: list[str], *, max_chars: int = 4500) -> str:
    for pattern in anchor_patterns:
        anchor = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if anchor:
            return text[anchor.start() : anchor.start() + max_chars]
    return text[:max_chars]


def contract_scope(text: str, heading_patterns: list[str], anchor_patterns: list[str], *, max_chars: int = 5000) -> str:
    return heading_section(text, heading_patterns, max_chars=max_chars) or anchored_scope(text, anchor_patterns, max_chars=max_chars)


def worker_prompt_packet(text: str) -> Violation | None:
    packet_pattern = r"\b(worker prompt packet|dispatch packet|next[- ]prompt packet|worker assignment packet)\b"
    packet_scope = contract_scope(
        text,
        [r"worker\s+prompt\s+packet", r"dispatch\s+packet", r"worker\s+assignment\s+packet"],
        [packet_pattern],
        max_chars=5000,
    )

    frame_scope = packet_scope
    frame_json = re.search(r'"(?:frame|frame_fields)"\s*:\s*\{', packet_scope, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if frame_json:
        frame_scope = packet_scope[frame_json.start() : frame_json.start() + 1000]
    else:
        frame_anchor = re.search(r"\bframe fields?\b", packet_scope, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if frame_anchor:
            frame_tail = packet_scope[frame_anchor.start() : frame_anchor.start() + 1000]
            boundary = re.search(
                r"(?:\n|\.\s+)\s*-?\s*(?:\*\*)?(current[_ ]state(?:_fields)?|current state|previous[_ ]dkr[_ ]checkpoint(?:_fields)?|previous DKR|previous checkpoint|assignment(?:_fields)?|budget|hand[- ]back|output schema)\b",
                frame_tail,
                flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
            )
            frame_scope = frame_tail[: boundary.start()] if boundary else frame_tail

    frame_field = (
        r"anti_goals?|relevant_anti_goals|anti[- ]goals?|action_envelope|action envelope|human[- ]ratified boundaries?|"
        r"human boundaries?|human boundary|human ratification|human approval"
    )
    omitted = r"not included|need not be included|need not include|may skip|skip|omits?|omitted|absent|excluded|does not require|do not require|not required|not mandatory|not part of|not in (?:the )?packet"
    optional = r"(?:is|are|as|marked|declared|treated as)\s+optional"
    if has_unrejected(rf"\b({frame_field})\b[\s\S]{{0,180}}\b({omitted})\b", packet_scope) or has_unrejected(
        rf"\b({omitted})\b[\s\S]{{0,180}}\b({frame_field})\b",
        packet_scope,
    ) or has(
        rf"\b({frame_field})\b[\s\S]{{0,180}}\b({optional})\b",
        frame_scope,
    ) or has(
        rf"\b(?:frame fields?|objective)\b(?:(?!\b(?:reject|block|fail|veto|forbid|disallow)\b)[^.\n]){{0,120}}\bwithout\b[^.\n]{{0,120}}\b({frame_field})\b",
        packet_scope,
    ):
        return Violation("worker_prompt_packet", "packet frame fields are explicitly omitted")

    missing = []
    checks = {
        "worker prompt packet or dispatch packet": packet_pattern,
        "frame objective": r"\b(objective|objective_metric_id|objective_target|objective_ref)\b",
        "frame anti-goals": r"\b(anti_goals?|relevant_anti_goals|anti_goal_ids_in_scope|anti_goal_refs?|anti_goals_ref|anti[- ]goals?)\b",
        "frame action envelope": r"\b(action_envelope|action envelope)\b",
        "frame human boundary": r"\b(human[- ]ratified boundaries?|human boundaries?|human boundary|human ratification|human approval|ratified frame|human-set|read_only|read-only|frame_hash)\b",
        "current state fields": r"\b(current_state|current state|current_round|current round|fresh|stale|open_flags|open flags?|active CKR|active PKR|remaining budget)\b",
        "previous checkpoint fields": r"\b(previous_dkr_checkpoint|previous DKR|previous checkpoint|source_dkr_checkpoint|source DKR checkpoint|accepted checkpoint|held checkpoint)\b",
        "assignment fields": r"\b(worker type|worker_kind|assignment|exact_task|exact scope|allowed_actions|allowed actions?|forbidden_actions|forbidden actions?)\b",
        "budget and stop rule": r"\b(budget_and_stop_rule|budget|stop_rule|stop rule|stopping rule|timebox|turn budget)\b",
        "hand-back rule": r"\b(hand_back_rule|hand[- ]back rule|hands? back|stop and report unknown|unknown discovery)\b",
        "output schema": r"\b(output schema|write back|progress\.jsonl|worker progress|learning checkpoint|changed paths?)\b",
    }
    for label, pattern in checks.items():
        if label == "worker prompt packet or dispatch packet":
            scope = text
        elif label in {"frame objective", "frame anti-goals", "frame action envelope"}:
            scope = frame_scope
        else:
            scope = packet_scope
        if not has(pattern, scope):
            missing.append(label)
    if missing:
        return Violation("worker_prompt_packet", "missing " + ", ".join(missing))
    return None


def in_progress_evidence_gate(text: str) -> Violation | None:
    scope = contract_scope(
        text,
        [r"in[- ]progress", r"governed\s+records", r"influence\s+rule"],
        [r"\b(in[- ]progress|governed records|worker progress|progress\.jsonl)\b"],
        max_chars=4000,
    )
    scope_one_line = compact(scope)
    narrative_source = r"freeform\s+(?:worker\s+)?narrative|worker\s+narrative|vibes|self[- ]report|model\s+narrative|chat\s+continuation"
    dispatch_target = r"next\s+prompt|next\s+dispatch|next\s+worker|next\s+DKR|allocation|steering\s+decision"
    if has(
        rf"\b({narrative_source})\b\s+(?:may|can|could)\s+"
        r"\b(influence|steer|shape|inform|feed|affect)\b"
        rf"[\s\S]{{0,120}}\b({dispatch_target})\b"
        r"|"
        rf"\b({narrative_source})\b\s+(?:may|can|could)\s+be\s+used\s+as\s+(?:context|input)\b"
        rf"[\s\S]{{0,160}}\b({dispatch_target})\b"
        r"|"
        rf"\b({narrative_source})\b[\s\S]{{0,160}}\b(?:but|however|nevertheless)\b"
        r"[\s\S]{0,80}\b(?:it\s+)?(?:may|can|could|is allowed to)\s+"
        r"\b(influence|steer|shape|inform|feed|affect)\b"
        rf"[\s\S]{{0,120}}\b({dispatch_target})\b",
        scope_one_line,
    ):
        return Violation("in_progress_evidence_gate", "freeform narrative is allowed to influence dispatch")
    if has(
        rf"\b({narrative_source})\b[\s\S]{{0,160}}\b(?:but|however|nevertheless)\b"
        r"[\s\S]{0,100}\b(?:it\s+)?(?:may|can|could|should|must|will|is allowed to)\s+be\s+used\s+as\s+(?:context|input)\b"
        rf"[\s\S]{{0,160}}\b({dispatch_target})\b",
        scope_one_line,
    ):
        return Violation("in_progress_evidence_gate", "freeform narrative is allowed to influence dispatch")
    if has(
        rf"\b({narrative_source})\b[\s\S]{{0,160}}\b(?:but|however|nevertheless)\b"
        r"[\s\S]{0,100}\b(?:it\s+)?(?:is|gets|becomes)\s+used\s+as\s+(?:context|input)\b"
        rf"[\s\S]{{0,160}}\b({dispatch_target})\b",
        scope_one_line,
    ):
        return Violation("in_progress_evidence_gate", "freeform narrative is allowed to influence dispatch")
    if has(
        rf"\b({narrative_source})\b[\s\S]{{0,160}}\b(?:but|however|nevertheless)\b"
        r"[\s\S]{0,120}\b(?:it\s+)?(?:(?:should|must|will)\s+)?(?:inform|informs|feed|feeds|shape|shapes|affect|affects|steer|steers)\b"
        rf"[\s\S]{{0,160}}\b({dispatch_target})\b",
        scope_one_line,
    ):
        return Violation("in_progress_evidence_gate", "freeform narrative is allowed to influence dispatch")
    if has(
        rf"\b({dispatch_target})\b[\s\S]{{0,140}}\b(?:may|can|could|is allowed to)\s+be\s+"
        r"(?:influenced|informed|fed|shaped|affected|steered)\b"
        rf"[\s\S]{{0,160}}\b({narrative_source})\b",
        scope_one_line,
    ):
        return Violation("in_progress_evidence_gate", "freeform narrative is allowed to influence dispatch")
    if has(
        rf"\b({dispatch_target})\b[\s\S]{{0,140}}\b(?:may|can|could|should|must|will|is allowed to)\s+use\b"
        rf"[\s\S]{{0,160}}\b({narrative_source})\b[\s\S]{{0,80}}\b(context|input)\b",
        scope_one_line,
    ):
        return Violation("in_progress_evidence_gate", "freeform narrative is allowed to influence dispatch")

    missing = []
    checks = {
        "governed in-progress records": r"\b(worker progress|progress\.jsonl|check[- ]ins?|metric reads?|ledger|flags?|accepted checkpoints?)\b",
        "next dispatch influence": r"\b(next dispatch|next prompt|next worker|next DKR|allocation|steering decision)\b",
        "freeform narrative rejection": (
            r"\b(never|cannot|can't|must not|reject)\b[\s\S]{0,220}"
            r"\b(freeform (?:worker )?narrative|worker narrative|vibes|self[- ]report|model narrative|chat continuation)\b"
        r"|"
        r"\b(freeform (?:worker )?narrative|worker narrative|vibes|self[- ]report|model narrative|chat continuation)\b"
            r"[\s\S]{0,220}\b(not[\W_]{0,12}evidence|not sufficient|cannot influence|must not influence|reject|never itself evidence|never evidence|never a valid input|never valid input|must never)\b"
            r"|"
            r"\b(freeform (?:worker )?narrative|worker narrative|vibes|self[- ]report|model narrative|chat continuation)\b"
            r"[\s\S]{0,220}\b(record is (?:the )?evidence|record path/hash|cite the record)\b"
        ),
    }
    for label, pattern in checks.items():
        if not has(pattern, scope):
            missing.append(label)
    if missing:
        return Violation("in_progress_evidence_gate", "missing " + ", ".join(missing))
    return None


def dkr_to_dkr_handoff(text: str) -> Violation | None:
    dkr_scope = contract_scope(
        text,
        [r"DKR\s*(?:[- ]?to[- ]?|->|→)\s*DKR[^\n]*handoff", r"handoff[^\n]*previous\s+DKR"],
        [r"^Every handoff from a previous DKR checkpoint", r"\bprevious DKR learning checkpoint\b", r"\bprevious DKR\b"],
        max_chars=3500,
    )

    empty_risk_implications = (
        r"\b(risk_or_anti_goal_implications|risk[_ -]?anti[_ -]?goal[_ -]?implications|"
        r"risk(?:s)? or anti[-_ ]goal implications?|risk(?:s)?/anti[-_ ]goal implications?|"
        r"anti[-_ ]goal implications?)\b\s*:?\s*\b(none recorded|none|not required|no implications?|empty|n/a|tbd|to be determined|unknown|unclear|pending)\b"
        r"|"
        r"\b(no|none|not required|no recorded)\b[\s\S]{0,120}"
        r"\b(risk(?:s)? or anti[-_ ]goal implications?|risk(?:s)?/anti[-_ ]goal implications?|anti[-_ ]goal implications?)\b"
    )
    if has(empty_risk_implications, dkr_scope):
        return Violation("dkr_to_dkr_handoff", "risk or anti-goal implications are empty")

    missing = []
    checks = {
        "previous DKR checkpoint": r"\b(previous_checkpoint|previous DKR|source DKR|prior DKR)\b[\s\S]{0,900}\b(learning checkpoint|checkpoint)\b",
        "decision target": r"\bdecision target|decision to unlock|steering decision|whether to (?:promote|fund|dry[- ]run|veto|pause|re-aim|reaim|escalate)\b",
        "evidence refs or hashes": r"\b(evidence_refs_or_hashes|evidence_refs?|evidence refs?|evidence hashes?|source refs?|content hashes?|trace refs?|prompt hash)\b",
        "confidence update": r"\b(confidence_probability_update|confidence_or_probability_update|probability_confidence_update|probability_confidence|confidence[_ -]?update|probability[_ -]?update|confidence|probability|posterior|likelihood)\b[\s\S]{0,180}\b(update|after|before|changed|delta|score|prior|posterior|basis|value)\b",
        "answered questions": r"\b(answered questions?|questions answered|answered_questions|questions_answered|answered and unanswered questions?)\b",
        "unanswered questions": r"\b(unanswered questions?|unanswered_questions|questions_unanswered|remaining unknowns?|remaining_unknowns|next unknowns?|next_unknowns)\b",
        "risk or anti-goal implications": r"\b(risk_or_anti_goal_implications|risk[_ -]?anti[_ -]?goal[_ -]?implications|risk(?:s)? or anti[-_ ]goal implications?|risk(?:s)?/anti[-_ ]goal implications?|anti[-_ ]goal uncertainty|risk reduced|risk implication|anti[-_ ]goal implications?)\b",
        "orchestrator checkpoint decision": r"\b(orchestrator[_ -]?(?:decision|acceptance)|orchestrator checkpoint decision|checkpoint decision)\b[\s\S]{0,180}\b(accepted|held|rejected|needs[_ -]?follow[_ -]?up)\b|\b(accepted|held|rejected|needs[_ -]?follow[_ -]?up)\b[\s\S]{0,100}\b(orchestrator[_ -]?(?:decision|acceptance)|orchestrator checkpoint decision|checkpoint decision)\b",
        "next DKR scoped by prior evidence": r"\b(next DKR|next_dkr_scope|follow[- ]up DKR)\b[\s\S]{0,700}\b(scope|only|focused|reduce|uncertainty|derived|traceable)\b",
    }
    for label, pattern in checks.items():
        if not has(pattern, dkr_scope):
            missing.append(label)
    if missing:
        return Violation("dkr_to_dkr_handoff", "missing " + ", ".join(missing))
    return None


def ckr_pkr_traceability(text: str) -> Violation | None:
    scope = heading_section(
        text,
        max_chars=5000,
        heading_patterns=[r"CKR[^\n]*value", r"CKR[^\n]*(?:toward|to)\s+PKR", r"CKR[^\n]*traceability", r"PKR[^\n]*traceability"],
    )
    if not scope:
        scope = text
    trace_field = (
        r"linked_ckr|linked CKR|CKR link|source CKR|source_dkr_checkpoint|source DKR checkpoint|"
        r"source DKR|DKR checkpoint ref|contribution_metric|contribution metric|direct CKR metric|"
        r"CKR metric"
    )
    local = r"(?:(?!\.\s)[\s\S])"
    negated_trace_patterns = [
        rf"\bPKRs?\b{local}{{0,220}}\bbut\b{local}{{0,120}}\b(?:does not|do not|doesn't|don't)\s+(?:carry|include|have)\b{local}{{0,140}}\b({trace_field})\b",
        rf"\bPKRs?\b{local}{{0,220}}\blacks?\b{local}{{0,140}}\b({trace_field})\b",
        rf"\bPKRs?\b{local}{{0,220}}\b(?:need not|needn't|does not need to|do not need to|does not require|do not require|doesn't require|don't require|not required to)\s+(?:(?:carry|include|have)\b\s*)?{local}{{0,140}}\b({trace_field})\b",
        rf"\bPKRs?\b{local}{{0,220}}\b(?:may|can|could)\s+(?:omit|skip|leave out)\b{local}{{0,140}}\b({trace_field})\b",
        rf"\bPKRs?\b{local}{{0,260}}\b({trace_field})\b{local}{{0,180}}\bonly when (?:available|known|present)\b{local}{{0,180}}\b(?:omit|skip|leave out)\b",
        rf"\bPKRs?\b{local}{{0,260}}\b({trace_field})\b{local}{{0,220}}\botherwise\b{local}{{0,80}}\b(?:may|can|could)?\s*(?:omit|skip|leave out)\b",
        rf"\bPKRs?\b{local}{{0,220}}\b({trace_field})\b{local}{{0,140}}\b(optional|not required|not mandatory)\b",
    ]
    if any(has_unrejected(pattern, scope, prefix_chars=80) for pattern in negated_trace_patterns):
        return Violation("ckr_pkr_traceability", "PKR traceability fields are explicitly negated")

    missing = []
    checks = {
        "CKR as measurable context": r"\b(?:CKRs?|A CKR|Each CKR)\b[\s\S]{0,500}\b(measurable contribution|contribution metric|direct CKR metric|context)\b",
        "CKR not worker work": r"\b(?:CKRs?|A CKR|Each CKR)\b[\s\S]{0,800}\b(not (?:a )?(?:worker|subagent|task|executable|job)|not\s+dispatched|not worker work|never\s+dispatched|no CKR worker)\b",
        "PKR linked CKR": r"\b(linked_ckr|linked CKR|CKR link|source CKR)\b",
        "PKR source DKR checkpoint": r"\b(source_dkr_checkpoint|source DKR checkpoint|source DKR|DKR checkpoint ref)\b",
        "PKR contribution metric": r"\b(contribution_metric|contribution metric|direct CKR metric|CKR metric)\b",
        "PKR done check": r"\b(done_check|done check|acceptance check|completion check|changed paths?|commands run)\b",
        "PKR progress signals": r"\b(progress signals?|off[- ]track|quality drift|churn|late discovery|stale metrics?|scope concern|authority concern)\b",
    }
    for label, pattern in checks.items():
        if not has(pattern, scope):
            missing.append(label)
    if missing:
        return Violation("ckr_pkr_traceability", "missing " + ", ".join(missing))
    return None


def pkr_discovery_handback(text: str) -> Violation | None:
    scope = heading_section(
        text,
        max_chars=4500,
        heading_patterns=[r"CKR[^\n]*value", r"CKR[^\n]*(?:toward|to)\s+PKR", r"PKR[^\n]*hand", r"PKR[^\n]*traceability"],
    )
    if not scope:
        scope = text
    bad = r"\b(figure out whatever is missing|resolve unknowns?|research unknowns?|discover as needed|decide the missing|improvise)\b"
    pkr_anchor = r"\b(PKRs?|PKR prompt|progression workers?)\b"
    for match in re.finditer(bad, scope, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
        context = scope[max(0, match.start() - 340) : match.start()]
        suffix = scope[match.end() : min(len(scope), match.end() + 160)]
        if not has(pkr_anchor, context) and not has(pkr_anchor, suffix):
            continue
        prefix = scope[max(0, match.start() - 80) : match.start()]
        if has(r"\b(must not|mustn't|never|cannot|can't|do not|don't|does not|doesn't|not)\s+(?:\w+\s+){0,3}$", prefix):
            continue
        if has(r"\b(rather than|instead of)\s+(?:\w+\s+){0,4}$", prefix):
            continue
        return Violation("pkr_discovery_handback", "PKR absorbs discovery instead of handing back")
    if not has(
        r"\bPKRs?\b[\s\S]{0,900}\b(hand[s]? back|stops? and reports? (?:the )?unknown|stop and report unknown|unknown discovery|orchestrator decides whether to spawn|late discovery)\b",
        scope,
    ):
        return Violation("pkr_discovery_handback", "missing PKR unknown hand-back rule")
    return None


def accumulated_antigoals(text: str) -> Violation | None:
    def has_unratified_promotion(pattern: str) -> bool:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
            prefix = text[max(0, match.start() - 80) : match.start()]
            if has(r"\b(reject|block|fail|veto|forbid|disallow)\b", prefix):
                continue
            window = text[max(0, match.start() - 80) : min(len(text), match.end() + 180)]
            if (
                has(r"\b(after|once|only after|when|if)\b", window)
                and has(r"\b(current evidence|current[- ]run evidence|current[- ]context evidence|current fit|current[- ]context fit)\b", window)
                and has(r"\b(human ratif(?:ication|ied)?|human approval)\b", window)
            ):
                continue
            return True
        return False

    if has_unratified_promotion(
        r"\b(previous|prior|accumulated|candidate)\b"
        r"(?:(?!\b(?:not|never|cannot|can't|must not|mustn't|do not|don't|candidate[- ]only|not automatic authority)\b)[^.\n]){0,160}"
        r"\banti[- ]goals?\b"
        r"(?:(?!\b(?:not|never|cannot|can't|must not|mustn't|do not|don't|candidate[- ]only|not automatic authority)\b)[^.\n]){0,160}"
        r"\b(automatically promoted|auto[- ]promoted|gets? promoted automatically|promoted automatically|becomes? active|active by default|default[- ]active|applied by default|enforced by default|used as defaults? for (?:the )?active frame|loaded as active(?: guardrails?)?|loaded[^.\n]{0,80}by default|active guardrails?[^.\n]{0,80}by default|must be applied|rewrite the frame)\b",
    ):
        return Violation("accumulated_antigoals", "accumulated anti-goals are auto-promoted")
    if has_unratified_promotion(
        r"(?<!not )(?<!never )(?<!do not )(?<!don't )(?<!must not )"
        r"\b(automatically promote|auto[- ]promote|promote automatically)\b"
        r"(?:(?!\b(?:not|never|cannot|can't|must not|mustn't|do not|don't|candidate[- ]only|not automatic authority)\b)[^.\n]){0,220}"
        r"\b(previous|prior|accumulated|candidate)[-_ ]?(?:run)?\b[^.\n]{0,160}\banti[- ]goals?\b",
    ):
        return Violation("accumulated_antigoals", "accumulated anti-goals are auto-promoted")
    if has_unratified_promotion(
        r"\b(?:orchestrator|loop|agent|model)?\b[^.\n]{0,80}\b(?:may|can|could|is allowed to)\s+promote\b"
        r"[^.\n]{0,220}\b(previous|prior|accumulated|candidate)[-_ ]?(?:run)?\b[^.\n]{0,160}\banti[- ]goals?\b"
        r"[^.\n]{0,100}\bautomatically\b",
    ):
        return Violation("accumulated_antigoals", "accumulated anti-goals are auto-promoted")
    if has_unratified_promotion(
        r"\bautomatically\s+(?:apply|enforce|load|use)\b"
        r"[^.\n]{0,220}\b(previous|prior|accumulated|candidate)[-_ ]?(?:run)?\b[^.\n]{0,160}\banti[- ]goals?\b"
        r"[^.\n]{0,100}\b(active frame|frame|guardrails?|defaults?)\b",
    ):
        return Violation("accumulated_antigoals", "accumulated anti-goals are auto-promoted")

    candidate_anchors = list(re.finditer(
        r"\b(candidate-anti-goals\.v1\.json|candidate anti[- ]goals? artifact|candidate guardrail library)\b",
        text,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    ))
    candidate_scope = text
    if candidate_anchors:
        candidate_scope = text[candidate_anchors[-1].start() : candidate_anchors[-1].start() + 3000]
        for anchor in candidate_anchors:
            window = text[anchor.start() : anchor.start() + 3000]
            if has(
                r"\b(each entry|each record)\b[\s\S]{0,500}\b(metric_id|metric id|threshold)\b"
                r"|\b(metric_id|metric id)\b[\s\S]{0,500}\bthreshold\b",
                window,
            ):
                candidate_scope = window
                break
    if has(
        r"\b(does not require|does not include|do not include|missing|omits?|never says|never states)\b"
        r"[\s\S]{0,180}\b(metric_id|metric id|threshold|type|tripwire|drift|applies_when|"
        r"does_not_apply_when|invalidates_when|recertify_by|valid_until|source_refs|source refs?|"
        r"candidate_status|no_regression_evidence|trace_manifest_ref)\b",
        candidate_scope,
    ):
        return Violation("accumulated_antigoals", "candidate anti-goal fields are explicitly omitted")

    missing = []
    checks = {
        "candidate anti-goal artifact": r"\b(candidate-anti-goals\.v1\.json|candidate anti[- ]goals? artifact|candidate guardrail library)\b",
        "metric_id": r"\b(metric_id|metric id)\b",
        "threshold": r"\bthreshold\b",
        "type": r"\b(type\b[\s\S]{0,80}\b(tripwire|drift)\b|(tripwire|drift)\b[\s\S]{0,80}\btype\b|\"type\"\s*:\s*\"(?:tripwire|drift)\")",
        "applies_when": r"\b(applies_when|applies when|context fit)\b",
        "does_not_apply_when": r"\b(does_not_apply_when|does not apply when|doesn't apply when|must not be loaded)\b",
        "invalidates or recertifies": r"\b(invalidates_when|invalidates when|recertify_by|recertify by|valid_until|valid until)\b",
        "source refs": r"\b(source_refs|source refs?|source run|source_run_id)\b",
        "candidate status": r"\b(candidate_status|candidate[- ]only|ratified|rejected|superseded)\b",
        "human ratification boundary": r"\b(human_ratification_boundary|human ratif(?:ication|ied|y)?|human approval|ratification_status|unratified_memory_promotion_count\s*==\s*0)\b",
        "no-regression evidence": r"\b(no_regression_evidence|no[- ]regression evidence|eval_regression_count\s*==\s*0)\b",
        "trace evidence": r"\b(trace_evidence|trace_manifest_ref|trace manifest|trace evidence|evidence hashes?)\b",
    }
    for label, pattern in checks.items():
        scope = text if label == "candidate anti-goal artifact" else candidate_scope
        if not has(pattern, scope):
            missing.append(label)
    if missing:
        return Violation("accumulated_antigoals", "missing " + ", ".join(missing))
    return None


RULES: list[Callable[[str], Violation | None]] = [
    worker_prompt_packet,
    in_progress_evidence_gate,
    dkr_to_dkr_handoff,
    ckr_pkr_traceability,
    pkr_discovery_handback,
    accumulated_antigoals,
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
        print(json.dumps({"path": str(path), "violations": [violation.__dict__ for violation in violations]}, indent=2))
    elif violations:
        print("OKRA handoff-contract violations:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation.code}: {violation.detail}", file=sys.stderr)
    else:
        print(f"ok: {path}")
    return 1 if violations else 0


def calibrate(root: Path) -> int:
    pass_files = markdown_files(root / "pass")
    fail_files = markdown_files(root / "fail")
    expected_fail_codes = {
        "auto-promoted-antigoal.md": "accumulated_antigoals",
        "auto-promoted-with-boundary-token.md": "accumulated_antigoals",
        "automatically-apply-antigoals.md": "accumulated_antigoals",
        "active-by-default-guardrails.md": "accumulated_antigoals",
        "applied-by-default-antigoals.md": "accumulated_antigoals",
        "human-only-ratification-antigoal.md": "accumulated_antigoals",
        "candidate-antigoal-loose-fields.md": "accumulated_antigoals",
        "candidate-antigoal-authority-drift-only.md": "accumulated_antigoals",
        "candidate-antigoal-type-stolen-from-worker.md": "accumulated_antigoals",
        "dkr-missing-risk-implications.md": "dkr_to_dkr_handoff",
        "dkr-decision-elsewhere-only.md": "dkr_to_dkr_handoff",
        "dkr-empty-risk-implications.md": "dkr_to_dkr_handoff",
        "dkr-placeholder-risk-implications.md": "dkr_to_dkr_handoff",
        "dkr-only-answered-questions.md": "dkr_to_dkr_handoff",
        "missing-prompt-packet.md": "worker_prompt_packet",
        "narrative-not-only.md": "in_progress_evidence_gate",
        "narrative-may-influence-next-prompt.md": "in_progress_evidence_gate",
        "narrative-informs-next-dispatch.md": "in_progress_evidence_gate",
        "narrative-is-used-as-context.md": "in_progress_evidence_gate",
        "narrative-passive-dispatch-influence.md": "in_progress_evidence_gate",
        "narrative-target-uses-context.md": "in_progress_evidence_gate",
        "narrative-should-inform.md": "in_progress_evidence_gate",
        "narrative-should-be-used-context.md": "in_progress_evidence_gate",
        "narrative-used-as-context.md": "in_progress_evidence_gate",
        "narrative-progress.md": "in_progress_evidence_gate",
        "pkr-absorbs-discovery.md": "pkr_discovery_handback",
        "pkr-absorbs-discovery-with-boilerplate.md": "pkr_discovery_handback",
        "pkr-may-omit-trace-fields.md": "ckr_pkr_traceability",
        "pkr-conditional-trace-fields.md": "ckr_pkr_traceability",
        "pkr-need-not-trace-fields.md": "ckr_pkr_traceability",
        "pkr-negated-trace-fields.md": "ckr_pkr_traceability",
        "pkr-optional-trace-fields.md": "ckr_pkr_traceability",
        "pkr-unrelated-reject-may-omit.md": "ckr_pkr_traceability",
        "pkr-do-not-require-trace-fields.md": "ckr_pkr_traceability",
        "pkr-research-unknowns-next-sentence.md": "pkr_discovery_handback",
        "pkr-unrelated-negation-research.md": "pkr_discovery_handback",
        "pkr-progression-workers-research.md": "pkr_discovery_handback",
        "pkr-research-before-anchor.md": "pkr_discovery_handback",
        "pkr-without-ckr-link.md": "ckr_pkr_traceability",
        "promoted-automatically-antigoal.md": "accumulated_antigoals",
        "reverse-auto-promoted-antigoal.md": "accumulated_antigoals",
        "reverse-may-promote-antigoals.md": "accumulated_antigoals",
        "singular-active-antigoal.md": "accumulated_antigoals",
        "worker-packet-frame-objective-only.md": "worker_prompt_packet",
        "worker-packet-action-envelope-assignment-only.md": "worker_prompt_packet",
        "worker-packet-action-envelope-global-only.md": "worker_prompt_packet",
        "worker-packet-does-not-require-frame-fields.md": "worker_prompt_packet",
        "worker-packet-need-not-include-frame-fields.md": "worker_prompt_packet",
        "worker-packet-fields-elsewhere.md": "worker_prompt_packet",
        "worker-packet-may-omit-frame-fields.md": "worker_prompt_packet",
        "worker-packet-negated-frame-fields.md": "worker_prompt_packet",
        "worker-packet-optional-frame-fields.md": "worker_prompt_packet",
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
            failures.append(f"{path}: expected at least one handoff-contract violation, got pass")
            continue
        expected_code = expected_fail_codes.get(path.name)
        if expected_code and expected_code not in {violation.code for violation in violations}:
            codes = ", ".join(violation.code for violation in violations)
            failures.append(f"{path}: expected violation {expected_code}, got: {codes}")

    rejection_sentence = (
        "In-progress worker narrative is not evidence; only worker progress, check-ins, metric reads, "
        "flags, or accepted checkpoints can influence the next dispatch."
    )
    if in_progress_evidence_gate(rejection_sentence) is not None:
        failures.append("probe: explicit narrative rejection should satisfy in-progress evidence gate")

    narrative_may_influence = (
        "Worker progress, check-ins, metric reads, flags, and accepted checkpoints influence the next "
        "dispatch. Freeform narrative is not evidence, but it may influence the next prompt as context."
    )
    if in_progress_evidence_gate(narrative_may_influence) is None:
        failures.append("probe: narrative permission should trip in-progress evidence violation")

    narrative_used_as_context = (
        "Worker progress, check-ins, metric reads, flags, and accepted checkpoints influence the next "
        "dispatch. Freeform narrative is not evidence, but it can be used as context for the next dispatch."
    )
    if in_progress_evidence_gate(narrative_used_as_context) is None:
        failures.append("probe: narrative-as-context permission should trip in-progress evidence violation")

    narrative_is_used_as_context = (
        "Worker progress, check-ins, metric reads, flags, and accepted checkpoints influence the next "
        "dispatch. Freeform narrative is not evidence, but it is used as context for the next dispatch."
    )
    if in_progress_evidence_gate(narrative_is_used_as_context) is None:
        failures.append("probe: declarative narrative-as-context permission should trip in-progress evidence violation")

    narrative_informs = (
        "Worker progress, check-ins, metric reads, flags, and accepted checkpoints influence the next "
        "dispatch. Freeform narrative is not evidence, but it informs the next dispatch as context."
    )
    if in_progress_evidence_gate(narrative_informs) is None:
        failures.append("probe: narrative-informs permission should trip in-progress evidence violation")

    passive_narrative = (
        "Freeform narrative is not evidence. However, the next dispatch may be influenced by "
        "freeform narrative as context. Worker progress, check-ins, metric reads, flags, and "
        "accepted checkpoints are still listed."
    )
    if in_progress_evidence_gate(passive_narrative) is None:
        failures.append("probe: passive narrative dispatch influence should trip violation")

    target_uses_narrative = (
        "Worker progress, check-ins, metric reads, flags, and accepted checkpoints influence the next "
        "dispatch. Freeform narrative is not evidence. The next prompt may use worker narrative as context."
    )
    if in_progress_evidence_gate(target_uses_narrative) is None:
        failures.append("probe: target-first narrative context use should trip violation")

    narrative_should_inform = (
        "Worker progress, check-ins, metric reads, flags, and accepted checkpoints influence the next "
        "dispatch. Freeform narrative is not evidence, but it should inform the next dispatch as context."
    )
    if in_progress_evidence_gate(narrative_should_inform) is None:
        failures.append("probe: should-inform narrative permission should trip violation")

    narrative_should_be_used = (
        "Worker progress, check-ins, metric reads, flags, and accepted checkpoints influence the next "
        "dispatch. Freeform narrative is not evidence, but it should be used as context for the next dispatch."
    )
    if in_progress_evidence_gate(narrative_should_be_used) is None:
        failures.append("probe: should-be-used narrative permission should trip violation")

    snake_case_packet = (
        "Worker Prompt Packet Contract. Every next DKR or PKR dispatch is a packet. Required fields: "
        "Frame fields include objective, anti_goals, metric_contracts, action_envelope, and frame_hash. "
        "Current state fields include current_state and current_round. Previous DKR checkpoint fields "
        "include source_dkr_checkpoint. Assignment fields include worker_kind, exact_task, "
        "allowed_actions, and forbidden_actions. Budget_and_stop_rule, hand_back_rule, and output schema "
        "write worker progress or a learning checkpoint."
    )
    if worker_prompt_packet(snake_case_packet) is not None:
        failures.append("probe: snake_case worker packet fields should satisfy packet contract")

    negated_packet_fields = (
        "Worker prompt packet required fields. Frame fields include objective only; anti-goals, "
        "action envelope, and human boundaries are not included in the packet. Current state fields "
        "include current_state, previous DKR checkpoint fields include source_dkr_checkpoint, "
        "assignment fields include worker_kind and exact_task, budget and stop rule, hand-back rule, "
        "and output schema."
    )
    if worker_prompt_packet(negated_packet_fields) is None:
        failures.append("probe: negated worker-packet frame fields should trip packet violation")

    optional_packet_fields = (
        "Worker prompt packet required fields. Frame fields include objective without anti-goals; "
        "action envelope and human boundaries are optional. Current state fields include current_state, "
        "previous DKR checkpoint fields include source_dkr_checkpoint, assignment fields include "
        "worker_kind and exact_task, budget and stop rule, hand-back rule, and output schema."
    )
    if worker_prompt_packet(optional_packet_fields) is None:
        failures.append("probe: optional worker-packet frame fields should trip packet violation")

    may_omit_packet_fields = (
        "Worker prompt packet required fields. Packets may omit anti_goals from the frame. "
        "Frame fields include objective, action_envelope, and human ratification. Current state fields "
        "include current_state, previous DKR checkpoint fields include source_dkr_checkpoint, "
        "assignment fields include worker_kind and exact_task, budget and stop rule, hand-back rule, "
        "and output schema."
    )
    if worker_prompt_packet(may_omit_packet_fields) is None:
        failures.append("probe: may-omit worker-packet frame fields should trip packet violation")

    not_optional_packet_fields = (
        "Worker prompt packet required fields. Frame fields include objective; anti_goals are not "
        "optional, action_envelope is required, and human ratification is required. Current state "
        "fields include current_state, previous DKR checkpoint fields include source_dkr_checkpoint, "
        "assignment fields include worker_kind and exact_task, budget and stop rule, hand-back rule, "
        "and output schema."
    )
    if worker_prompt_packet(not_optional_packet_fields) is not None:
        failures.append("probe: not-optional worker-packet frame fields should not trip omission violation")

    assignment_only_action_envelope = (
        "Worker Prompt Packet Contract. Every next DKR or PKR dispatch is a packet. Required fields: "
        "Frame fields include objective, anti_goals, metric_contracts, and frame_hash. Current state "
        "fields include current_state and current_round. Previous DKR checkpoint fields include "
        "source_dkr_checkpoint. Assignment fields include worker_kind, exact_task, allowed_actions, "
        "and forbidden_actions. Budget and stop rule, hand-back rule, and output schema are required."
    )
    if worker_prompt_packet(assignment_only_action_envelope) is None:
        failures.append("probe: assignment-only allowed_actions should not satisfy frame action envelope")

    global_only_action_envelope = (
        "Worker Prompt Packet Contract. Every next DKR or PKR dispatch is a packet. Required fields: "
        "Frame fields include objective, anti_goals, metric_contracts, and frame_hash. Current state "
        "fields include current_state and current_round. Previous DKR checkpoint fields include "
        "source_dkr_checkpoint. Assignment fields include worker_kind and exact_task. Budget and stop "
        "rule, hand-back rule, and output schema are required. Action envelope: allowed moves and "
        "forbidden moves are described later outside the frame fields."
    )
    if worker_prompt_packet(global_only_action_envelope) is None:
        failures.append("probe: global action envelope should not satisfy packet frame action envelope")

    reject_without_packet = (
        "Worker prompt packet required fields. Frame fields reject dispatch packets without anti_goals, "
        "action_envelope, or human boundaries; objective is always required. Current state fields "
        "include current_state, previous DKR checkpoint fields include source_dkr_checkpoint, "
        "assignment fields include worker_kind and exact_task, budget and stop rule, hand-back rule, "
        "and output schema."
    )
    if worker_prompt_packet(reject_without_packet) is not None:
        failures.append("probe: rejection-shaped packet without wording should not trip omission violation")

    packet_does_not_require = (
        "Worker prompt packet required fields. Frame fields include objective but do not require "
        "anti_goals, action_envelope, or human boundaries. Current state fields include current_state, "
        "previous DKR checkpoint fields include source_dkr_checkpoint, assignment fields include "
        "worker_kind and exact_task, budget and stop rule, hand-back rule, and output schema."
    )
    if worker_prompt_packet(packet_does_not_require) is None:
        failures.append("probe: do-not-require packet frame fields should trip omission violation")

    packet_need_not_include = (
        "Worker prompt packet required fields. anti_goals, action_envelope, and human boundaries "
        "need not be included. Current state fields include current_state, previous DKR checkpoint "
        "fields include source_dkr_checkpoint, assignment fields include worker_kind and exact_task, "
        "budget and stop rule, hand-back rule, and output schema."
    )
    if worker_prompt_packet(packet_need_not_include) is None:
        failures.append("probe: need-not-include packet frame fields should trip omission violation")

    bad_pkr = "PKR prompt: implement the feature and figure out whatever is missing."
    if pkr_discovery_handback(bad_pkr) is None:
        failures.append("probe: PKR absorbing discovery should trip hand-back violation")

    bad_pkr_with_boilerplate = (
        "PKR prompt: implement the feature and figure out whatever is missing. "
        "Elsewhere, PKRs hand back on unknown discovery."
    )
    if pkr_discovery_handback(bad_pkr_with_boilerplate) is None:
        failures.append("probe: PKR absorbing discovery should trip even with hand-back boilerplate")

    bad_pkr_next_sentence = (
        "PKR prompt: implement the checker. The progression worker may research unknowns and "
        "continue implementation. Elsewhere, PKRs hand back on unknown discovery."
    )
    if pkr_discovery_handback(bad_pkr_next_sentence) is None:
        failures.append("probe: PKR absorbing discovery should trip across a sentence break")

    negated_pkr_discovery = "PKRs must not research unknowns; they hand back on unknown discovery."
    if pkr_discovery_handback(negated_pkr_discovery) is not None:
        failures.append("probe: negated PKR discovery wording should not trip hand-back violation")

    unrelated_negation_pkr = (
        "PKR prompt: implement the feature, not the docs, and research unknowns as needed. "
        "Elsewhere, PKRs hand back on unknown discovery."
    )
    if pkr_discovery_handback(unrelated_negation_pkr) is None:
        failures.append("probe: unrelated negation should not hide PKR discovery absorption")

    progression_workers_research = (
        "Progression workers may research unknowns as needed in PKR prompts. Elsewhere, PKRs hand "
        "back on unknown discovery."
    )
    if pkr_discovery_handback(progression_workers_research) is None:
        failures.append("probe: progression-workers discovery wording should trip")

    pkr_research_before_anchor = (
        "Research unknowns as needed in PKR prompts. Elsewhere, PKRs hand back on unknown discovery."
    )
    if pkr_discovery_handback(pkr_research_before_anchor) is None:
        failures.append("probe: discovery verb before PKR anchor should trip")

    negated_pkr = "The PKR has a done check, but it does not carry linked_ckr, source_dkr_checkpoint, or contribution_metric."
    if ckr_pkr_traceability(negated_pkr) is None:
        failures.append("probe: negated PKR trace fields should trip traceability violation")

    need_not_pkr = "PKRs need not carry linked_ckr, source_dkr_checkpoint, or contribution_metric."
    if ckr_pkr_traceability(need_not_pkr) is None:
        failures.append("probe: PKR need-not trace fields should trip traceability violation")

    optional_pkr = "PKRs say linked_ckr, source_dkr_checkpoint, and contribution_metric are optional."
    if ckr_pkr_traceability(optional_pkr) is None:
        failures.append("probe: optional PKR trace fields should trip traceability violation")

    may_omit_pkr = "PKRs may omit linked_ckr, source_dkr_checkpoint, or contribution_metric."
    if ckr_pkr_traceability(may_omit_pkr) is None:
        failures.append("probe: may-omit PKR trace fields should trip traceability violation")

    conditional_pkr = (
        "PKRs carry linked_ckr, source_dkr_checkpoint, and contribution_metric only when available; "
        "otherwise they may omit them."
    )
    if ckr_pkr_traceability(conditional_pkr) is None:
        failures.append("probe: conditional PKR trace fields should trip traceability violation")

    reject_lacking_pkr = (
        "CKRs are measurable contribution context, not worker work, and never dispatched. "
        "Each PKR carries linked_ckr, source_dkr_checkpoint, contribution_metric, done check, "
        "changed paths, commands run, and progress signals for off-track work. "
        "Reject PKRs that lack linked_ckr, source_dkr_checkpoint, or contribution_metric."
    )
    if ckr_pkr_traceability(reject_lacking_pkr) is not None:
        failures.append("probe: rejection-shaped missing PKR link wording should not trip violation")

    unrelated_reject_pkr = (
        "Reject stale metrics. CKRs are measurable contribution context, not worker work, and never "
        "dispatched. PKRs may omit linked_ckr, source_dkr_checkpoint, or contribution_metric. They "
        "still have a done check, changed paths, commands run, and progress signals."
    )
    if ckr_pkr_traceability(unrelated_reject_pkr) is None:
        failures.append("probe: unrelated rejection sentence should not hide PKR trace omission")

    do_not_require_pkr = (
        "CKRs are measurable contribution context, not worker work, and never dispatched. "
        "PKRs do not require linked_ckr, source_dkr_checkpoint, or contribution_metric. They still "
        "have a done check, changed paths, commands run, and progress signals."
    )
    if ckr_pkr_traceability(do_not_require_pkr) is None:
        failures.append("probe: do-not-require PKR trace fields should trip")

    only_answered = (
        "Previous DKR learning checkpoint had a decision target, evidence refs, confidence update, "
        "answered questions, orchestrator checkpoint accepted, and next DKR scope derived from evidence."
    )
    if dkr_to_dkr_handoff(only_answered) is None:
        failures.append("probe: DKR handoff with answered-only questions should trip missing unanswered side")

    no_risk_implication = (
        "Previous DKR learning checkpoint had a decision target, evidence refs, confidence update, "
        "answered questions, unanswered questions, orchestrator checkpoint accepted, and next DKR "
        "scope derived from evidence."
    )
    if dkr_to_dkr_handoff(no_risk_implication) is None:
        failures.append("probe: DKR handoff without risk or anti-goal implications should trip violation")

    empty_risk_implication = (
        "Previous DKR learning checkpoint had a decision target, evidence refs, confidence update, "
        "answered questions, unanswered questions, risk or anti-goal implications: none recorded, "
        "orchestrator checkpoint accepted, and next DKR scope derived from evidence."
    )
    if dkr_to_dkr_handoff(empty_risk_implication) is None:
        failures.append("probe: DKR handoff with empty risk implications should trip violation")

    placeholder_risk_implication = (
        "Previous DKR learning checkpoint had a decision target, evidence refs, confidence update, "
        "answered questions, unanswered questions, risk or anti-goal implications: TBD, "
        "orchestrator decision accepted, and next DKR scope derived from evidence."
    )
    if dkr_to_dkr_handoff(placeholder_risk_implication) is None:
        failures.append("probe: DKR handoff with placeholder risk implications should trip violation")

    decision_elsewhere = (
        "Previous DKR learning checkpoint had a decision target, evidence refs, confidence update, "
        "answered questions, unanswered questions, risk or anti-goal implications, and next DKR "
        "scope derived from evidence. Elsewhere in worker packet prose, accepted checkpoint status "
        "is listed as a packet field."
    )
    if dkr_to_dkr_handoff(decision_elsewhere) is None:
        failures.append("probe: DKR decision missing from handoff section should trip violation")

    auto_with_boundary = (
        "Accumulated anti-goals from previous runs are automatically promoted into the next frame. "
        "The artifact elsewhere says unratified_memory_promotion_count == 0."
    )
    if accumulated_antigoals(auto_with_boundary) is None:
        failures.append("probe: auto-promotion should trip even when boundary token appears elsewhere")

    reverse_auto = (
        "Automatically promote previous-run anti-goals into the active frame. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(reverse_auto) is None:
        failures.append("probe: reverse-ordered auto-promotion should trip")

    singular_active = (
        "A previous-run anti-goal becomes active in the next frame by default. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(singular_active) is None:
        failures.append("probe: singular active anti-goal should trip")

    promoted_automatically = (
        "Prior-run anti-goals get promoted automatically into the active frame. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(promoted_automatically) is None:
        failures.append("probe: promoted-automatically anti-goal should trip")

    active_default_guardrail = (
        "Prior-run anti-goals are loaded as active guardrails for the next frame by default. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(active_default_guardrail) is None:
        failures.append("probe: active-by-default anti-goal guardrails should trip")

    applied_default_antigoal = (
        "Previous-run anti-goals are applied by default to the active frame. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(applied_default_antigoal) is None:
        failures.append("probe: applied-by-default anti-goals should trip")

    reverse_may_promote = (
        "The orchestrator may promote previous-run anti-goals automatically. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(reverse_may_promote) is None:
        failures.append("probe: may-promote reverse auto-promotion should trip")

    automatically_apply = (
        "Automatically apply previous-run anti-goals to the active frame. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(automatically_apply) is None:
        failures.append("probe: automatically-apply previous anti-goals should trip")

    ratified_activation = (
        "Previous-run anti-goals become active only after current evidence and human ratification. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire type, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(ratified_activation) is not None:
        failures.append("probe: ratified anti-goal activation should not trip auto-promotion violation")

    current_run_ratified_activation = (
        "Previous-run anti-goals become active only after current-run evidence and human ratification. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire type, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(current_run_ratified_activation) is not None:
        failures.append("probe: current-run evidence plus ratification should not trip auto-promotion violation")

    human_only_activation = (
        "Previous-run anti-goals become active after human ratification only. "
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire type, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification."
    )
    if accumulated_antigoals(human_only_activation) is None:
        failures.append("probe: human-only activation without current evidence should trip")

    reject_active_default = (
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire type, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification. Reject previous-run "
        "anti-goals that become active by default."
    )
    if accumulated_antigoals(reject_active_default) is not None:
        failures.append("probe: rejection-shaped active-by-default wording should not trip violation")

    negated_auto = (
        "candidate-anti-goals.v1.json includes metric_id, threshold, tripwire type, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, trace_manifest_ref, and human ratification. Previous-run "
        "anti-goals are not automatically promoted into the active frame."
    )
    if accumulated_antigoals(negated_auto) is not None:
        failures.append("probe: negated auto-promotion wording should not trip violation")

    loose_antigoal = (
        "candidate-anti-goals.v1.json contains metric_id and applies_when with candidate_status, "
        "human ratification, no_regression_evidence, trace_manifest_ref, and source refs."
    )
    if accumulated_antigoals(loose_antigoal) is None:
        failures.append("probe: candidate anti-goal library missing threshold/type/context fields should trip violation")

    authority_drift_only = (
        "candidate-anti-goals.v1.json includes metric_id, threshold, authority drift, applies_when, "
        "does_not_apply_when, invalidates_when, source refs, candidate_status, "
        "no_regression_evidence, and human ratification."
    )
    if accumulated_antigoals(authority_drift_only) is None:
        failures.append("probe: authority-drift prose should not satisfy candidate anti-goal type or trace evidence")

    if failures:
        print("okra handoff-contract calibration failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"okra handoff-contract calibration ok: {len(pass_files)} pass, {len(fail_files)} fail")
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
