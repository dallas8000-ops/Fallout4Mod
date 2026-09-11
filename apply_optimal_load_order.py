"""
Apply the requested MO2 left-pane sequence (Priority 0 to highest number).

Priority semantics in this project:
- Lower numeric priority = earlier in the managed list (top-to-bottom guide).
- Higher numeric priority = later in the managed list.

When writing MO2 modlist.txt, this script keeps the existing reverse-write
behavior used by this repository's tooling.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MOD_DATA_PATH = ROOT / "mod_manager" / "mod_data.json"
MO2_MODS = Path(r"C:\Users\Ray\AppData\Local\ModOrganizer\Fallout 4\mods")
MO2_MODLIST = Path(
    r"C:\Users\Ray\AppData\Local\ModOrganizer\Fallout 4\profiles\Default\modlist.txt"
)

# Exact folder names in requested top-to-bottom guide order
# (Priority 0 to highest number).
ORDER_LOW_TO_HIGH: list[str] = [
    # --- 1) Core Frameworks & Engine Fixes ---
    "Address Library - All In One",
    "Address Library",  # kept disabled if All-In-One present
    "Buffout 4",
    "Unofficial Fallout 4 Patch",
    "Mod Configuration Menu 1.11.221",
    "Mod Configuration Menu 1.43",  # disabled on Next Gen (duplicate)

    # --- 2) Animation & Body Frameworks (The Foundation) ---
    "Advanced Animation Framework",
    "ZeX - ZaZ Extended Skeleton",
    "BodySlide and Outfit Studio -",

    # --- 3) Body Frameworks & Physics ---
    "Caliente's Beautiful Bodies Enhancer -CBBE-",
    "BodyTalk",
    "Atomic Muscle",
    "Sam BodySlide Output",
    "MTM 3B OCBP - OCBPC Physics and Collision Preset",
    "Toned and Shapely Body for CBBE and 3BA Vagina Add-on",

    # --- 4) Textures, Skins, & Face Morphs ---
    "RealVagCBBE",
    "Muscular Body",
    "ADDON_Body_Textures_With_Detailed_Vagina",
    "Younger Male Face Texture",
    "BodyTriangleEnhancer",
    "High Res DLC Black Face Fix",

    # --- 5) NPC Changes & Hair ---
    "Beautiful Female Settlers",
    "Beautiful Female Enemies V. 2.0",
    "MyCleanRaiders_CBBE1.0",
    "Lots More Male Hairstyles v. 1.21 - Fix",
    "Lots More Female Hairstyles v. 1.33",
    "Ponytail Hairstyles by Azar - BA2",
    "Looks Menu Customization Compendium",
    "LooksMenu v1-7-0-3",
    "LooksMenu v1-7-0-2",  # disabled (older duplicate)

    # --- 6) AAF Theme Packs & Adult Frameworks ---
    "SexAttributes",
    "AAF_FamilyPlanningEnhanced_",
    "AAF_SEU_V",
    "AAF_SCRS",
    "AAF - The One Patch to Bang Them All",
    "Atomic Lust",
    "AAF Vanilla-Kinky-Creatures Sex Animation Themes",
    "Four-Play Animations by Crazy6987",
    "FO4 Animations by Leito",
    "Animated_Fannies__",
    "SavageCabbages Animation Pack",
    "BP70 Fallout 4 Sex Animations 2.3",
    "SAM Enhanced Animations",
    "RZF4S_",
    "Dynamic Cumshots",
    "CumOverlays v",
    "Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0",
    "Extended AAF Patch",
    "Ultimate AAF Patch",
    "AAF patches for Leito and Crazy animations",

    # --- 6) AAF Theme Packs & Adult Frameworks (companions) ---
    "Commonwealth Moisturizer",
    "LLFP",
    "Nude Male Cut Erect",
    "Hookers of the Commonwealth (HotC) - v.0.99h",

    # --- 7) Armor, Clothing, & Weapons ---
    "NanoSuit",
    "Black and Red Vaultsuit_FULL_Male and Female",
    "Black Road Leathers",
    "Cronen Squall - Main",
    "JensenArmor",
    "Stealth Glasses",
    "File C - HN66_SiriusArmor_3.20_Main mod files",
    # --- Weapon frameworks, then weapons, then weapon patches ---
    "Tactical Reload Framework",
    "CALIBER-COMPLEX",
    "AS Vektor Commonwealth Version",
    "RU556 - Assault Rifle",
    "Smith and Wesson 500- REDUX beta",
    "Combined Arms - 1.0",
    "Accuracy International AX50",
    "Tavor X95",
    "MG42",
    "FN P90",
    "Bolt Actions of the Wasteland",
    "HK G11 K2",
    "Mk 23 SOCOM - 1.0 - MAIN",
    "1. SR-25 - Main CN",
    "FACTOR ENG (FULL)",
    "155mm Howitzer M1 4K New",
    "2. Glock family - Main NO TR",
    "Scar Family - Main NO TR",
    "Desert Eagle",
    "Desert Eagle Silencer 1.4",
    "R8 Revolver 4K",
    "Remington 700",
    "Kendall Ballistics Karma",
    "Stahl Arms STA-20 10mm Pistol",
    "Ranger Sequoia Replacer 1.1",
    "Crossbows of the Commonwealth 1.4",
    "Dak's Throwables",
    "Explosives Expanded",
    "Remote Explosives - Standard ESP",
    "Special Rings",

    # --- 8) Settlement, Environment, & Patches ---
    "Clean My Settlement Redux - NextGen REBUILT",
    "Sanctuary Estates",
    "Fusion City Rising v.1.0",
    "Generator Fixerupper",
    "Better Generators (x3)",
    "Very Small Generators (1000)",
    "Deployable Turret Pack 2",
    "Scrap scrap 1.1",
    # Keep leveled-list patches at the absolute bottom.
    "Weapons Level List Patches",
]

# Prefer newer / Next-Gen; disable older duplicates when both exist.
DISABLE_IF_PRESENT: dict[str, str] = {
    # older -> preferred
    "LooksMenu v1-7-0-2": "LooksMenu v1-7-0-3",
    "Mod Configuration Menu 1.43": "Mod Configuration Menu 1.11.221",
    "Address Library": "Address Library - All In One",
}

# Only true duplicates — never disable animation packs / AAF patches for "theory".
ALWAYS_DISABLE: set[str] = set()


CAT_CORE = "Core Frameworks & Engine Fixes"
CAT_ANIM_BODY = "Animation & Body Frameworks"
CAT_BODY_PHYS = "Body Frameworks & Physics"
CAT_TEXTURES = "Textures, Skins, & Face Morphs"
CAT_NPC_HAIR = "NPC Changes & Hair"
CAT_AAF = "AAF Theme Packs & Adult Frameworks"
CAT_ARMOR_WEAPONS = "Armor, Clothing, & Weapons"
CAT_SETTLEMENTS = "Settlement, Environment, & Patches"
CAT_OTHER = "Other"


TIER_BY_CATEGORY = {
    CAT_CORE: 1,
    CAT_ANIM_BODY: 2,
    CAT_BODY_PHYS: 3,
    CAT_TEXTURES: 4,
    CAT_NPC_HAIR: 5,
    CAT_AAF: 6,
    CAT_ARMOR_WEAPONS: 7,
    CAT_SETTLEMENTS: 8,
    CAT_OTHER: 9,
}

CATEGORY_HINTS: list[tuple[str, str]] = [
    ("address library", CAT_CORE),
    ("buffout", CAT_CORE),
    ("unofficial fallout 4 patch", CAT_CORE),
    ("mod configuration menu", CAT_CORE),
    ("advanced animation framework", CAT_ANIM_BODY),
    ("zex", CAT_ANIM_BODY),
    ("bodyslide", CAT_ANIM_BODY),
    ("cbbe", CAT_BODY_PHYS),
    ("bodytalk", CAT_BODY_PHYS),
    ("atomic muscle", CAT_BODY_PHYS),
    ("ocbp", CAT_BODY_PHYS),
    ("realvag", CAT_TEXTURES),
    ("muscular", CAT_TEXTURES),
    ("texture", CAT_TEXTURES),
    ("bodytriangle", CAT_TEXTURES),
    ("black face fix", CAT_TEXTURES),
    ("looksmenu", CAT_NPC_HAIR),
    ("hairstyle", CAT_NPC_HAIR),
    ("beautiful female", CAT_NPC_HAIR),
    ("aaf", CAT_AAF),
    ("atomic lust", CAT_AAF),
    ("animation", CAT_AAF),
    ("cum", CAT_AAF),
    ("hotc", CAT_AAF),
    ("hookers of the commonwealth", CAT_AAF),
    ("weapon", CAT_ARMOR_WEAPONS),
    ("rifle", CAT_ARMOR_WEAPONS),
    ("revolver", CAT_ARMOR_WEAPONS),
    ("caliber", CAT_ARMOR_WEAPONS),
    ("tactical reload", CAT_ARMOR_WEAPONS),
    ("armor", CAT_ARMOR_WEAPONS),
    ("suit", CAT_ARMOR_WEAPONS),
    ("generator", CAT_SETTLEMENTS),
    ("settlement", CAT_SETTLEMENTS),
    ("scrap", CAT_SETTLEMENTS),
    ("turret", CAT_SETTLEMENTS),
    ("fusion city", CAT_SETTLEMENTS),
    ("sanctuary", CAT_SETTLEMENTS),
    ("level list", CAT_SETTLEMENTS),
]


def categorize(name: str) -> str:
    low = name.lower()
    for needle, cat in CATEGORY_HINTS:
        if needle in low:
            return cat
    return CAT_OTHER


def read_star_entries(modlist_path: Path) -> list[str]:
    """Preserve DLC / Creation Club / Unmanaged lines from existing modlist."""
    if not modlist_path.exists():
        return []
    stars: list[str] = []
    for line in modlist_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("*"):
            stars.append(line)
    return stars


def installed_mods() -> set[str]:
    if not MO2_MODS.exists():
        return set()
    return {p.name for p in MO2_MODS.iterdir() if p.is_dir()}


def build_ordered(installed: set[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in ORDER_LOW_TO_HIGH:
        if name in installed and name not in seen:
            ordered.append(name)
            seen.add(name)
    # Any leftover mods: put before settlements-level (end of low-to-high = high priority)
    leftovers = sorted(installed - seen)
    ordered.extend(leftovers)
    return ordered


def enabled_from_modlist(modlist_path: Path) -> dict[str, bool]:
    """Read +/- enable state from an existing MO2 modlist."""
    state: dict[str, bool] = {}
    if not modlist_path.exists():
        return state
    for line in modlist_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("+"):
            state[line[1:]] = True
        elif line.startswith("-"):
            state[line[1:]] = False
    return state


def enabled_map(
    ordered: list[str],
    existing: dict,
    prior_modlist_state: dict[str, bool] | None = None,
) -> dict[str, bool]:
    enabled: dict[str, bool] = {}
    for name in ordered:
        if prior_modlist_state and name in prior_modlist_state:
            enabled[name] = prior_modlist_state[name]
        else:
            prev = existing.get(name, {})
            enabled[name] = bool(prev.get("enabled", True))
    for older, newer in DISABLE_IF_PRESENT.items():
        if older in enabled and newer in enabled:
            enabled[older] = False
            enabled[newer] = True
    for name in ALWAYS_DISABLE:
        if name in enabled:
            enabled[name] = False
    return enabled



def write_modlist(ordered_low_to_high: list[str], enabled: dict[str, bool], stars: list[str]) -> None:
    # Reverse: highest conflict priority first in file
    lines = ["# This file was automatically generated by Mod Organizer."]
    for name in reversed(ordered_low_to_high):
        prefix = "+" if enabled.get(name, True) else "-"
        lines.append(f"{prefix}{name}")
    lines.extend(stars)
    MO2_MODLIST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text) if text.strip() else {}


def update_mod_data(ordered_low_to_high: list[str], enabled: dict[str, bool]) -> None:
    data = load_json(MOD_DATA_PATH)
    data.pop("example", None)

    for idx, name in enumerate(ordered_low_to_high):
        cat = categorize(name)
        if name in data and data[name].get("category") not in (None, "", "Uncategorized", "Other"):
            cat = data[name]["category"]
            # Re-categorize leftovers that were stuck in Other
            if cat == "Other":
                cat = categorize(name)
        entry = data.get(name, {})
        entry["category"] = cat
        entry["priority"] = idx
        entry["enabled"] = enabled.get(name, True)
        entry["tier"] = TIER_BY_CATEGORY.get(cat, 9)
        data[name] = entry

    # Drop mods no longer installed
    for key in list(data.keys()):
        if key not in enabled:
            del data[key]

    MOD_DATA_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    installed = installed_mods()
    if not installed:
        raise SystemExit(f"No mods found in {MO2_MODS}")

    existing = load_json(MOD_DATA_PATH)

    stars = read_star_entries(MO2_MODLIST)
    # Prefer enable state from backup if we are about to overwrite
    bak = MO2_MODLIST.with_suffix(".txt.bak_before_optimal")
    prior_state = enabled_from_modlist(bak if bak.exists() else MO2_MODLIST)
    ordered = build_ordered(installed)
    enabled = enabled_map(ordered, existing, prior_state)


    # Backup modlist
    if MO2_MODLIST.exists():
        bak = MO2_MODLIST.with_suffix(".txt.bak_before_optimal")
        bak.write_text(MO2_MODLIST.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup: {bak}")

    write_modlist(ordered, enabled, stars)
    update_mod_data(ordered, enabled)

    disabled = [n for n, e in enabled.items() if not e]
    print(f"Wrote {len(ordered)} managed mods to {MO2_MODLIST}")
    print(f"Preserved {len(stars)} DLC/CC/Unmanaged entries")
    if disabled:
        print("Disabled (duplicates / prior choice):")
        for n in disabled:
            print(f"  - {n}")
    print("\nTop of modlist (wins conflicts):")
    for n in reversed(ordered[-8:]):
        mark = "+" if enabled[n] else "-"
        print(f"  {mark}{n}")
    print("\nBottom of managed (foundations):")
    for n in ordered[:8]:
        mark = "+" if enabled[n] else "-"
        print(f"  {mark}{n}")


if __name__ == "__main__":
    main()
