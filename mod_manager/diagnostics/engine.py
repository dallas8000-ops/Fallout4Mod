"""Entry point: Symptom -> collect only the signals that symptom's rules
need -> ranked findings. This is the "diagnostic engine" the AI scope
decision asked for -- deterministic, auditable, no network call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..core import config, mod_data_store
from . import signals
from .rules import RULES_BY_SYMPTOM, Finding, SignalBundle, rank
from .symptoms import Symptom

# Which raw signals each symptom's rules actually consume, so we don't
# collect plugin headers for an animation-alignment report or vice versa.
# No crash-log signal here -- see signals.py's module docstring for why
# (CLASSIC already does that job; rules.py points to it as a manual step).
_NEEDS_PLUGINS = {
    Symptom.CTD_ON_LAUNCH,
    Symptom.CTD_INGAME,
    Symptom.CONTENT_MISSING_INGAME,
    Symptom.LOAD_HANG,
    Symptom.ANIMATION_TPOSE,
}
_NEEDS_RESOLUTION_STATE = {Symptom.ANIMATION_MISALIGN}
_NEEDS_SKELETON_WINNER = {Symptom.ANIMATION_TPOSE}
_NEEDS_DUPLICATE_PAIRS = {Symptom.CTD_ON_LAUNCH, Symptom.CTD_INGAME, Symptom.LOAD_HANG}
# Grounded in a real, confirmed bug (2026-09-08): crash on initiating an AAF
# animation scene, root-caused to xmlutility.ini's UseSignatures flag and/or
# a load-order collision on AAF content XML. CTD_INGAME is the closest
# existing symptom to "crashes when an animation starts" -- no new Symptom
# was needed for this.
_NEEDS_AAF_INTEGRITY = {Symptom.CTD_INGAME}
_NEEDS_AAF_MULTI_OWNER = {Symptom.CTD_INGAME}


@dataclass
class DiagnosisResult:
    symptom: Symptom
    findings: list[Finding]
    signals_collected: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.findings:
            return "No known-pattern issues detected from current signals."
        lines = [f"{i}. [{f.confidence.value.upper()}] {f.title}" for i, f in enumerate(self.findings, 1)]
        return "\n".join(lines)


def diagnose(
    symptom: Symptom,
    *,
    mods_path: Path | None = None,
    modlist_path: Path | None = None,
    plugins_path: Path | None = None,
    mod_data_path: Path | None = None,
) -> DiagnosisResult:
    mods_path = mods_path or config.MO2_MODS
    modlist_path = modlist_path or config.MO2_MODLIST
    plugins_path = plugins_path or config.MO2_PLUGINS
    mod_data_path = mod_data_path or config.MOD_DATA_PATH

    bundle = SignalBundle()
    collected: list[str] = []

    bundle.mod_data = mod_data_store.load(mod_data_path)
    collected.append(f"mod_data: {mod_data_path}")

    if symptom in _NEEDS_PLUGINS:
        bundle.plugin_signals = signals.collect_plugin_signals(mods_path, plugins_path)
        collected.append(f"plugin activation + headers: {plugins_path}")

    if symptom in _NEEDS_DUPLICATE_PAIRS:
        bundle.duplicate_pairs = signals.duplicate_pairs_both_enabled(bundle.mod_data)
        collected.append("duplicate-pair check (mod_data)")

    if symptom in _NEEDS_RESOLUTION_STATE:
        bundle.resolution_state = signals.collect_resolution_policy_state(mods_path)
        collected.append("resolution-policy file/ini state")

    if symptom in _NEEDS_SKELETON_WINNER:
        bundle.skeleton_winner = signals.file_conflict_winner(
            "Meshes/Actors/Character/CharacterAssets/skeleton.nif", mods_path, modlist_path
        )
        collected.append("skeleton.nif conflict winner")

    if symptom in _NEEDS_AAF_INTEGRITY:
        bundle.aaf_integrity = signals.collect_aaf_integrity(mods_path)
        collected.append("AAF xmlutility.ini / aaf.xsd / zero-byte XML integrity check")

    if symptom in _NEEDS_AAF_MULTI_OWNER:
        bundle.aaf_multi_owner_files = signals.find_aaf_multi_owner_files(mods_path, modlist_path)
        collected.append("AAF content-file multi-owner (load-order collision) check")

    rule_fn = RULES_BY_SYMPTOM[symptom]
    findings = rank(rule_fn(bundle))

    return DiagnosisResult(symptom=symptom, findings=findings, signals_collected=collected)
