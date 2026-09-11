"""Signal collectors: pure functions that read real on-disk state and
return facts. No interpretation happens here -- that's rules.py's job.
Every function takes explicit paths (defaulting to core.config) so tests
can point them at a fixture directory instead of the real MO2 install.

No Buffout 4 crash-log parsing lives here. An earlier version of this file
had a regex-based crash-log scanner; it was removed after checking prior
art and finding CLASSIC (github.com/GuidanceOfGrace/CLASSIC-Fallout4,
6,300+ endorsements, native-compiled, actively maintained) already does
that job properly -- ~250 checks against a real known-issue database,
versus two regexes pulling text out of "PROBABLE CALL STACK". Re-deriving
a worse version of an actively maintained community tool was a mistake,
not a design decision; see rules.py's CTD findings for the pointer to it
instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core import catalog, config, loadorder_io, resolution_policy
from . import esp_parser


# ---------------------------------------------------------------------------
# Plugin activation + master-file dependency signals
# ---------------------------------------------------------------------------
@dataclass
class PluginSignal:
    name: str
    active: bool
    source_mod: str | None
    masters: list[str] = field(default_factory=list)
    missing_masters: list[str] = field(default_factory=list)
    inactive_masters: list[str] = field(default_factory=list)
    is_light: bool = False
    parse_error: str | None = None


def map_plugin_sources(mods_path: Path | None = None) -> dict[str, str]:
    """plugin filename -> owning mod folder name."""
    mods_path = mods_path or config.MO2_MODS
    sources: dict[str, str] = {}
    if not mods_path.exists():
        return sources
    for mod_dir in mods_path.iterdir():
        if not mod_dir.is_dir():
            continue
        for ext in ("*.esp", "*.esm", "*.esl"):
            for plugin_file in mod_dir.rglob(ext):
                sources.setdefault(plugin_file.name, mod_dir.name)
    return sources


def collect_plugin_signals(
    mods_path: Path | None = None, plugins_path: Path | None = None
) -> list[PluginSignal]:
    mods_path = mods_path or config.MO2_MODS
    plugins_path = plugins_path or config.MO2_PLUGINS

    plugins = loadorder_io.read_plugins(plugins_path)
    if not plugins:
        return []

    sources = map_plugin_sources(mods_path)
    active_names = {name for name, active in plugins if active}
    all_names = {name for name, _ in plugins}

    out: list[PluginSignal] = []
    for name, active in plugins:
        source_mod = sources.get(name)
        masters: list[str] = []
        missing_masters: list[str] = []
        inactive_masters: list[str] = []
        is_light = False
        parse_error = None

        if source_mod:
            plugin_path = mods_path / source_mod / name
            header = esp_parser.parse_header(plugin_path)
            parse_error = header.error
            is_light = header.is_light
            masters = header.masters
            for m in masters:
                if m not in all_names:
                    missing_masters.append(m)
                elif m not in active_names:
                    inactive_masters.append(m)

        out.append(
            PluginSignal(
                name=name,
                active=active,
                source_mod=source_mod,
                masters=masters,
                missing_masters=missing_masters,
                inactive_masters=inactive_masters,
                is_light=is_light,
                parse_error=parse_error,
            )
        )
    return out


# ---------------------------------------------------------------------------
# File-conflict winner: given a relative path, which enabled mod (by
# modlist.txt conflict priority, top of file wins) actually provides it.
# ---------------------------------------------------------------------------
def file_conflict_winner(
    relative_path: str, mods_path: Path | None = None, modlist_path: Path | None = None
) -> str | None:
    mods_path = mods_path or config.MO2_MODS
    modlist_path = modlist_path or config.MO2_MODLIST
    if not modlist_path.exists():
        return None
    for line in modlist_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("+"):
            continue
        name = line[1:]
        candidate = mods_path / name / Path(relative_path)
        if candidate.exists():
            return name
    return None


# ---------------------------------------------------------------------------
# Resolution-policy state: is the current AAF fix actually applied right now?
# ---------------------------------------------------------------------------
@dataclass
class ResolutionPolicyState:
    skeleton_hides_applied: dict[str, bool] = field(default_factory=dict)
    ultimate_override_hidden: bool | None = None  # None = mod not installed
    squirtcum_offset_present: dict[str, bool] = field(default_factory=dict)
    ini_settings_correct: dict[str, bool] = field(default_factory=dict)


def collect_resolution_policy_state(mods_path: Path | None = None) -> ResolutionPolicyState:
    mods_path = mods_path or config.MO2_MODS
    from ..core import actions

    state = ResolutionPolicyState()

    for hide in resolution_policy.all_file_hides():
        target = mods_path / hide.mod / Path(hide.relative_path)
        key = f"{hide.mod}/{hide.relative_path}"
        if not (mods_path / hide.mod).exists():
            continue
        state.skeleton_hides_applied[key] = actions.is_hidden(target) or not target.exists()

    uap = mods_path / "Ultimate AAF Patch"
    if uap.exists():
        targets = resolution_policy.ultimate_override_targets(mods_path)
        # If glob found files, they're NOT hidden yet (hidden ones end in
        # .mohidden and the glob pattern doesn't match that suffix).
        state.ultimate_override_hidden = len(targets) == 0

    for patch in resolution_policy.all_text_patches():
        target = mods_path / patch.mod / Path(patch.relative_path)
        key = f"{patch.mod}/{patch.relative_path}"
        if target.exists():
            text = target.read_text(encoding="utf-8", errors="replace")
            state.squirtcum_offset_present[key] = patch.remove_substring in text

    for setting in resolution_policy.all_ini_settings():
        target = mods_path / setting.mod / Path(setting.relative_path)
        key = f"{setting.mod}/{setting.relative_path}#{setting.key}"
        if target.exists():
            text = target.read_text(encoding="utf-8", errors="replace")
            pattern = re.compile(
                rf"^\s*{re.escape(setting.key)}\s*=\s*{re.escape(setting.value)}\s*$", re.M | re.I
            )
            state.ini_settings_correct[key] = bool(pattern.search(text))

    return state


# ---------------------------------------------------------------------------
# Duplicate / known-conflict-pair signals
# ---------------------------------------------------------------------------
def duplicate_pairs_both_enabled(mod_data: dict) -> list[tuple[str, str]]:
    out = []
    for older, newer in catalog.DISABLE_IF_PRESENT.items():
        if older in mod_data and newer in mod_data:
            if mod_data[older].get("enabled", True) and mod_data[newer].get("enabled", True):
                out.append((older, newer))
    return out


# ---------------------------------------------------------------------------
# AAF content integrity: is xmlutility rejecting/losing registered XML?
#
# Grounded in a real, confirmed-on-hardware bug (2026-09-08): AAF's
# xmlutility.dll registers per-mod XML content packs under each mod's AAF/
# subfolder. A 0-byte file there is dagobaking's (AAF's own author) own
# documented signature of exactly two distinct causes, both checked here
# directly off disk rather than by parsing xmlutility.log:
#   1. UseSignatures=true rejecting unsigned third-party content outright.
#   2. A higher-MO2-priority mod's copy of the same relative path silently
#      shadowing the real one (see find_aaf_multi_owner_files below).
# ---------------------------------------------------------------------------
@dataclass
class AAFIntegritySignal:
    zero_byte_xml_files: list[str] = field(default_factory=list)  # "ModName/AAF/File.xml"
    use_signatures_enabled: bool | None = None  # None = xmlutility.ini not found/no such key
    schema_missing: bool = False


def collect_aaf_integrity(mods_path: Path | None = None) -> AAFIntegritySignal:
    mods_path = mods_path or config.MO2_MODS
    sig = AAFIntegritySignal()

    aaf_mod = mods_path / "Advanced Animation Framework"
    if aaf_mod.exists():
        xmlutility_ini = aaf_mod / "xmlutility.ini"
        if xmlutility_ini.exists():
            text = xmlutility_ini.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"^\s*UseSignatures\s*=\s*(\S+)\s*$", text, re.M | re.I)
            if match:
                sig.use_signatures_enabled = match.group(1).strip().lower() == "true"
        # Exact expected location isn't confirmed against the real install --
        # xmlutility.ini lives at the mod root, but aaf.xsd's folder wasn't
        # verified. Check both plausible spots rather than assert one.
        schema_candidates = [aaf_mod / "aaf.xsd", aaf_mod / "AAF" / "aaf.xsd"]
        sig.schema_missing = not any(p.exists() for p in schema_candidates)

    if mods_path.exists():
        for mod_dir in sorted(mods_path.iterdir()):
            if not mod_dir.is_dir():
                continue
            aaf_dir = mod_dir / "AAF"
            if not aaf_dir.exists():
                continue
            for xml_file in sorted(aaf_dir.rglob("*.xml")):
                try:
                    if xml_file.stat().st_size == 0:
                        sig.zero_byte_xml_files.append(f"{mod_dir.name}/{xml_file.relative_to(mod_dir)}")
                except OSError:
                    continue

    return sig


# ---------------------------------------------------------------------------
# AAF multi-owner files: which AAF/*.xml relative paths are shipped by more
# than one enabled mod (a genuine load-order collision), and who currently
# wins. Generalizes the manual MO2 Information->Filetree per-filename search
# that was the only way to find this by hand.
# ---------------------------------------------------------------------------
@dataclass
class MultiOwnerFile:
    relative_path: str  # e.g. "AAF/Atomic Lust_mfgSetData.xml"
    owning_mods: list[str]
    current_winner: str | None


def find_aaf_multi_owner_files(
    mods_path: Path | None = None, modlist_path: Path | None = None
) -> list[MultiOwnerFile]:
    mods_path = mods_path or config.MO2_MODS
    modlist_path = modlist_path or config.MO2_MODLIST
    if not mods_path.exists():
        return []

    owners: dict[str, list[str]] = {}
    for mod_dir in sorted(mods_path.iterdir()):
        if not mod_dir.is_dir():
            continue
        aaf_dir = mod_dir / "AAF"
        if not aaf_dir.exists():
            continue
        for xml_file in aaf_dir.rglob("*.xml"):
            relative_path = str(xml_file.relative_to(mod_dir))
            owners.setdefault(relative_path, []).append(mod_dir.name)

    out: list[MultiOwnerFile] = []
    for relative_path, owning_mods in sorted(owners.items()):
        if len(owning_mods) < 2:
            continue
        winner = file_conflict_winner(relative_path, mods_path, modlist_path)
        out.append(
            MultiOwnerFile(
                relative_path=relative_path,
                owning_mods=sorted(owning_mods),
                current_winner=winner,
            )
        )
    return out
