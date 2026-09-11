"""python -m mod_manager.diagnostics.cli report --symptom <name>
python -m mod_manager.diagnostics.cli report --symptom <name> --apply
python -m mod_manager.diagnostics.cli list-symptoms
"""
from __future__ import annotations

import argparse
import sys

from ..core.resolver import apply as apply_resolution_policy
from .engine import diagnose
from .rules import Action
from .symptoms import Symptom


def _cmd_list_symptoms(_args: argparse.Namespace) -> int:
    for s in Symptom:
        print(f"{s.value:24s} {Symptom.describe(s)}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    try:
        symptom = Symptom(args.symptom)
    except ValueError:
        print(f"Unknown symptom '{args.symptom}'. Run 'list-symptoms' to see valid values.", file=sys.stderr)
        return 2

    result = diagnose(symptom)

    print(f"Symptom: {symptom.value} -- {Symptom.describe(symptom)}")
    print("Signals collected:")
    for s in result.signals_collected:
        print(f"  - {s}")
    print()

    if not result.findings:
        print("No known-pattern issues detected from current signals.")
        return 0

    for i, finding in enumerate(result.findings, 1):
        print(f"{i}. [{finding.confidence.value.upper()}] {finding.title}")
        for e in finding.evidence:
            print(f"     evidence: {e}")
        if finding.action == Action.APPLY_RESOLUTION_POLICY:
            print("     fix: covered by the current resolution policy (core/resolution_policy.py)")
        elif finding.manual_steps:
            print("     fix (manual):")
            for step in finding.manual_steps:
                print(f"       - {step}")
        print()

    if args.apply:
        applyable = [f for f in result.findings if f.action == Action.APPLY_RESOLUTION_POLICY]
        if not applyable:
            print("Nothing in this report is covered by --apply (all findings need manual action).")
            return 0
        print(f"--apply: running the resolution policy for {len(applyable)} finding(s) that it covers...")
        report = apply_resolution_policy(dry_run=False)
        for note in report.notes:
            print(f"  {note}")
    else:
        applyable = [f for f in result.findings if f.action == Action.APPLY_RESOLUTION_POLICY]
        if applyable:
            print(f"{len(applyable)} finding(s) above are covered by the resolution policy. Re-run with --apply to fix them.")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mod_manager.diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-symptoms").set_defaults(func=_cmd_list_symptoms)

    report_parser = sub.add_parser("report")
    report_parser.add_argument("--symptom", required=True, help="see list-symptoms")
    report_parser.add_argument(
        "--apply", action="store_true", help="Actually apply fixes covered by the resolution policy (default: report only)."
    )
    report_parser.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
