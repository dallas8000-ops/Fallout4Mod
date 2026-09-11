"""Interactive CLI: list installed mods, edit category/priority/enabled,
write MO2's modlist.txt.

Root-cause note: this used to resolve mod_data.json as the bare relative
string "mod_data.json", which meant the file it actually touched depended
on the shell's current directory at the moment you ran `python main.py`
-- NOT on where this project lives. That produced a second, permanently
stale mod_data.json at the repo root that this script alone kept feeding
flat priority=100/category="Uncategorized" defaults into, while
mod_manager/mod_data.json (fed by server.py and the fix scripts) diverged
further every time someone used the web UI or one of the fix scripts
instead. Every entry point now goes through core/config.py, which resolves
MOD_DATA_PATH from this file's own location, never from cwd.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mod_manager.core import catalog, config, loadorder_io, mod_data_store  # noqa: E402


def main() -> None:
    installed = mod_data_store.scan_installed_mods()
    if not installed:
        print(f"Mods folder not found or empty: {config.MO2_MODS}")
        return

    mod_data = mod_data_store.load()
    mod_data, changed = mod_data_store.sync_with_installed(mod_data, installed)
    if changed:
        mod_data_store.save(mod_data)

    def sorted_mods() -> list[str]:
        return sorted(
            installed,
            key=lambda m: (
                mod_data[m].get("priority", catalog.order_index(m)),
                mod_data[m].get("category", config.DEFAULT_CATEGORY),
                m,
            ),
        )

    ordered = sorted_mods()
    loadorder_io.write_modlist(ordered, mod_data)

    print("Mods (sorted by priority, then category):")
    for idx, mod in enumerate(ordered, 1):
        entry = mod_data[mod]
        print(
            f"{idx}. {mod} [Category: {entry.get('category')}, "
            f"Priority: {entry.get('priority')}, Enabled: {'Yes' if entry.get('enabled', True) else 'No'}]"
        )

    while True:
        print("\nOptions:")
        print("  [E]dit a mod's category/priority")
        print("  [T]oggle enable/disable a mod")
        print("  [Q]uit")
        choice = input("Choose an option (E/T/Q): ").strip().lower()
        if choice == "q":
            break
        elif choice == "e":
            try:
                sel = int(input(f"Enter mod number (1-{len(ordered)}): "))
                if not (1 <= sel <= len(ordered)):
                    print("Invalid number.")
                    continue
                mod = ordered[sel - 1]
                print(f"Selected: {mod}")
                new_cat = input(f"Enter new category (current: {mod_data[mod]['category']}): ").strip()
                if new_cat:
                    mod_data[mod]["category"] = new_cat
                new_prio = input(f"Enter new priority (current: {mod_data[mod]['priority']}): ").strip()
                if new_prio:
                    try:
                        mod_data[mod]["priority"] = int(new_prio)
                        # Protect this from ever being silently resynced back
                        # to the catalog value (see core/resolver.py).
                        mod_data[mod]["priority_source"] = "manual"
                    except ValueError:
                        print("Invalid priority, must be an integer.")
                mod_data_store.save(mod_data)
                print(f"Updated {mod}.")
            except (ValueError, IndexError) as exc:
                print(f"Error: {exc}")
        elif choice == "t":
            try:
                sel = int(input(f"Enter mod number (1-{len(ordered)}): "))
                if not (1 <= sel <= len(ordered)):
                    print("Invalid number.")
                    continue
                mod = ordered[sel - 1]
                mod_data[mod]["enabled"] = not mod_data[mod].get("enabled", True)
                print(f"{'Enabled' if mod_data[mod]['enabled'] else 'Disabled'} '{mod}'.")
                mod_data_store.save(mod_data)
            except (ValueError, IndexError) as exc:
                print(f"Error: {exc}")
        else:
            print("Unknown option.")

        ordered = sorted_mods()
        loadorder_io.write_modlist(ordered, mod_data)


if __name__ == "__main__":
    main()
