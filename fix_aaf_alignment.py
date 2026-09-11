"""Force-fix AAF actor misalignment causes that modlist order alone may not fix.

1) Hide Atomic Muscle's human skeleton files (rename .nif -> .nif.disabled)
   so ZeX always wins even if MO2 priority is wrong.
2) Disable conflicting AAF position-patch mods in modlist.txt.
3) Ensure Ultimate AAF Patch + Leito/Crazy patch stay enabled and high.
4) Optionally set AAF scale_actors_for_animations = true for height mismatch.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

MO2 = Path(r"C:\Users\Ray\AppData\Local\ModOrganizer\Fallout 4")
MODS = MO2 / "mods"
MODLIST = MO2 / "profiles" / "Default" / "modlist.txt"
MOD_DATA = Path(r"C:\Software Projects\Fallout4Mod\mod_manager\mod_data.json")
AAF_SETTINGS = MODS / "Advanced Animation Framework" / "AAF" / "AAF_settings.ini"

# Mods that rewrite positionData and fight each other
DISABLE_MODS = {
    "AAF - The One Patch to Bang Them All",
    "Extended AAF Patch",
    "Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0",
    "LooksMenu v1-7-0-2",
    "Mod Configuration Menu 1.43",
    "Address Library",
}

MUST_ENABLE = {
    "Ultimate AAF Patch",
    "AAF patches for Leito and Crazy animations",
    "Advanced Animation Framework",
    "ZeX - ZaZ Extended Skeleton",
    "BodyTalk",
    "Address Library - All In One",
    "LooksMenu v1-7-0-3",
    "Mod Configuration Menu 1.11.221",
}

# Hide these files inside Atomic Muscle so they cannot override ZeX
ATOMIC_MUSCLE_HIDE = [
    Path("Meshes") / "Actors" / "Character" / "CharacterAssets" / "skeleton.nif",
    Path("Meshes") / "Actors" / "Character" / "CharacterAssets" / "skeleton.hkx",
    Path("Meshes") / "Actors" / "Character" / "CharacterAssets" / "skeleton_faceBones.nif",
    Path("Meshes") / "Actors" / "Character" / "CharacterAssets" / "skeleton_female_faceBones.nif",
]


def hide_atomic_muscle_skeleton() -> list[str]:
    am = MODS / "Atomic Muscle"
    done: list[str] = []
    if not am.exists():
        return ["Atomic Muscle folder missing"]
    for rel in ATOMIC_MUSCLE_HIDE:
        src = am / rel
        dst = Path(str(src) + ".disabled")
        if src.exists():
            if dst.exists():
                dst.unlink()
            src.rename(dst)
            done.append(f"hid {rel}")
        elif dst.exists():
            done.append(f"already hid {rel}")
        else:
            done.append(f"missing {rel}")
    return done


def patch_modlist() -> tuple[int, int]:
    """Rewrite +/- flags; keep order but force enable/disable sets."""
    text = MODLIST.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    disabled = enabled = 0
    for line in lines:
        if line.startswith("#") or line.startswith("*") or not line.strip():
            out.append(line)
            continue
        if line[0] in "+-" and len(line) > 1:
            name = line[1:]
            if name in DISABLE_MODS:
                out.append(f"-{name}")
                disabled += 1
            elif name in MUST_ENABLE:
                out.append(f"+{name}")
                enabled += 1
            else:
                out.append(line)
        else:
            out.append(line)
    # Backup
    bak = MODLIST.with_suffix(".txt.bak_aaf_force")
    bak.write_text(text, encoding="utf-8")
    MODLIST.write_text("\n".join(out) + "\n", encoding="utf-8")
    return disabled, enabled


def reorder_aaf_critical() -> None:
    """Move ZeX/BodyTalk/Ultimate above Atomic Muscle & conflicting patches."""
    text = MODLIST.read_text(encoding="utf-8")
    header: list[str] = []
    managed: list[tuple[str, str]] = []  # (prefix, name)
    stars: list[str] = []

    for line in text.splitlines():
        if line.startswith("#") and not managed and not stars:
            header.append(line)
        elif line.startswith("*"):
            stars.append(line)
        elif line[:1] in "+-" and len(line) > 1:
            managed.append((line[0], line[1:]))
        elif line.startswith("#"):
            header.append(line)
        else:
            if line.strip():
                header.append(line)

    by_name = {name: prefix for prefix, name in managed}
    names = [n for _, n in managed]

    def take(name: str) -> str | None:
        if name in names:
            names.remove(name)
            return name
        return None

    # Rebuild: keep non-critical order, but inject critical block
    critical_low_to_high = [
        "Atomic Muscle",  # low — after hide, textures only
        "ZeX - ZaZ Extended Skeleton",
        "BodyTalk",
        "Advanced Animation Framework",
        "SexAttributes",
        "AAF_FamilyPlanningEnhanced_",
        "AAF_SEU_V",
        "AAF_SCRS",
        "AAF - The One Patch to Bang Them All",
        "Extended AAF Patch",
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
        "AAF patches for Leito and Crazy animations",
        "Ultimate AAF Patch",
    ]

    critical_set = set(critical_low_to_high)
    rest = [n for n in names if n not in critical_set]
    # rest is currently high-priority-first (modlist order). We rebuild full low->high then reverse.

    # Convert current modlist (high first) to low-first for rest:
    rest_low_first = list(reversed(rest))

    # Insert critical block after body foundations if possible, else at end of foundations area.
    # Simpler: put critical_low_to_high as a contiguous low-to-high segment at the
    # start of low-first list (so they end near bottom of file / mid after reverse... wait)

    # modlist file = HIGH priority first.
    # We want HIGH: Ultimate, Leito patch, anim packs... then BodyTalk, ZeX, then Atomic Muscle low.
    high_first_critical = list(reversed(critical_low_to_high))
    # Existing rest already high-first from original file order
    # Place critical block after world/armor/weapons (keep rest as-is) — but splice:
    # Put high_first_critical at a position: after scrap/weapons? Easiest: prepend critical
    # high-first so Ultimate is near TOP — too high vs settlements. Better: insert after
    # first settlement-ish mods.

    # Practical approach: build final high-first as:
    # [all rest that are not critical] but rest already excludes critical.
    # Insert high_first_critical just before ZeX would naturally be... 
    # Put critical block in the middle: after clothing? 

    # Simplest reliable: final = rest (high first) with critical mods removed already,
    # then find index to insert. Insert high_first_critical before "Commonwealth Moisturizer"
    # or at end of rest if not found — NO that puts AAF at bottom (low priority). Wrong.

    # We want Ultimate HIGH. So high_first_critical should be near the top of the file.
    # Put them right after Weapons Level List / settlements? Or right at top after LL patches.

    insert_before = None
    for marker in (
        "Commonwealth Moisturizer",
        "Hookers of the Commonwealth (HotC) - v.0.99h",
        "NanoSuit",
        "Weapons Level List Patches",
    ):
        if marker in rest:
            insert_before = rest.index(marker)
            break

    if insert_before is None:
        # Put critical high-first near top (after first 5 rest entries)
        insert_before = min(5, len(rest))

    final_high_first = rest[:insert_before] + high_first_critical + rest[insert_before:]

    lines = header[:] if header else ["# This file was automatically generated by Mod Organizer."]
    for name in final_high_first:
        prefix = by_name.get(name, "+")
        if name in DISABLE_MODS:
            prefix = "-"
        if name in MUST_ENABLE:
            prefix = "+"
        lines.append(f"{prefix}{name}")
    lines.extend(stars)
    MODLIST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def patch_aaf_settings() -> list[str]:
    """Help mismatched actor heights; keep gender checks."""
    notes: list[str] = []
    if not AAF_SETTINGS.exists():
        return ["AAF_settings.ini not found"]
    raw = AAF_SETTINGS.read_text(encoding="utf-8", errors="replace")
    bak = AAF_SETTINGS.with_suffix(".ini.bak_align")
    if not bak.exists():
        bak.write_text(raw, encoding="utf-8")
        notes.append(f"backed up to {bak.name}")

    def set_key(text: str, key: str, value: str) -> str:
        import re

        pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.M)
        if pattern.search(text):
            return pattern.sub(rf"\g<1>{value}", text, count=1)
        return text

    new = raw
    new = set_key(new, "scale_actors_for_animations", "true")
    # When scale_actors is true, enforce_race_scale can fight it — prefer scale to player
    new = set_key(new, "enforce_race_scale", "false")
    if new != raw:
        AAF_SETTINGS.write_text(new, encoding="utf-8")
        notes.append("set scale_actors_for_animations=true, enforce_race_scale=false")
    else:
        notes.append("AAF_settings.ini unchanged (keys missing?)")
    return notes


def update_mod_data() -> None:
    if not MOD_DATA.exists():
        return
    data = json.loads(MOD_DATA.read_text(encoding="utf-8-sig"))
    for name in DISABLE_MODS:
        if name in data:
            data[name]["enabled"] = False
    for name in MUST_ENABLE:
        if name in data:
            data[name]["enabled"] = True
    MOD_DATA.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def verify() -> None:
    print("\n=== VERIFY skeleton winner ===")
    for line in MODLIST.read_text(encoding="utf-8").splitlines():
        if line.startswith("+"):
            name = line[1:]
            sk = MODS / name / "Meshes" / "Actors" / "Character" / "CharacterAssets" / "skeleton.nif"
            if sk.exists():
                print(f"WINNER: {name}")
                break
    print("\n=== VERIFY AAF patch flags ===")
    for line in MODLIST.read_text(encoding="utf-8").splitlines():
        if any(
            x in line
            for x in (
                "Ultimate AAF",
                "Extended AAF",
                "One Patch",
                "Patch for animations",
                "AAF patches for Leito",
                "Atomic Muscle",
                "ZeX",
                "BodyTalk",
            )
        ):
            print(line)


def main() -> None:
    print("1) Hiding Atomic Muscle skeleton files...")
    for msg in hide_atomic_muscle_skeleton():
        print(f"   {msg}")

    print("2) Reordering AAF-critical mods + force flags...")
    shutil.copy2(MODLIST, MODLIST.with_suffix(".txt.bak_before_force_align"))
    reorder_aaf_critical()
    d, e = patch_modlist()
    print(f"   forced disable touches={d}, enable touches={e}")

    print("3) Patching AAF_settings.ini...")
    for msg in patch_aaf_settings():
        print(f"   {msg}")

    print("4) Updating mod_data.json...")
    update_mod_data()

    verify()
    print("\nDone. Close Fallout 4 + refresh/restart Mod Organizer, then launch.")


if __name__ == "__main__":
    main()
