#!/usr/bin/env python3
"""okra verify-artifact -- PUBLIC completeness checker for OKRA artifacts.

This is the product's own definition-of-done gate, used by an agent in a
produce -> verify -> repair loop before it finishes. It checks presence and
structure of the sections/fields documented in the skill's PUBLIC contract
(contracts/<artifact>.v1.json). It is deliberately NOT the hidden eval rubric:
it imports nothing from evals/blindbox/checks, encodes no regex-adjacency or
scoring rules, and every requirement cites a public source. The hidden eval
checkers stay independent and grade honest application.

Usage:
  okra-verify-artifact.py <artifact.md> [--contract <contract.json>] [--json]

Exit code 0 when complete; 1 when required elements are missing; 2 on usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONTRACT = SCRIPT_DIR.parent / "contracts" / "handoff-contract.v1.json"


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace so multi-word tokens tolerate wrapping."""
    return re.sub(r"\s+", " ", text.lower())


def token_present(haystack: str, token: str) -> bool:
    return normalize(token) in haystack


def group_passes(haystack: str, group: dict) -> tuple[bool, list[str]]:
    mode = group.get("mode", "all")
    tokens = group.get("tokens", [])
    present = [t for t in tokens if token_present(haystack, t)]
    if mode == "any":
        return (len(present) > 0, present)
    return (len(present) == len(tokens), present)


def evaluate(artifact_text: str, contract: dict) -> dict:
    haystack = normalize(artifact_text)
    missing = []
    satisfied = []
    for req in contract.get("requirements", []):
        groups = req.get("groups", [])
        failed_groups = []
        for g in groups:
            ok, _present = group_passes(haystack, g)
            if not ok:
                failed_groups.append({
                    "mode": g.get("mode", "all"),
                    "needed": g.get("tokens", []),
                })
        if failed_groups:
            missing.append({
                "id": req.get("id"),
                "description": req.get("description"),
                "hint": req.get("hint"),
                "source": req.get("source"),
                "unsatisfied_groups": failed_groups,
            })
        else:
            satisfied.append(req.get("id"))
    return {
        "artifact_contract": contract.get("contract_version"),
        "complete": len(missing) == 0,
        "satisfied_count": len(satisfied),
        "required_count": len(contract.get("requirements", [])),
        "satisfied": satisfied,
        "missing": missing,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="okra verify-artifact", description=__doc__)
    parser.add_argument("artifact", help="path to the artifact markdown file")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT),
                        help="path to the PUBLIC contract json (default: handoff-contract.v1.json)")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args(argv)

    artifact_path = Path(args.artifact)
    contract_path = Path(args.contract)
    if not artifact_path.is_file():
        print(f"artifact not found: {artifact_path}", file=sys.stderr)
        return 2
    if not contract_path.is_file():
        print(f"contract not found: {contract_path}", file=sys.stderr)
        return 2

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    report = evaluate(artifact_path.read_text(encoding="utf-8"), contract)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if report["complete"]:
            print(f"OKRA artifact complete: {report['satisfied_count']}/{report['required_count']} "
                  f"requirements satisfied against {report['artifact_contract']}.")
        else:
            print(f"OKRA artifact INCOMPLETE: {report['satisfied_count']}/{report['required_count']} "
                  f"satisfied against {report['artifact_contract']}. Fill these before finishing:")
            for m in report["missing"]:
                print(f"  - [{m['id']}] {m['hint']}")
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
