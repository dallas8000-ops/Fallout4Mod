"""One-time migration: reconcile the two divergent mod_data.json files into
the single canonical store, archive the five legacy scripts, and flag any
".disabled" files the old fix_aaf_alignment*.py scripts left behind that
this project's tooling can no longer see (see core/actions.py's docstring).

Dry-run by default -- prints exactly what it would do and why. Pass
--apply to actually write. Always takes a timestamped backup of both source
files before touching anything.

Usage:
    python migrate_legacy.py            # report only, writes nothing
    python migrate_legacy.py --apply    # perform the migration
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from mod_manager.core import catalog, config  # noqa: E402

ROOT_MOD_DATA = PROJECT_ROOT / "mod_data.json"  # the stale, flat copy
CANONICAL_MOD_DATA = config.MOD_DATA_PATH  # mod_manager/mod_data.json

LEGACY_SCRIPTS = [
    "check_mod_conflicts.py",
    "align_mods_compatibility.py",
    "apply_optimal_load_order.py",
    "set_mod_priorities.py",
    "fix_aaf_alignment.py",
    "fix_aaf_alignment_v2.py",
]

LEGACY_README = """\
# Legacy scripts (archived {date})

These six scripts are superseded by `mod_manager/core/` and
`mod_manager/diagnostics/`. They are kept here for reference, not deleted,
because two of them (`fix_aaf_alignment.py`, `fix_aaf_alignment_v2.py`)
contain the diagnostic reasoning (the offset="0,50,180" root cause) that
`core/resolution_policy.py` now encodes as data instead of a script.

Do not run these against a live MO2 install anymore -- they read/wrote
mod_data.json at inconsistent paths (see MIGRATION_NOTES.md) and three of
them define contradictory enable/disable sets for the same mods. Running
one after another was the actual cause of the recurring "fixed it, then it
broke again" cycle.

| Script | Superseded by |
|---|---|
| check_mod_conflicts.py | `python -m mod_manager.diagnostics.cli report --symptom <x>` |
| apply_optimal_load_order.py | `mod_manager.core.resolver.apply()` (canonical order) |
| align_mods_compatibility.py | `mod_manager.core.resolution_policy` (adopted as canonical) |
| fix_aaf_alignment.py | superseded by align_mods_compatibility's approach, then by resolution_policy |
| fix_aaf_alignment_v2.py | root-cause diagnosis preserved in `resolution_policy.py`'s docstring |
| set_mod_priorities.py | `mod_manager.core.catalog.ORDER_LOW_TO_HIGH` (single canonical order) |
"""


def _load_json_tolerant(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text) if text.strip() else {}


def find_orphaned_disabled_files(mods_path: Path) -> list[Path]:
    if not mods_path.exists():
        return []
    return sorted(mods_path.rglob("*.disabled"))


def build_report(apply_mode: bool) -> tuple[dict, list[str]]:
    notes: list[str] = []

    root_data = _load_json_tolerant(ROOT_MOD_DATA)
    canonical_data = _load_json_tolerant(CANONICAL_MOD_DATA)

    notes.append(f"Root copy:      {ROOT_MOD_DATA} ({len(root_data)} entries)")
    notes.append(f"Canonical copy: {CANONICAL_MOD_DATA} ({len(canonical_data)} entries)")

    flat_root = all(
        e.get("category") in (None, "Uncategorized") and e.get("priority") == 100 for e in root_data.values()
    ) and bool(root_data)
    if flat_root:
        notes.append(
            "Root copy is FLAT (every entry priority=100, category=Uncategorized) -- "
            "it reflects main.py's default-on-first-scan values, not any of the tiered "
            "ordering work. Canonical copy wins for every key present in both."
        )

    merged: dict = dict(canonical_data)  # canonical wins on conflict
    only_in_root = [k for k in root_data if k not in canonical_data]
    for key in only_in_root:
        notes.append(f"Key only in root copy, adopting into canonical: {key}")
        merged[key] = root_data[key]

    installed = set()
    if config.MO2_MODS.exists():
        installed = {p.name for p in config.MO2_MODS.iterdir() if p.is_dir()}
        notes.append(f"Live MO2 mods folder: {len(installed)} mods found at {config.MO2_MODS}")
    else:
        notes.append(f"MO2 mods folder not found at {config.MO2_MODS} -- skipping install-state sync.")

    if installed:
        for name in installed:
            if name not in merged:
                category, tier = catalog.get_category_and_tier(name)
                merged[name] = {
                    "category": category,
                    "priority": catalog.order_index(name),
                    "enabled": True,
                    "tier": tier,
                }
                notes.append(f"New mod not in either file, added with catalog defaults: {name}")

        for name in list(merged.keys()):
            if name not in installed:
                notes.append(f"'{name}' is in mod_data but not currently installed -- left in place (not deleted).")

    orphaned = find_orphaned_disabled_files(config.MO2_MODS)
    if orphaned:
        notes.append(
            f"{len(orphaned)} '.disabled' file(s) found -- these were hidden by the old "
            "fix_aaf_alignment*.py scripts using a suffix MO2's UI and this project's "
            "actions.py do not recognize. They still work (excluded from MO2's virtual "
            "filesystem), but nothing can un-hide them automatically anymore:"
        )
        for p in orphaned:
            notes.append(f"    {p}")
        notes.append(
            "    -> Leave them as-is unless you specifically need to restore one of these "
            "files; rename .disabled back to the original name by hand if so."
        )

    return merged, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes. Without this flag, report only.")
    args = parser.parse_args()

    merged, notes = build_report(apply_mode=args.apply)

    print("=== Migration report ===")
    for n in notes:
        print(f"- {n}")
    print()

    if not args.apply:
        print(f"Dry run only. {len(merged)} entries would be written to {CANONICAL_MOD_DATA}.")
        print("Re-run with --apply to write, archive legacy scripts, and back up both source files.")
        return 0

    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if ROOT_MOD_DATA.exists():
        shutil.copy2(ROOT_MOD_DATA, config.BACKUP_DIR / f"mod_data.json.root.{stamp}.bak")
    if CANONICAL_MOD_DATA.exists():
        shutil.copy2(CANONICAL_MOD_DATA, config.BACKUP_DIR / f"mod_data.json.canonical.{stamp}.bak")

    from mod_manager.core import mod_data_store

    mod_data_store.save(merged, CANONICAL_MOD_DATA)
    print(f"Wrote {len(merged)} entries to {CANONICAL_MOD_DATA}")

    if ROOT_MOD_DATA.exists():
        legacy_dir = PROJECT_ROOT / "legacy"
        legacy_dir.mkdir(exist_ok=True)
        dest = legacy_dir / "mod_data.json.root_copy_pre_migration"
        shutil.move(str(ROOT_MOD_DATA), str(dest))
        print(f"Moved stale root mod_data.json to {dest}")

    legacy_dir = PROJECT_ROOT / "legacy"
    legacy_dir.mkdir(exist_ok=True)
    for script in LEGACY_SCRIPTS:
        src = PROJECT_ROOT / script
        if src.exists():
            shutil.move(str(src), str(legacy_dir / script))
            print(f"Archived {script} -> legacy/{script}")
    (legacy_dir / "README.md").write_text(
        LEGACY_README.format(date=_dt.date.today().isoformat()), encoding="utf-8"
    )

    print("\nMigration complete. Verify with:")
    print("  python -m mod_manager.diagnostics.cli report --symptom animation_misalign")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
