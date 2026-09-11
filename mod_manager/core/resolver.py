"""Top-level orchestration: apply the canonical catalog order + the current
resolution policy to a live (or fixture) MO2 install. This is the single
replacement for apply_optimal_load_order.py's main(),
align_mods_compatibility.py's main(), and both fix_aaf_alignment*.py mains.

Nothing here mutates anything on import or at module scope. Call apply()
explicitly; it always takes a rotating backup first (see loadorder_io) and
returns a report of exactly what it did, so a caller can print it, log it,
or (for the diagnostics engine) show it to the user before deciding to
apply for real.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import actions, catalog, config, loadorder_io, mod_data_store, resolution_policy


@dataclass
class ApplyReport:
    dry_run: bool
    installed_count: int = 0
    modlist_backup: Path | None = None
    mod_data_changed: bool = False
    notes: list[str] = field(default_factory=list)

    def add(self, note: str) -> None:
        self.notes.append(note)


def compute_enabled_state(
    ordered: list[str], mod_data: dict, prior_state: dict[str, bool]
) -> dict[str, bool]:
    enabled: dict[str, bool] = {}
    for name in ordered:
        if name in prior_state:
            enabled[name] = prior_state[name]
        else:
            enabled[name] = bool(mod_data.get(name, {}).get("enabled", True))

    for older, newer in catalog.DISABLE_IF_PRESENT.items():
        if older in enabled and newer in enabled:
            enabled[older] = False
            enabled[newer] = True

    return enabled


def apply(
    *,
    dry_run: bool = True,
    mods_path: Path | None = None,
    modlist_path: Path | None = None,
    mod_data_path: Path | None = None,
) -> ApplyReport:
    """Apply canonical order + current resolution policy.

    dry_run=True (the default) computes and reports everything it WOULD do
    without writing anything. Pass dry_run=False to actually write. This
    default is deliberate: every legacy script mutated the live MO2 profile
    the instant you ran `python script.py`, with a backup as the only safety
    net (and, per loadorder_io's docstring, not even a reliable one).
    """
    mods_path = mods_path or config.MO2_MODS
    modlist_path = modlist_path or config.MO2_MODLIST
    mod_data_path = mod_data_path or config.MOD_DATA_PATH

    report = ApplyReport(dry_run=dry_run)

    installed = mod_data_store.scan_installed_mods(mods_path)
    report.installed_count = len(installed)
    if not installed:
        report.add(f"No mods found under {mods_path} -- nothing to do.")
        return report

    mod_data = mod_data_store.load(mod_data_path)
    mod_data, changed = mod_data_store.sync_with_installed(mod_data, installed)
    report.mod_data_changed = changed

    entries = catalog.build_catalog(installed)
    ordered = [e.name for e in entries]

    prior_state = loadorder_io.read_enabled_state(modlist_path)
    enabled = compute_enabled_state(ordered, mod_data, prior_state)

    for name, entry in zip(ordered, entries):
        mod_data.setdefault(name, {})
        mod_data[name]["category"] = entry.category
        mod_data[name]["tier"] = entry.tier
        mod_data[name]["priority"] = entry.order
        mod_data[name]["enabled"] = enabled.get(name, True)

    if dry_run:
        report.add(f"[dry-run] Would write {len(ordered)} mods to {modlist_path}")
        report.add(f"[dry-run] Would write mod_data to {mod_data_path}")
    else:
        report.modlist_backup = loadorder_io.write_modlist(ordered, mod_data, modlist_path=modlist_path)
        mod_data_store.save(mod_data, mod_data_path)
        report.add(f"Wrote {len(ordered)} mods to {modlist_path}")
        if report.modlist_backup:
            report.add(f"Backup: {report.modlist_backup}")

    # Resolution policy: file hides, text patches, ini settings.
    for hide in resolution_policy.all_file_hides():
        target = mods_path / hide.mod / Path(hide.relative_path)
        if dry_run:
            state = "already hidden" if actions.is_hidden(target) else (
                "would hide" if target.exists() else "missing"
            )
            report.add(f"[dry-run] {state}: {hide.mod}/{hide.relative_path}")
        else:
            report.add(actions.hide_file(target) + f" ({hide.reason})")

    for target in resolution_policy.ultimate_override_targets(mods_path):
        if dry_run:
            report.add(f"[dry-run] would hide: {target.name}")
        else:
            report.add(actions.hide_file(target) + f" ({resolution_policy.ULTIMATE_OVERRIDE_REASON})")

    for patch in resolution_policy.all_text_patches():
        target = mods_path / patch.mod / Path(patch.relative_path)
        if dry_run:
            present = target.exists() and patch.remove_substring in target.read_text(
                encoding="utf-8", errors="replace"
            ) if target.exists() else False
            report.add(f"[dry-run] {'would patch' if present else 'no change needed'}: {patch.relative_path}")
        else:
            report.add(actions.strip_substring_in_file(target, patch.remove_substring) + f" ({patch.reason})")

    for setting in resolution_policy.all_ini_settings():
        target = mods_path / setting.mod / Path(setting.relative_path)
        if dry_run:
            report.add(f"[dry-run] would ensure {setting.key}={setting.value} in {setting.relative_path}")
        else:
            report.add(actions.set_key_in_ini(target, setting.key, setting.value) + f" ({setting.reason})")

    return report
