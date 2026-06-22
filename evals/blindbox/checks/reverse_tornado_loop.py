#!/usr/bin/env python3
"""Black-box structural checks for a Reverse Tornado loop artifact."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None


CHECKS = {
    "objective has a measured target": (
        r"objective[\s\S]{0,900}(metric|activation|rate|revenue|sales|users|tickets)"
        r"[\s\S]{0,900}(\d[\d,]*(?:\.\d+)?\s*(?:%|percent|users?|sales|revenue|tickets?|per|rate)?|\$[\d,]+)"
    ),
    "anti-goal has metric, threshold, and type": (
        r"anti-goal[\s\S]{0,1200}(metric|anti-metric|rate|support ticket|tickets per)"
        r"[\s\S]{0,1200}"
        r"(threshold|<=|>=|under|over|at or below|at or above)[\s\S]{0,500}"
        r"(\d[\d,]*(?:\.\d+)?|\$[\d,]+)[\s\S]{0,1200}"
        r"(drift|tripwire)"
    ),
    "frame ratification is explicit": r"(candidate frame|human[- ]ratified|ratified frame|human approval|approver)",
    "action authority envelope is explicit": (
        r"(action envelope|allowed move|forbidden action|approval gate|spend cap|blast[- ]radius|data boundar|rollback)"
    ),
    "human-owned frame is explicit": r"(human-owned|human owns|human-only|goal-switching is human-only)",
    "no-cascade direct metric rule is explicit": r"(no-cascade|scaffolding, not scoreboard|direct metric)",
    "DKR discovery unit is present": r"\bDKR\b[\s\S]{0,900}(discovery|probe|budget|learning)",
    "CKR contribution unit is measurable": r"\bCKR\b[\s\S]{0,900}(metric|measurable|target)",
    "PKR progression unit reaches tasks": r"\bPKR\b[\s\S]{0,900}(task|progression|do-and-check|execution)",
    "admissibility eval is before action": r"admissibility[\s\S]{0,900}(before|pre[- ]?dispatch|veto|admit)",
    "direct read eval is after action": r"direct read[\s\S]{0,900}(after|actual|source|anti-metric)",
    "paired goal eval checks both sides": (
        r"paired[\s\S]{0,1200}(objective|goal|activation|target)"
        r"[\s\S]{0,1200}(anti-goal|support|tickets|threshold|held|wall)"
    ),
    "metric freshness contract is present": (
        r"(freshness|metric contract|source of truth|stale)[\s\S]{0,1500}"
        r"(observed_at|observed at|as_of|as of|recorded_at|recorded at|max[_ -]?age|max age|stale)"
    ),
    "heartbeat cadence and next check are present": (
        r"(heartbeat|cadence|ritual|turn[- ]based|time[- ]based|weekly|daily)[\s\S]{0,1500}"
        r"(next[_ -]?check|next check|next_check_at|check_at|idle heartbeat)"
    ),
    "metric lag or measurement window is present": (
        r"(lag rule|lag window|measurement window|impact window|waiting_for_measurement|waiting for measurement)"
    ),
    "flag lifecycle is operational": (
        r"(open|acknowledged|resolved|waived)[\s\S]{0,1500}"
        r"(owner|deadline|requires_human_by|blocking|pause|status)"
    ),
    "storage and idempotency are included": (
        r"(idempotency|idempotent|stable key|resume|ledger|frame_version|frame version)"
        r"[\s\S]{0,1200}(frame|ledger|result|flag|key)"
    ),
    "cannot flag is defined": r"\b(cannot|can't)\b[\s\S]{0,500}(budget|flatline|learning|nothing back)",
    "breaking flag is defined": r"\bbreaking\b[\s\S]{0,700}(drift|trip|anti|wall|worse|support|ticket|threshold|breach)",
    "pointless flag is defined": r"\bpointless\b[\s\S]{0,700}(objective|metric|budge|flat|wrong tip)",
    "authority drift flag is defined": r"(authority[_ -]?drift|authority breach|outside.*action envelope|bypass approval)",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Markdown loop artifact to check")
    args = parser.parse_args()

    if not args.path.exists():
        print(f"missing file: {args.path}", file=sys.stderr)
        return 2

    text = args.path.read_text(encoding="utf-8", errors="replace")
    missing = [name for name, pattern in CHECKS.items() if not has(pattern, text)]
    if missing:
        print("missing or weak loop parts:", file=sys.stderr)
        for name in missing:
            print(f"- {name}", file=sys.stderr)
        return 1

    print(f"ok: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
