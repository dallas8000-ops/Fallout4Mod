"""python -m mod_manager.apply_load_order
python -m mod_manager.apply_load_order --apply

Direct, no-symptom-required entry point for resolver.apply(): sorts every
installed mod into the canonical, conflict-avoiding sequence
(core/catalog.py's ORDER_LOW_TO_HIGH) and runs the current conflict
resolution policy (file hides, ini settings, text patches -- see
core/resolution_policy.py). Existing per-mod priorities are never
disturbed -- only a mod this tool hasn't seen before gets assigned its
catalog position, and only that resequencing gets reported. Run it again
with nothing changed and it reports zero resequenced mods; the resolution
policy actions are independently idempotent (see actions.py).

This is deliberately separate from `diagnostics/cli.py`'s `report --apply`,
which only triggers the resolution policy as one possible fix for a
diagnosed symptom and requires you to name one first. Use THIS command for
routine, no-symptom-needed maintenance: after installing or removing a mod,
after a manual MO2 change, or on a schedule (see the weekly automation job,
which calls this as its sequencing step before running the test suite).
"""
from __future__ import annotations

import argparse

from .core.resolver import apply as resolver_apply


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mod_manager.apply_load_order")
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually write modlist.txt / mod_data.json and perform file "
            "hides, ini settings, and text patches (default: dry run, "
            "report only, nothing written)."
        ),
    )
    args = parser.parse_args(argv)

    report = resolver_apply(dry_run=not args.apply)

    prefix = "[DRY RUN] " if report.dry_run else ""
    print(f"{prefix}{report.installed_count} mod(s) scanned.")
    for note in report.notes:
        print(f"  {note}")

    if report.dry_run and report.installed_count:
        print("\nNo changes written. Re-run with --apply to write them.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
