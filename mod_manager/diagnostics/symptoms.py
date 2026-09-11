"""The fixed set of symptom categories this engine can diagnose.

Kept deliberately closed (an enum, not free text) because this is the
"deterministic engine, no LLM" design the AI scope decision called for --
a symptom has to map onto real, checkable signals in signals.py, or it
doesn't belong here. Add a new symptom only alongside the signals and
rules that back it.
"""
from __future__ import annotations

from enum import Enum


class Symptom(str, Enum):
    CTD_ON_LAUNCH = "ctd_on_launch"
    CTD_INGAME = "ctd_ingame"
    ANIMATION_MISALIGN = "animation_misalign"
    ANIMATION_TPOSE = "animation_tpose"
    CONTENT_MISSING_INGAME = "content_missing_ingame"
    LOAD_HANG = "load_hang"

    @classmethod
    def describe(cls, symptom: "Symptom") -> str:
        return _DESCRIPTIONS[symptom]


_DESCRIPTIONS = {
    Symptom.CTD_ON_LAUNCH: "Crash to desktop before or during the main menu / initial load.",
    Symptom.CTD_INGAME: "Crash to desktop while playing (not on launch).",
    Symptom.ANIMATION_MISALIGN: "Actors facing the wrong way, offset, or not lined up during an animation.",
    Symptom.ANIMATION_TPOSE: "Actor stuck in a T-pose / not playing the animation at all.",
    Symptom.CONTENT_MISSING_INGAME: "Expected item, NPC, or location from an installed mod is missing in-game.",
    Symptom.LOAD_HANG: "Game hangs or freezes on a loading screen / stuck at black screen.",
}
