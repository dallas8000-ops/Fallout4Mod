"""Single source of truth for every filesystem path this project touches.

Root cause this file fixes: main.py, mod_manager_gui.py and set_mod_priorities.py
resolved MOD_DATA_PATH as the bare relative string "mod_data.json" (or
"mod_manager/mod_data.json"), which means the actual file touched depended on
the *current working directory of the shell that launched Python* -- not on
where the project lives. Two physical files (repo root and mod_manager/)
existed and silently diverged for months because of this. See
MIGRATION_NOTES.md for the forensic detail.

All paths below are resolved from THIS file's location, never from cwd.
Every MO2 path is also overridable via environment variable so the test
suite (and any future machine) never has to hardcode "C:\\Users\\Ray\\...".
"""
from __future__ import annotations

import os
from pathlib import Path

# mod_manager/core/config.py -> mod_manager/core -> mod_manager -> <project root>
PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = PACKAGE_DIR.parent

# ---------------------------------------------------------------------------
# The ONE mod_data.json. Every legacy script pointed at a different path;
# this is now the only path any code in this project is allowed to write.
# ---------------------------------------------------------------------------
MOD_DATA_PATH = Path(
    os.environ.get("MOD4_MOD_DATA_PATH", str(PACKAGE_DIR / "mod_data.json"))
)

# ---------------------------------------------------------------------------
# Mod Organizer 2 paths. Defaults match what every legacy script hardcoded
# for this install; override with env vars for testing or another machine.
# ---------------------------------------------------------------------------
MO2_ROOT = Path(
    os.environ.get(
        "MOD4_MO2_ROOT",
        r"C:\Users\Ray\AppData\Local\ModOrganizer\Fallout 4",
    )
)
MO2_PROFILE = os.environ.get("MOD4_MO2_PROFILE", "Default")

MO2_MODS = Path(os.environ.get("MOD4_MO2_MODS", str(MO2_ROOT / "mods")))
MO2_MODLIST = Path(
    os.environ.get(
        "MOD4_MO2_MODLIST", str(MO2_ROOT / "profiles" / MO2_PROFILE / "modlist.txt")
    )
)
MO2_PLUGINS = Path(
    os.environ.get(
        "MOD4_MO2_PLUGINS", str(MO2_ROOT / "profiles" / MO2_PROFILE / "plugins.txt")
    )
)
MO2_LOADORDER = Path(
    os.environ.get(
        "MOD4_MO2_LOADORDER",
        str(MO2_ROOT / "profiles" / MO2_PROFILE / "loadorder.txt"),
    )
)

# No CRASH_LOGS_DIR here. An earlier version of this file pointed at Buffout
# 4's crash-log output for a custom parser; the parser was removed after
# checking prior art and finding CLASSIC (github.com/GuidanceOfGrace/
# CLASSIC-Fallout4) already does that job with a real known-issue database
# instead of two regexes. diagnostics/rules.py points to it directly.

# Rotating backups for anything this project overwrites in place.
BACKUP_DIR = Path(
    os.environ.get("MOD4_BACKUP_DIR", str(PACKAGE_DIR / "backups"))
)
BACKUP_KEEP = int(os.environ.get("MOD4_BACKUP_KEEP", "10"))

DEFAULT_CATEGORY = "Uncategorized"
DEFAULT_PRIORITY = 9999
DEFAULT_ENABLED = True
