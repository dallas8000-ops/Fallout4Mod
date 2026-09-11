from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from apply_optimal_load_order import (
    ALWAYS_DISABLE,
    DISABLE_IF_PRESENT,
    MOD_DATA_PATH,
    MO2_MODS,
    MO2_MODLIST,
    build_ordered,
    enabled_map,
    installed_mods,
    load_json,
)


MO2_PLUGINS = MO2_MODLIST.with_name("plugins.txt")


CONFLICT_GROUPS: list[tuple[str, list[str], str]] = [
    (
        "Skeleton / body rig",
        [
            "Atomic Muscle",
            "ZeX - ZaZ Extended Skeleton",
            "BodySlide and Outfit Studio -",
            "BodyTalk",
        ],
        "Keep the scripted order: Atomic Muscle -> ZeX -> BodySlide -> BodyTalk. BodyTalk should win the male skeleton and morph overrides.",
    ),
    (
        "AAF position data",
        [
            "AAF - The One Patch to Bang Them All",
            "Extended AAF Patch",
            "Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0",
            "Ultimate AAF Patch",
        ],
        "Keep Ultimate AAF Patch as the only active position-data source. The older packs are disabled when present.",
    ),
    (
        "Core duplicate replacements",
        [
            "Address Library",
            "Address Library - All In One",
            "Mod Configuration Menu 1.43",
            "Mod Configuration Menu 1.11.221",
            "LooksMenu v1-7-0-2",
            "LooksMenu v1-7-0-3",
        ],
        "Prefer the newer replacement in each pair and disable the older duplicate.",
    ),
]


def load_installed_or_known_mods() -> set[str]:
    installed = installed_mods()
    if installed:
        return installed
    mod_data = load_json(MOD_DATA_PATH)
    return set(mod_data.keys())


def read_plugins() -> list[tuple[str, bool]]:
    if not MO2_PLUGINS.exists():
        return []
    plugins: list[tuple[str, bool]] = []
    for line in MO2_PLUGINS.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        active = line.startswith("*")
        plugin_name = line[1:] if active else line
        plugins.append((plugin_name, active))
    return plugins


def map_plugin_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    if not MO2_MODS.exists():
        return sources
    for mod_dir in MO2_MODS.iterdir():
        if not mod_dir.is_dir():
            continue
        for plugin_file in mod_dir.rglob("*.esp"):
            sources.setdefault(plugin_file.name, mod_dir.name)
        for plugin_file in mod_dir.rglob("*.esm"):
            sources.setdefault(plugin_file.name, mod_dir.name)
        for plugin_file in mod_dir.rglob("*.esl"):
            sources.setdefault(plugin_file.name, mod_dir.name)
    return sources


def describe_conflicts(installed: set[str], enabled: dict[str, bool]) -> list[str]:
    lines: list[str] = []

    for older, newer in DISABLE_IF_PRESENT.items():
        if older in installed and newer in installed:
            lines.append(f"- {older} conflicts with {newer}; keep {newer} and disable {older}.")

    for name in sorted(ALWAYS_DISABLE):
        if name in installed:
            lines.append(f"- {name} is intentionally disabled when present because it overlaps with the resolved AAF stack.")

    for group_name, members, resolution in CONFLICT_GROUPS:
        present = [name for name in members if name in installed]
        if len(present) >= 2:
            lines.append(f"- {group_name}: {', '.join(present)}")
            lines.append(f"  Resolution: {resolution}")

    if not lines:
        lines.append("- No known ordering conflicts were detected from the installed mod names.")

    disabled = [name for name, is_enabled in enabled.items() if not is_enabled]
    if disabled:
        lines.append("")
        lines.append("Disabled by the resolver:")
        for name in disabled:
            lines.append(f"- {name}")

    return lines


def describe_plugins() -> list[str]:
    plugins = read_plugins()
    if not plugins:
        return ["- plugins.txt was not found, so plugin activation could not be checked."]

    sources = map_plugin_sources()
    inactive = [name for name, active in plugins if not active]
    lines: list[str] = []
    if not inactive:
        lines.append("- All listed plugins in plugins.txt are active.")
        return lines

    lines.append("- Inactive plugins in plugins.txt:")
    for plugin_name in inactive:
        source_mod = sources.get(plugin_name)
        if source_mod:
            lines.append(f"  - {plugin_name} (from {source_mod})")
        else:
            lines.append(f"  - {plugin_name}")
    lines.append("  Resolution: enable the plugin in MO2's Plugins tab. DLC being installed does not automatically activate a separate .esp/.esm plugin.")
    return lines


def group_by_category(ordered: list[str], mod_data: dict[str, dict]) -> list[tuple[str, list[str]]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for name in ordered:
        category = mod_data.get(name, {}).get("category", "Uncategorized")
        grouped[category].append(name)
    category_order = sorted(grouped.keys(), key=lambda cat: (mod_data.get(next((n for n in ordered if mod_data.get(n, {}).get("category", "Uncategorized") == cat), ordered[0]), {}).get("tier", 99), cat))
    return [(category, grouped[category]) for category in category_order]


def main() -> None:
    installed = load_installed_or_known_mods()
    mod_data = load_json(MOD_DATA_PATH)
    ordered = build_ordered(installed)
    enabled = enabled_map(ordered, mod_data)

    print(f"Checked {len(ordered)} mods from {MO2_MODS if MO2_MODS.exists() else MOD_DATA_PATH}")
    print("")
    print("Detected conflicts and resolutions:")
    for line in describe_conflicts(installed, enabled):
        print(line)

    print("")
    print("Plugin activation check:")
    for line in describe_plugins():
        print(line)

    print("")
    print("Optimal sequence (lowest priority first; later entries override earlier ones):")
    for index, name in enumerate(ordered, 1):
        entry = mod_data.get(name, {})
        category = entry.get("category", "Uncategorized")
        priority = entry.get("priority", "?")
        state = "enabled" if enabled.get(name, True) else "disabled"
        print(f"{index:>3}. {name} [{category}] priority={priority} {state}")

    print("")
    print("Category groupings:")
    for category, names in group_by_category(ordered, mod_data):
        print(f"- {category}")
        for name in names:
            print(f"  - {name}")


if __name__ == "__main__":
    main()