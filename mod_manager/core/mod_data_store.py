"""The ONE load/save path for mod_data.json.

Replaces four independent copies of this logic (main.py, mod_manager_gui.py,
server.py, and the ad-hoc load_json()/write_text() calls scattered through
apply_optimal_load_order.py, align_mods_compatibility.py, and both
fix_aaf_alignment*.py). Every one of those had a slightly different bug:
main.py/mod_manager_gui.py never read utf-8-sig (a BOM in the file would
raise), server.py silently drops mods no longer in the mods folder on
*every* GET request (fine for the web UI, catastrophic if another process
calls it mid-edit), and none of them wrote atomically -- a crash or Ctrl-C
mid-json.dump() leaves a truncated, unparseable mod_data.json with no
recovery path.

This module fixes all three: atomic write (write to temp file, fsync,
os.replace), utf-8-sig tolerant read, and syncing installed/removed mods is
an explicit method the caller opts into rather than a side effect of every
read.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TypedDict

from . import config


class ModEntry(TypedDict, total=False):
    category: str
    priority: int
    enabled: bool
    tier: int
    # "catalog" (default for anything auto-seeded) means resolver.apply()
    # and server.py's /mods GET are free to keep this mod's priority in
    # sync with catalog.py's current order on every run. "manual" is set
    # the instant a human sets priority through the web UI (PUT
    # /mods/<name>) or main.py's CLI, and is permanent protection from
    # ever being overwritten again. An entry with no priority_source key at
    # all predates this field -- treated as "catalog" (see resolver.py's
    # docstring for why that's the correct default, not just the
    # convenient one).
    priority_source: str


ModData = dict[str, ModEntry]


def load(path: Path | None = None) -> ModData:
    path = path or config.MOD_DATA_PATH
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object at the top level")
    return data


def save(data: ModData, path: Path | None = None) -> None:
    """Atomic write: never leaves a truncated file on disk."""
    path = path or config.MOD_DATA_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".mod_data.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def scan_installed_mods(mods_path: Path | None = None) -> set[str]:
    mods_path = mods_path or config.MO2_MODS
    if not mods_path.exists():
        return set()
    return {p.name for p in mods_path.iterdir() if p.is_dir()}


def sync_with_installed(
    data: ModData, installed: set[str], *, drop_missing: bool = True
) -> tuple[ModData, bool]:
    """Add newly-installed mods with catalog defaults; optionally drop mods
    no longer physically present. Returns (data, changed).

    drop_missing=True reproduces server.py's existing behavior (stale mods
    vanish from mod_data.json on the next scan). Set it False when you want
    to keep history for a mod you've temporarily removed -- the legacy
    scripts gave you no choice here at all.
    """
    from . import catalog

    changed = False
    for name in installed:
        if name not in data:
            category, tier = catalog.get_category_and_tier(name)
            data[name] = {
                "category": category,
                "priority": catalog.order_index(name),
                "enabled": config.DEFAULT_ENABLED,
                "tier": tier,
                "priority_source": "catalog",
            }
            changed = True
        else:
            entry = data[name]
            if "enabled" not in entry:
                entry["enabled"] = config.DEFAULT_ENABLED
                changed = True

    if drop_missing:
        for name in list(data.keys()):
            if name not in installed:
                del data[name]
                changed = True

    return data, changed
