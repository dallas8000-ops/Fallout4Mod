import json

from mod_manager.core import mod_data_store


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "mod_data.json"
    data = {"Buffout 4": {"category": "Core", "priority": 1, "enabled": True, "tier": 2}}
    mod_data_store.save(data, path)
    loaded = mod_data_store.load(path)
    assert loaded == data


def test_save_is_atomic_no_tmp_file_left_behind(tmp_path):
    path = tmp_path / "mod_data.json"
    mod_data_store.save({"A": {"enabled": True}}, path)
    leftovers = list(tmp_path.glob(".mod_data.*.tmp"))
    assert leftovers == []


def test_load_tolerates_bom(tmp_path):
    path = tmp_path / "mod_data.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"A": {"enabled": True}}).encode("utf-8"))
    loaded = mod_data_store.load(path)
    assert loaded == {"A": {"enabled": True}}


def test_load_missing_file_returns_empty_dict(tmp_path):
    assert mod_data_store.load(tmp_path / "does_not_exist.json") == {}


def test_sync_with_installed_adds_new_mods_with_catalog_defaults():
    data, changed = mod_data_store.sync_with_installed({}, {"Buffout 4"})
    assert changed is True
    assert data["Buffout 4"]["category"] == "Body Talk & Physics Actors"  # see test_catalog.py note
    assert data["Buffout 4"]["enabled"] is True


def test_sync_with_installed_drops_missing_by_default():
    data = {"Old Removed Mod": {"category": "Other", "priority": 5, "enabled": True}}
    data, changed = mod_data_store.sync_with_installed(data, {"Buffout 4"})
    assert "Old Removed Mod" not in data
    assert "Buffout 4" in data
    assert changed is True


def test_sync_with_installed_can_keep_missing_when_asked():
    data = {"Old Removed Mod": {"category": "Other", "priority": 5, "enabled": True}}
    data, changed = mod_data_store.sync_with_installed(data, {"Buffout 4"}, drop_missing=False)
    assert "Old Removed Mod" in data
    assert "Buffout 4" in data


def test_sync_with_installed_backfills_missing_enabled_key():
    data = {"Buffout 4": {"category": "Core", "priority": 1}}
    data, changed = mod_data_store.sync_with_installed(data, {"Buffout 4"})
    assert data["Buffout 4"]["enabled"] is True
    assert changed is True
