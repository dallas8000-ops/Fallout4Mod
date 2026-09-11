# Fallout4Mod

Load-order tooling for a Mod Organizer 2 Fallout 4 profile, plus a
deterministic diagnostics engine that turns a symptom into ranked,
evidence-backed findings (and, where the fix is already policy, an
`--apply` that performs it). See `mod_manager/README.md` for day-to-day
usage and `MIGRATION_NOTES.md` for why the project is structured the way
it is and what changed from the original per-script tools.

The top-level `*.py` scripts (`align_mods_compatibility.py`,
`apply_optimal_load_order.py`, `fix_aaf_alignment*.py`,
`check_mod_conflicts.py`, `set_mod_priorities.py`) are the original,
pre-refactor tools -- superseded by `mod_manager/core/` and
`mod_manager/diagnostics/`, kept here for reference until
`migrate_legacy.py --apply` archives them (see `MIGRATION_NOTES.md`).
