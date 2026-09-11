"""Small, typed vocabulary of file-level mutations the resolver and the
diagnostics engine are allowed to perform. Every fix_aaf_alignment*.py /
align_mods_compatibility.py script reimplemented hide_file() and the
INI key-patcher separately, with subtly different idempotency behavior
(v1's hide_file renames .disabled, align's renames .mohidden -- picking
the WRONG one for a given mod means MO2 either does or doesn't recognize
the file as hidden). This module is the one place those operations live.

Every mutating function here is idempotent (safe to call twice) and
returns a human-readable note of what it did, never raises on "nothing to
do", and standardizes on MO2's own ".mohidden" hide convention -- the
suffix MO2's file-tree UI specifically recognizes and offers to restore.
fix_aaf_alignment.py / fix_aaf_alignment_v2.py instead renamed to
".disabled": that still excludes the file from MO2's virtual filesystem
(any rename away from the original name does), but MO2's own "unhide"
button won't find it, and neither will this module's is_hidden()/
unhide_file() -- they only look for ".mohidden". A file this project
hid via the old suffix is effectively orphaned: still working, but
untracked by anything going forward. migrate_legacy.py scans for and
flags any ".disabled" files left over from those two scripts.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

MOHIDDEN_SUFFIX = ".mohidden"


def hide_file(path: Path) -> str:
    """Rename path -> path.mohidden. Idempotent."""
    hidden = path.with_name(path.name + MOHIDDEN_SUFFIX)
    if hidden.exists():
        return f"already hidden: {path.name}"
    if not path.exists():
        return f"missing (nothing to hide): {path.name}"
    path.rename(hidden)
    return f"hid: {path.name}"


def unhide_file(path: Path) -> str:
    """Rename path.mohidden -> path. Idempotent."""
    hidden = path.with_name(path.name + MOHIDDEN_SUFFIX)
    if path.exists():
        return f"already visible: {path.name}"
    if not hidden.exists():
        return f"missing (nothing to unhide): {path.name}"
    hidden.rename(path)
    return f"unhid: {path.name}"


def is_hidden(path: Path) -> bool:
    return path.with_name(path.name + MOHIDDEN_SUFFIX).exists()


def set_key_in_ini(path: Path, key: str, value: str, *, backup: bool = True) -> str:
    """Set `key = value` on the first line matching that key, preserving
    everything else in the file. No-ops (returns a note) if the file is
    missing or the key doesn't exist -- never invents a new key, since an
    invented key an engine doesn't recognize is a silent no-op *in-game*
    that this tool would otherwise report as "fixed".
    """
    if not path.exists():
        return f"missing ini: {path.name}"
    raw = path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.M)
    if not pattern.search(raw):
        return f"key '{key}' not found in {path.name} (left unchanged)"

    new = pattern.sub(rf"\g<1>{value}", raw, count=1)
    if new == raw:
        return f"{key} already {value} in {path.name}"

    if backup:
        bak = path.with_suffix(path.suffix + ".bak_before_patch")
        if not bak.exists():
            shutil.copy2(path, bak)

    path.write_text(new, encoding="utf-8")
    return f"set {key}={value} in {path.name}"


def strip_substring_in_file(
    path: Path, needle: str, *, backup: bool = True
) -> str:
    """Remove all occurrences of `needle` from a text file. Used for the
    diagnosed SquirtCum offset="0,50,180" 180-degree-yaw bug.
    """
    if not path.exists():
        return f"missing: {path.name}"
    raw = path.read_text(encoding="utf-8", errors="replace")
    if needle not in raw:
        return f"'{needle}' not present in {path.name} (already clean or N/A)"

    if backup:
        bak = path.with_suffix(path.suffix + ".bak_before_patch")
        if not bak.exists():
            shutil.copy2(path, bak)

    new = raw.replace(needle, "")
    path.write_text(new, encoding="utf-8")
    return f"removed {needle!r} from {path.name}"
