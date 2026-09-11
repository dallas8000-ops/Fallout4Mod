"""
Align MO2 left-pane for maximum compatibility — keep packs ENABLED.

Conflict rules (facts from filenames):
- Animation packs ship HKX + base AAF XML.
- One Patch overwrites pack *positionData* (same IDs HotC/AAF call).
- SquirtCum adds FX and also overwrites some pack XML — keep it for FX,
  but let One Patch win *positionData* (priority).
- Ultimate adds [UAP] extras; its *Override* XMLs null original IDs
  (loadPriority + animation=Null). Hide only Override files so UAP stays.
- Extended duplicates many Ultimate files — keep enabled, below Ultimate.
- Atomic Muscle ships skeleton.nif — hide those files so ZeX wins
  (mod stays enabled for body/textures).
- Only disable true duplicates: old LooksMenu, old MCM, old Address Library.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

MO2 = Path(r"C:\Users\Ray\AppData\Local\ModOrganizer\Fallout 4")
MODS = MO2 / "mods"
MODLIST = MO2 / "profiles" / "Default" / "modlist.txt"
MOD_DATA = Path(r"C:\Software Projects\Fallout4Mod\mod_manager\mod_data.json")

# True duplicates only
DISABLE = {
    "LooksMenu v1-7-0-2",
    "Mod Configuration Menu 1.43",
    "Address Library",
}

# Low priority first (foundations) -> high last (wins conflicts)
ORDER_LOW_TO_HIGH: list[str] = [
    # Core
    "Address Library - All In One",
    "Address Library",
    "Buffout 4",
    "Unofficial Fallout 4 Patch",
    "High Res DLC Black Face Fix",
    "Mod Configuration Menu 1.11.221",
    "Mod Configuration Menu 1.43",
    # Skeleton / body (Atomic Muscle below ZeX via file hide + order)
    "Atomic Muscle",
    "ZeX - ZaZ Extended Skeleton",
    "BodySlide and Outfit Studio -",
    "Caliente's Beautiful Bodies Enhancer -CBBE-",
    "Sam BodySlide Output",
    "MTM 3B OCBP - OCBPC Physics and Collision Preset",
    "Toned and Shapely Body for CBBE and 3BA Vagina Add-on",
    "RealVagCBBE",
    "Muscular Body",
    "ADDON_Body_Textures_With_Detailed_Vagina",
    "BodyTalk",
    # Looks
    "Younger Male Face Texture",
    "BodyTriangleEnhancer",
    "Beautiful Female Settlers",
    "Beautiful Female Enemies V. 2.0",
    "MyCleanRaiders_CBBE1.0",
    "Lots More Male Hairstyles v. 1.21 - Fix",
    "Lots More Female Hairstyles v. 1.33",
    "Ponytail Hairstyles by Azar - BA2",
    "Looks Menu Customization Compendium",
    "LooksMenu v1-7-0-3",
    "LooksMenu v1-7-0-2",
    # AAF engine + helpers
    "Advanced Animation Framework",
    "SexAttributes",
    "AAF_FamilyPlanningEnhanced_",
    "AAF_SEU_V",
    "AAF_SCRS",
    # Ultimate/Extended: UAP extras (Override files hidden separately)
    "Extended AAF Patch",
    "Ultimate AAF Patch",
    # Animation packs (assets)
    "Atomic Lust",
    "AAF Vanilla-Kinky-Creatures Sex Animation Themes",
    "Four-Play Animations by Crazy6987",
    "FO4 Animations by Leito",
    "Animated_Fannies__",
    "SavageCabbages Animation Pack",
    "BP70 Fallout 4 Sex Animations 2.3",
    "SAM Enhanced Animations",
    "RZF4S_",
    # FX layers (animationData / overlays) — below One Patch for positionData
    "Dynamic Cumshots",
    "CumOverlays v",
    "AAF patches for Leito and Crazy animations",  # actually CumNWealth overlays
    "Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0",
    # One Patch MUST beat SquirtCum + packs on shared *positionData*
    "AAF - The One Patch to Bang Them All",
    # World / NPC
    "Commonwealth Moisturizer",
    "LLFP",
    "Nude Male Cut Erect",
    "Hookers of the Commonwealth (HotC) - v.0.99h",
    # Armor
    "NanoSuit",
    "Black and Red Vaultsuit_FULL_Male and Female",
    "Black Road Leathers",
    "Cronen Squall - Main",
    "JensenArmor",
    "Stealth Glasses",
    "File C - HN66_SiriusArmor_3.20_Main mod files",
    # Weapons
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
    "Weapons Level List Patches",
    # Settlements
    "Clean My Settlement Redux - NextGen REBUILT",
    "Sanctuary Estates",
    "Fusion City Rising v.1.0",
    "Generator Fixerupper",
    "Better Generators (x3)",
    "Very Small Generators (1000)",
    "Deployable Turret Pack 2",
    "Scrap scrap 1.1",
]


def hide_file(path: Path) -> str:
    if not path.exists():
        hidden = Path(str(path) + ".mohidden")
        if hidden.exists():
            return f"already hidden {path.name}"
        return f"missing {path.name}"
    dest = Path(str(path) + ".mohidden")
    if dest.exists():
        dest.unlink()
    path.rename(dest)
    return f"hid {path.name}"


def hide_conflicts() -> list[str]:
    notes: list[str] = []
    # ZeX must supply human skeleton
    am = MODS / "Atomic Muscle" / "Meshes" / "Actors" / "Character" / "CharacterAssets"
    for name in (
        "skeleton.nif",
        "skeleton.hkx",
        "skeleton_faceBones.nif",
        "skeleton_female_faceBones.nif",
    ):
        notes.append("AtomicMuscle: " + hide_file(am / name))

    # Keep Ultimate UAP content; stop Override from nulling original position IDs
    uap = MODS / "Ultimate AAF Patch" / "AAF"
    if uap.exists():
        for path in sorted(uap.glob("*Override*positionData*.xml")):
            notes.append("Ultimate: " + hide_file(path))
        hide_crazy = uap / "Hide-Four-Play_Animations_by_Crazy_MM_positionData.xml"
        if hide_crazy.exists() or Path(str(hide_crazy) + ".mohidden").exists():
            notes.append("Ultimate: " + hide_file(hide_crazy))
    return notes


def ensure_squirt_offset_fixed() -> str:
    squirt = (
        MODS
        / "Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0"
        / "AAF"
    )
    fixed = []
    for name in ("Atomic Lust_positionData.xml", "Atomic Lust_positionData2.xml"):
        path = squirt / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if 'offset="0,50,180"' in text:
            bak = path.with_suffix(path.suffix + ".bak_before_offset_fix")
            if not bak.exists():
                shutil.copy2(path, bak)
            path.write_text(text.replace(' offset="0,50,180"', "").replace('offset="0,50,180"', ""), encoding="utf-8")
            fixed.append(name)
    return "re-fixed offset in " + ", ".join(fixed) if fixed else "SquirtCum Atomic Lust offsets OK"


def write_modlist(installed: set[str], prior_enabled: dict[str, bool]) -> None:
    stars: list[str] = []
    if MODLIST.exists():
        for line in MODLIST.read_text(encoding="utf-8").splitlines():
            if line.startswith("*"):
                stars.append(line)

    ordered: list[str] = []
    seen: set[str] = set()
    for name in ORDER_LOW_TO_HIGH:
        if name in installed and name not in seen:
            ordered.append(name)
            seen.add(name)
    leftovers = sorted(installed - seen)
    ordered.extend(leftovers)

    shutil.copy2(MODLIST, MODLIST.with_suffix(".txt.bak_before_compat_align"))

    lines = ["# This file was automatically generated by Mod Organizer."]
    # high priority first
    for name in reversed(ordered):
        if name in DISABLE:
            prefix = "-"
        else:
            # default enable; preserve prior disable only for Nude Male if user had it off
            if name == "Nude Male Cut Erect" and prior_enabled.get(name) is False:
                prefix = "-"
            else:
                prefix = "+"
        lines.append(f"{prefix}{name}")
    lines.extend(stars)
    MODLIST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ordered


def sync_mod_data(ordered: list[str], enabled: dict[str, bool]) -> None:
    data = {}
    if MOD_DATA.exists():
        data = json.loads(MOD_DATA.read_text(encoding="utf-8-sig"))
    data.pop("example", None)
    for idx, name in enumerate(ordered):
        entry = data.get(name, {})
        entry["priority"] = idx
        entry["enabled"] = enabled.get(name, True)
        data[name] = entry
    for key in list(data.keys()):
        if key not in enabled:
            del data[key]
    MOD_DATA.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def verify() -> None:
    print("\n=== Enabled AAF/body flags ===")
    for line in MODLIST.read_text(encoding="utf-8").splitlines():
        if any(
            k in line
            for k in (
                "Atomic Lust",
                "One Patch",
                "Ultimate",
                "Extended",
                "SquirtCum",
                "Patch for animations",
                "Leito",
                "ZeX",
                "Atomic Muscle",
                "BodyTalk",
                "LooksMenu",
            )
        ):
            print(line)

    print("\n=== File winners (enabled) ===")
    checks = [
        ("Atomic Lust_positionData.xml", "AAF"),
        ("Atomic Lust_animationData.xml", "AAF"),
        ("Leito_positionData.xml", "AAF"),
        ("skeleton.nif", "Meshes/Actors/Character/CharacterAssets"),
    ]
    for fname, sub in checks:
        for line in MODLIST.read_text(encoding="utf-8").splitlines():
            if line.startswith("+"):
                name = line[1:]
                path = MODS / name / Path(sub) / fname
                # also check without Path quirks
                path = MODS / name / sub.replace("/", "\\") / fname if "\\" not in sub and "/" in sub else MODS / name / sub / fname
                if sub == "AAF":
                    path = MODS / name / "AAF" / fname
                else:
                    path = MODS / name / "Meshes" / "Actors" / "Character" / "CharacterAssets" / fname
                if path.exists():
                    print(f"{fname} <= {name}")
                    break

    ov = MODS / "Ultimate AAF Patch" / "AAF" / "UAP_Atomic_Lust_Override-positionData.xml"
    print(f"Ultimate Override active? {ov.exists()} (want False)")
    sk = MODS / "Atomic Muscle" / "Meshes" / "Actors" / "Character" / "CharacterAssets" / "skeleton.nif"
    print(f"Atomic Muscle skeleton active? {sk.exists()} (want False)")


def main() -> None:
    installed = {p.name for p in MODS.iterdir() if p.is_dir()}
    prior: dict[str, bool] = {}
    if MODLIST.exists():
        for line in MODLIST.read_text(encoding="utf-8").splitlines():
            if line[:1] in "+-" and len(line) > 1:
                prior[line[1:]] = line[0] == "+"

    print("1) Hide conflicting FILES (mods stay enabled)")
    for n in hide_conflicts():
        print("  ", n)

    print("2) Ensure SquirtCum position offsets safe")
    print("  ", ensure_squirt_offset_fixed())

    print("3) Write complementary modlist (all packs on)")
    ordered = write_modlist(installed, prior)
    enabled = {
        n: (n not in DISABLE and not (n == "Nude Male Cut Erect" and prior.get(n) is False))
        for n in ordered
    }
    for n in DISABLE:
        if n in enabled:
            enabled[n] = False

    print("4) Sync mod_data.json")
    sync_mod_data(ordered, enabled)

    verify()
    print(
        "\nDone. Close Fallout 4 + restart Mod Organizer so it reloads the list.\n"
        "All animation packs stay ON. Conflicts resolved by order + file hides only."
    )


if __name__ == "__main__":
    main()
