"""THE current, single AAF/body conflict resolution decision.

This file exists because three scripts (fix_aaf_alignment.py,
fix_aaf_alignment_v2.py, align_mods_compatibility.py) each independently
"fixed" the same actor-misalignment bug with mutually contradictory
strategies, and nothing recorded which one was actually the last word:

  1. fix_aaf_alignment.py    -- disable One Patch, Extended, SquirtCum;
                                 keep Ultimate AAF Patch enabled.
  2. fix_aaf_alignment_v2.py -- the OPPOSITE: disable Ultimate + Extended +
                                 SquirtCum, enable One Patch. Root-caused the
                                 bug in its own docstring: Ultimate's Override
                                 XMLs default to offset="0,50,180", a 180-
                                 degree yaw that makes actors face away from
                                 each other when the original position IDs are
                                 still triggered by HotC/AAF.
  3. align_mods_compatibility.py -- refines #2: instead of disabling whole
                                 mods (losing Ultimate's non-conflicting
                                 content), HIDE only the specific Override
                                 *positionData*.xml files inside Ultimate AAF
                                 Patch, and hide Atomic Muscle's skeleton
                                 files so ZeX's skeleton always wins. Every
                                 mod involved stays enabled.

  #3 is adopted here as canonical, for two reasons, not just "it ran last":
  - It is strictly more correct: file-hides don't depend on modlist.txt
    enable flags, so a later re-run of apply_optimal_load_order.py (which
    has NO knowledge of the AAF-specific disable sets from #1/#2) cannot
    silently undo it. That is exactly the drift bug that made this project
    need a diagnostics engine in the first place -- #1 and #2's fixes kept
    getting reset because nothing else in the codebase knew they existed.
  - It preserves mod content instead of nuking whole mods for one bad file.

If you determine a different resolution is correct, change it HERE and
nowhere else -- do not add a sixth script with its own DISABLE set.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass(frozen=True)
class FileHide:
    mod: str
    relative_path: str
    reason: str


@dataclass(frozen=True)
class TextPatch:
    mod: str
    relative_path: str
    remove_substring: str
    reason: str


@dataclass(frozen=True)
class IniSetting:
    mod: str
    relative_path: str
    key: str
    value: str
    reason: str


# Atomic Muscle ships its own human skeleton.nif/.hkx; ZeX must be the one
# actual skeleton provider or body/animation morphs break across the board.
ATOMIC_MUSCLE_SKELETON_HIDES: list[FileHide] = [
    FileHide(
        mod="Atomic Muscle",
        relative_path="Meshes/Actors/Character/CharacterAssets/skeleton.nif",
        reason="Atomic Muscle's skeleton must not win over ZeX - ZaZ Extended Skeleton.",
    ),
    FileHide(
        mod="Atomic Muscle",
        relative_path="Meshes/Actors/Character/CharacterAssets/skeleton.hkx",
        reason="Same as skeleton.nif -- the havok counterpart.",
    ),
    FileHide(
        mod="Atomic Muscle",
        relative_path="Meshes/Actors/Character/CharacterAssets/skeleton_faceBones.nif",
        reason="Face-bone rig must also come from ZeX, not Atomic Muscle.",
    ),
    FileHide(
        mod="Atomic Muscle",
        relative_path="Meshes/Actors/Character/CharacterAssets/skeleton_female_faceBones.nif",
        reason="Female counterpart of the above.",
    ),
]

# Ultimate AAF Patch's Override XMLs default to offset="0,50,180" -- a
# 180-degree yaw -- which fights the original position IDs still triggered
# by HotC/AAF and produces actors facing away from each other / one standing
# one lying. Hide only the Override files; the rest of Ultimate's content
# (extra scenes/tags) is kept.
ULTIMATE_OVERRIDE_HIDE_GLOB = "AAF/*Override*positionData*.xml"
ULTIMATE_OVERRIDE_REASON = (
    'Ultimate AAF Patch Override XMLs default to offset="0,50,180" (180-degree '
    "yaw), which conflicts with original positionData IDs still started by "
    "HotC/AAF -- root cause of the facing-opposite-directions / one-standing-"
    "one-lying misalignment bug (diagnosed in the retired fix_aaf_alignment_v2.py)."
)

# SquirtCum's own copy of Atomic Lust's positionData carries the same bad
# offset; strip it directly rather than disabling the whole patch (it also
# provides FX overlays nothing else supplies).
SQUIRTCUM_OFFSET_PATCHES: list[TextPatch] = [
    TextPatch(
        mod="Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0",
        relative_path="AAF/Atomic Lust_positionData.xml",
        remove_substring=' offset="0,50,180"',
        reason="Same 180-degree-yaw bug as Ultimate's Override files, in SquirtCum's own copy.",
    ),
    TextPatch(
        mod="Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0",
        relative_path="AAF/Atomic Lust_positionData2.xml",
        remove_substring=' offset="0,50,180"',
        reason="Second copy of the same file/bug.",
    ),
]

# Actor height mismatches independent of the yaw bug -- scale to the
# participant instead of enforcing race scale, which fights it.
AAF_SETTINGS_PATCH = IniSetting(
    mod="Advanced Animation Framework",
    relative_path="AAF/AAF_settings.ini",
    key="scale_actors_for_animations",
    value="true",
    reason="Corrects actor height mismatches during animations.",
)
AAF_ENFORCE_RACE_SCALE_PATCH = IniSetting(
    mod="Advanced Animation Framework",
    relative_path="AAF/AAF_settings.ini",
    key="enforce_race_scale",
    value="false",
    reason="Fights scale_actors_for_animations if left true.",
)

# Confirmed root cause (2026-09-08) of a real crash-when-initiating-an-
# animation-scene bug, not a hypothetical: UseSignatures is an experimental
# flag -- xmlutility.ini's own comment documents "Default: false, disabled
# until fully tested". Every third-party AAF content pack (Atomic Lust,
# BodyTalk2, rxl_bp70, etc.) predates this signing scheme and is never
# signed, so xmlutility.dll reads their XML as empty (0 bytes) across the
# board when this is left true. xmlutility.ini sits at the AAF mod's root,
# not under its AAF/ subfolder -- verified against the real install.
XMLUTILITY_SIGNATURES_PATCH = IniSetting(
    mod="Advanced Animation Framework",
    relative_path="xmlutility.ini",
    key="UseSignatures",
    value="false",
    reason=(
        'UseSignatures=true rejects unsigned third-party AAF content packs as '
        '0-byte/empty -- confirmed root cause of a crash on animation-scene '
        'start. The ini\'s own comment states the default is false.'
    ),
)


def all_file_hides() -> list[FileHide]:
    return list(ATOMIC_MUSCLE_SKELETON_HIDES)


def all_text_patches() -> list[TextPatch]:
    return list(SQUIRTCUM_OFFSET_PATCHES)


def all_ini_settings() -> list[IniSetting]:
    return [AAF_SETTINGS_PATCH, AAF_ENFORCE_RACE_SCALE_PATCH, XMLUTILITY_SIGNATURES_PATCH]


def ultimate_override_targets(mods_root: Path | None = None) -> list[Path]:
    mods_root = mods_root or config.MO2_MODS
    uap = mods_root / "Ultimate AAF Patch"
    if not uap.exists():
        return []
    return sorted(uap.glob(ULTIMATE_OVERRIDE_HIDE_GLOB))
