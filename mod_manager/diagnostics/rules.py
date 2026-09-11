"""Symptom -> signal -> ranked findings. Each rule function is pure: it
takes an already-collected SignalBundle and returns zero or more Findings.
No file I/O happens in this module -- that's signals.py's job, so these
rules are trivially unit-testable against fabricated signal objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..core import catalog
from . import signals
from .symptoms import Symptom

# Fallout 4's plugin master list has a hard 255-slot index (0x00-0xFE; 0xFF
# is reserved). ESL-flagged ("light") plugins share a separate 0xFE00-0xFEFF
# range and don't count against this. This is an engine constraint, not a
# guess.
MAX_REGULAR_PLUGINS = 254


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Action(str, Enum):
    APPLY_RESOLUTION_POLICY = "apply_resolution_policy"  # fixed by resolver.apply()
    MANUAL = "manual"


@dataclass
class Finding:
    title: str
    confidence: Confidence
    evidence: list[str]
    action: Action
    manual_steps: list[str] = field(default_factory=list)


@dataclass
class SignalBundle:
    """Everything a rule function might need, pre-collected so rules stay
    pure functions with no I/O of their own."""

    plugin_signals: list[signals.PluginSignal] = field(default_factory=list)
    resolution_state: signals.ResolutionPolicyState | None = None
    duplicate_pairs: list[tuple[str, str]] = field(default_factory=list)
    skeleton_winner: str | None = None  # who actually wins skeleton.nif right now
    mod_data: dict = field(default_factory=dict)
    aaf_integrity: signals.AAFIntegritySignal | None = None
    aaf_multi_owner_files: list[signals.MultiOwnerFile] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------
def _missing_master_findings(bundle: SignalBundle) -> list[Finding]:
    out = []
    for sig in bundle.plugin_signals:
        if not sig.active:
            continue
        if sig.missing_masters:
            out.append(
                Finding(
                    title=f"{sig.name} requires a master that isn't installed",
                    confidence=Confidence.HIGH,
                    evidence=[
                        f"{sig.name} (from {sig.source_mod or 'unknown mod'}) declares master(s): {', '.join(sig.missing_masters)}",
                        "None of these appear anywhere in plugins.txt -- the required mod is not installed.",
                    ],
                    action=Action.MANUAL,
                    manual_steps=[f"Install the missing master mod that provides {m}" for m in sig.missing_masters],
                )
            )
        if sig.inactive_masters:
            out.append(
                Finding(
                    title=f"{sig.name} requires a master that is installed but not active",
                    confidence=Confidence.HIGH,
                    evidence=[
                        f"{sig.name} (from {sig.source_mod or 'unknown mod'}) declares master(s): {', '.join(sig.inactive_masters)}",
                        "These are present in plugins.txt but not marked active (no leading '*').",
                    ],
                    action=Action.MANUAL,
                    manual_steps=[f"Enable {m} in MO2's Plugins tab" for m in sig.inactive_masters],
                )
            )
        if sig.parse_error and sig.source_mod:
            out.append(
                Finding(
                    title=f"{sig.name} could not be read as a plugin header",
                    confidence=Confidence.LOW,
                    evidence=[f"{sig.parse_error} (file: {sig.source_mod}/{sig.name})"],
                    action=Action.MANUAL,
                    manual_steps=[f"Verify {sig.name} downloaded/installed correctly; it may be corrupt or a non-standard format."],
                )
            )
    return out


def _duplicate_pair_findings(bundle: SignalBundle, confidence: Confidence) -> list[Finding]:
    out = []
    for older, newer in bundle.duplicate_pairs:
        out.append(
            Finding(
                title=f"'{older}' and '{newer}' are both enabled -- known duplicate pair",
                confidence=confidence,
                evidence=[
                    f"Both '{older}' and '{newer}' are installed and enabled at the same time.",
                    f"The resolution policy expects only '{newer}' enabled (see core/catalog.py DISABLE_IF_PRESENT).",
                ],
                action=Action.APPLY_RESOLUTION_POLICY,
            )
        )
    return out


def _plugin_count_finding(bundle: SignalBundle) -> Finding | None:
    active_regular = [s for s in bundle.plugin_signals if s.active and not s.is_light]
    if len(active_regular) <= MAX_REGULAR_PLUGINS:
        return None
    return Finding(
        title=f"{len(active_regular)} active non-ESL plugins exceeds Fallout 4's {MAX_REGULAR_PLUGINS}-slot limit",
        confidence=Confidence.HIGH,
        evidence=[
            f"{len(active_regular)} active plugins are NOT flagged ESL (light).",
            "Fallout 4 has a hard 254-slot regular plugin index; beyond it, plugins silently fail to load "
            "or the game hangs/crashes at the load-order stage.",
        ],
        action=Action.MANUAL,
        manual_steps=["Flag eligible plugins as ESL (light) with a tool like xEdit's ESL flag, or merge/remove plugins."],
    )


def _aaf_integrity_findings(bundle: SignalBundle) -> list[Finding]:
    """Findings from collect_aaf_integrity() -- grounded in a real, confirmed
    crash-when-initiating-an-animation-scene bug (2026-09-08), not a
    hypothetical: UseSignatures=true and/or missing aaf.xsd producing 0-byte
    registered XML across every AAF content pack.
    """
    out: list[Finding] = []
    sig = bundle.aaf_integrity
    if sig is None:
        return out

    if sig.use_signatures_enabled:
        out.append(
            Finding(
                title="AAF's xmlutility.ini has UseSignatures=true, rejecting unsigned content packs",
                confidence=Confidence.HIGH,
                evidence=[
                    "xmlutility.ini's own comment documents 'Default: false, disabled until fully "
                    "tested' -- this is an experimental flag, not a normal setting.",
                    "Third-party AAF content packs (Atomic Lust, BodyTalk2, rxl_bp70, etc.) predate "
                    "this signing scheme and are never signed, so xmlutility.dll reads their XML as "
                    "0 bytes/empty with this left true.",
                ],
                action=Action.APPLY_RESOLUTION_POLICY,
            )
        )

    if sig.zero_byte_xml_files:
        evidence = [
            "A 0-byte AAF content XML is produced by one of two causes: UseSignatures rejecting "
            "unsigned content (finding above, if present), or -- per AAF author dagobaking's own "
            "changelog -- a higher-priority patch mod silently shadowing the real file via a "
            "load-order collision (see the multi-owner finding below, if present).",
        ]
        evidence.extend(sig.zero_byte_xml_files[:10])
        if len(sig.zero_byte_xml_files) > 10:
            evidence.append(f"...and {len(sig.zero_byte_xml_files) - 10} more.")
        out.append(
            Finding(
                title=f"{len(sig.zero_byte_xml_files)} AAF content XML file(s) are 0 bytes on disk",
                confidence=Confidence.HIGH,
                evidence=evidence,
                action=Action.MANUAL,
                manual_steps=[
                    "If UseSignatures=true above, fix that first, then re-run this check before "
                    "doing anything else -- most 0-byte files are explained by that alone.",
                    "For files still 0 bytes after that, check the multi-owner finding for a "
                    "genuine load-order collision instead.",
                ],
            )
        )

    if sig.schema_missing:
        out.append(
            Finding(
                title="AAF's schema file (aaf.xsd) was not found in the AAF mod folder",
                confidence=Confidence.MEDIUM,
                evidence=[
                    "Checked 'Advanced Animation Framework/aaf.xsd' and "
                    "'Advanced Animation Framework/AAF/aaf.xsd' -- neither exists. (The exact "
                    "expected location wasn't confirmed against a working install, so both "
                    "plausible spots are checked rather than asserting one.)",
                    "xmlutility.dll uses this schema to validate registered content packs; a "
                    "missing schema can itself cause registration to fail even for valid, signed XML.",
                ],
                action=Action.MANUAL,
                manual_steps=["Re-download/reinstall Advanced Animation Framework -- aaf.xsd ships with it."],
            )
        )

    return out


def _aaf_multi_owner_findings(bundle: SignalBundle) -> list[Finding]:
    """Findings from find_aaf_multi_owner_files() -- surfaces the exact class
    of bug that required manual MO2 Filetree searching to diagnose by hand:
    two or more mods shipping the same AAF/*.xml relative path, where only
    the MO2 load-order winner's copy is actually used in-game.
    """
    out: list[Finding] = []
    for f in bundle.aaf_multi_owner_files:
        out.append(
            Finding(
                title=f"{f.relative_path} is shipped by {len(f.owning_mods)} mods -- load-order collision",
                confidence=Confidence.MEDIUM,
                evidence=[
                    f"Owning mods (alphabetical, not priority order): {', '.join(f.owning_mods)}.",
                    f"Current MO2 load-order winner: {f.current_winner or 'not resolvable from modlist.txt'}.",
                    "Only the winner's copy of this file is used in-game. If that copy is stale, "
                    "empty, or otherwise wrong, this file's real animation data never loads for the "
                    "player -- same observable symptom as the UseSignatures bug but a different cause.",
                ],
                action=Action.MANUAL,
                manual_steps=[
                    "Open MO2 -> Information -> Filetree, search this exact filename to confirm the "
                    "winner, then decide whether that's the mod that should actually own it.",
                ],
            )
        )
    return out


def _classic_recommendation() -> Finding:
    """Always-present pointer, not a detected problem. CLASSIC (Crash Log
    Auto-Scanner And Setup Integrity Checker) is the actively maintained
    community tool for Buffout 4 crash-log analysis -- ~250 checks against a
    real known-issue database, FormID lookups, structured markdown reports.
    This engine used to regex its way through raw crash logs instead; that
    was a worse reimplementation of something already solved, so it was
    removed. If it's not already installed, it needs to be grabbed
    separately (it is not bundled with MO2 or Buffout 4).
    """
    return Finding(
        title="Run CLASSIC for full crash-log analysis",
        confidence=Confidence.LOW,
        evidence=[
            "This engine does not parse Buffout 4 crash logs itself -- CLASSIC "
            "(Crash Log Auto-Scanner And Setup Integrity Checker) already does that job "
            "properly: ~250 checks against a maintained known-issue database, FormID "
            "lookups, and a per-crash markdown report.",
        ],
        action=Action.MANUAL,
        manual_steps=[
            "If not already installed: https://www.nexusmods.com/fallout4/mods/56255",
            "Run it, then open the generated crash-<date>-AUTOSCAN.md report next to your crash log.",
        ],
    )


# ---------------------------------------------------------------------------
# Per-symptom rule sets
# ---------------------------------------------------------------------------
def rules_for_ctd_on_launch(bundle: SignalBundle) -> list[Finding]:
    out = _missing_master_findings(bundle)
    out.extend(_duplicate_pair_findings(bundle, Confidence.MEDIUM))
    count_finding = _plugin_count_finding(bundle)
    if count_finding:
        out.append(count_finding)
    out.append(_classic_recommendation())
    return out


def rules_for_ctd_ingame(bundle: SignalBundle) -> list[Finding]:
    out = _missing_master_findings(bundle)
    out.extend(_duplicate_pair_findings(bundle, Confidence.LOW))
    out.extend(_aaf_integrity_findings(bundle))
    out.extend(_aaf_multi_owner_findings(bundle))
    out.append(_classic_recommendation())
    return out


def rules_for_animation_misalign(bundle: SignalBundle) -> list[Finding]:
    out: list[Finding] = []
    state = bundle.resolution_state
    if state is None:
        return out

    installed = {s.source_mod for s in bundle.plugin_signals if s.source_mod}

    squirtcum_key = "Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0/AAF/Atomic Lust_positionData.xml"
    if state.squirtcum_offset_present.get(squirtcum_key):
        out.append(
            Finding(
                title='SquirtCum positionData still contains the offset="0,50,180" bug',
                confidence=Confidence.HIGH,
                evidence=[
                    "The 180-degree yaw offset that causes actors to face away from each other "
                    "is still present in SquirtCum's copy of Atomic Lust_positionData.xml.",
                ],
                action=Action.APPLY_RESOLUTION_POLICY,
            )
        )

    if state.ultimate_override_hidden is False:
        out.append(
            Finding(
                title="Ultimate AAF Patch's Override positionData files are not hidden",
                confidence=Confidence.HIGH,
                evidence=[
                    'Ultimate AAF Patch Override *positionData*.xml files default to offset="0,50,180" '
                    "(180-degree yaw), which fights the original position IDs still started by HotC/AAF.",
                    "These files are currently active (not renamed to .mohidden).",
                ],
                action=Action.APPLY_RESOLUTION_POLICY,
            )
        )

    for key, correct in state.ini_settings_correct.items():
        if not correct:
            out.append(
                Finding(
                    title=f"AAF_settings.ini setting not applied: {key.split('#')[-1]}",
                    confidence=Confidence.MEDIUM,
                    evidence=[f"{key} is not set to the value the resolution policy expects."],
                    action=Action.APPLY_RESOLUTION_POLICY,
                )
            )

    return out


def rules_for_animation_tpose(bundle: SignalBundle) -> list[Finding]:
    out: list[Finding] = []
    winner = bundle.skeleton_winner
    if winner and winner != "ZeX - ZaZ Extended Skeleton":
        out.append(
            Finding(
                title=f"'{winner}' is winning the human skeleton file, not ZeX",
                confidence=Confidence.HIGH,
                evidence=[
                    f"skeleton.nif under Meshes/Actors/Character/CharacterAssets/ is currently served by '{winner}'.",
                    "ZeX - ZaZ Extended Skeleton is expected to be the sole skeleton provider; any other "
                    "winner (commonly Atomic Muscle) causes T-pose or broken morphs.",
                ],
                action=Action.APPLY_RESOLUTION_POLICY
                if winner == "Atomic Muscle"
                else Action.MANUAL,
                manual_steps=[]
                if winner == "Atomic Muscle"
                else [f"Reorder '{winner}' below ZeX - ZaZ Extended Skeleton, or hide its skeleton.nif."],
            )
        )
    zex_installed = any(s.source_mod == "ZeX - ZaZ Extended Skeleton" for s in bundle.plugin_signals) or "ZeX - ZaZ Extended Skeleton" in bundle.mod_data
    if not zex_installed:
        out.append(
            Finding(
                title="ZeX - ZaZ Extended Skeleton is not installed",
                confidence=Confidence.HIGH,
                evidence=["No skeleton provider found -- ZeX is not present in the mod list."],
                action=Action.MANUAL,
                manual_steps=["Install ZeX - ZaZ Extended Skeleton."],
            )
        )
    return out


def rules_for_content_missing_ingame(bundle: SignalBundle) -> list[Finding]:
    out = _missing_master_findings(bundle)
    for sig in bundle.plugin_signals:
        if sig.active or not sig.source_mod:
            continue
        mod_enabled = bundle.mod_data.get(sig.source_mod, {}).get("enabled", True)
        if mod_enabled:
            out.append(
                Finding(
                    title=f"{sig.name} is inactive even though its mod is enabled",
                    confidence=Confidence.HIGH,
                    evidence=[
                        f"'{sig.source_mod}' is enabled in the mod list, but its plugin {sig.name} "
                        "has no leading '*' in plugins.txt -- MO2 does not auto-activate plugins from an "
                        "enabled mod, so the mod's content (items, NPCs, cells) will not appear in-game.",
                    ],
                    action=Action.MANUAL,
                    manual_steps=[f"Enable {sig.name} in MO2's Plugins tab (right pane)."],
                )
            )
    return out


def rules_for_load_hang(bundle: SignalBundle) -> list[Finding]:
    out = _missing_master_findings(bundle)
    count_finding = _plugin_count_finding(bundle)
    if count_finding:
        out.append(count_finding)
    out.extend(_duplicate_pair_findings(bundle, Confidence.MEDIUM))
    return out


RULES_BY_SYMPTOM = {
    Symptom.CTD_ON_LAUNCH: rules_for_ctd_on_launch,
    Symptom.CTD_INGAME: rules_for_ctd_ingame,
    Symptom.ANIMATION_MISALIGN: rules_for_animation_misalign,
    Symptom.ANIMATION_TPOSE: rules_for_animation_tpose,
    Symptom.CONTENT_MISSING_INGAME: rules_for_content_missing_ingame,
    Symptom.LOAD_HANG: rules_for_load_hang,
}

_CONFIDENCE_ORDER = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}


def rank(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: _CONFIDENCE_ORDER[f.confidence])
