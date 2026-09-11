"""Shared pytest fixtures: a fabricated MO2 install so nothing in this test
suite ever touches a real game folder. Every test that needs paths gets them
via core.config, monkeypatched to point at a tmp_path tree built here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mod_manager.core import config  # noqa: E402


@pytest.fixture
def mo2_root(tmp_path: Path) -> Path:
    root = tmp_path / "MO2Profile"
    (root / "mods").mkdir(parents=True)
    (root / "profiles" / "Default").mkdir(parents=True)
    return root


@pytest.fixture
def patch_config(monkeypatch, mo2_root: Path, tmp_path: Path):
    """Point every core.config path at the fixture tree. Returns a small
    namespace of the paths for convenience in tests.
    """
    mo2_mods = mo2_root / "mods"
    modlist = mo2_root / "profiles" / "Default" / "modlist.txt"
    plugins = mo2_root / "profiles" / "Default" / "plugins.txt"
    loadorder = mo2_root / "profiles" / "Default" / "loadorder.txt"
    mod_data_path = tmp_path / "mod_data.json"
    backup_dir = tmp_path / "backups"

    monkeypatch.setattr(config, "MO2_MODS", mo2_mods)
    monkeypatch.setattr(config, "MO2_MODLIST", modlist)
    monkeypatch.setattr(config, "MO2_PLUGINS", plugins)
    monkeypatch.setattr(config, "MO2_LOADORDER", loadorder)
    monkeypatch.setattr(config, "MOD_DATA_PATH", mod_data_path)
    monkeypatch.setattr(config, "BACKUP_DIR", backup_dir)

    class Paths:
        pass

    p = Paths()
    p.mo2_root = mo2_root
    p.mods = mo2_mods
    p.modlist = modlist
    p.plugins = plugins
    p.loadorder = loadorder
    p.mod_data = mod_data_path
    p.backups = backup_dir
    return p
