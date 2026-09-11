"""Flask endpoint tests for the priority_source (catalog vs. manual) model.

server.py's /mods GET seeds/resyncs a catalog-owned priority the same way
core/resolver.py's apply() does; PUT /mods/<name> is the point a human's
edit becomes permanently protected. These tests exercise the actual Flask
routes (via Flask's test client) rather than re-deriving the logic, since
this module has no other coverage and it was the source of the production
bug (tied/duplicate priorities in the web UI) reported against a real
install.
"""
from __future__ import annotations

from helpers import make_mod_folder

from mod_manager import server
from mod_manager.core import catalog, config, mod_data_store


def _client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def test_get_mods_seeds_catalog_priority_for_new_mod(patch_config):
    make_mod_folder(patch_config.mods, "Buffout 4")
    client = _client()

    resp = client.get("/mods")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["Buffout 4"]["priority"] == catalog.order_index("Buffout 4")
    assert body["Buffout 4"]["priority_source"] == "catalog"


def test_put_priority_tags_manual_and_survives_a_later_get(patch_config):
    make_mod_folder(patch_config.mods, "Buffout 4")
    client = _client()
    client.get("/mods")  # seed it first, as the real UI does on load

    put_resp = client.put("/mods/Buffout 4", json={"priority": 999999})
    assert put_resp.status_code == 200
    assert put_resp.get_json()["priority_source"] == "manual"

    # A later GET (e.g. the user reloading the page) must not resync this
    # back to the catalog value -- that's the exact bug this model fixes.
    get_resp = client.get("/mods")
    body = get_resp.get_json()
    assert body["Buffout 4"]["priority"] == 999999
    assert body["Buffout 4"]["priority_source"] == "manual"


def test_get_mods_resyncs_stale_untagged_priority(patch_config):
    # Regression test for the production bug: a priority written before
    # priority_source existed (or under a stale catalog order) must be
    # resynced on the next GET, not frozen forever.
    make_mod_folder(patch_config.mods, "Buffout 4")
    client = _client()
    client.get("/mods")

    mod_data = mod_data_store.load(config.MOD_DATA_PATH)
    correct_priority = mod_data["Buffout 4"]["priority"]
    mod_data["Buffout 4"]["priority"] = correct_priority + 500
    del mod_data["Buffout 4"]["priority_source"]
    mod_data_store.save(mod_data, config.MOD_DATA_PATH)

    resp = client.get("/mods")

    body = resp.get_json()
    assert body["Buffout 4"]["priority"] == correct_priority
    assert body["Buffout 4"]["priority_source"] == "catalog"


def test_put_category_alone_does_not_tag_manual_priority(patch_config):
    # Editing category only (no priority in the request body) must not
    # accidentally mark this mod's priority as manually-owned.
    make_mod_folder(patch_config.mods, "Buffout 4")
    client = _client()
    client.get("/mods")

    resp = client.put("/mods/Buffout 4", json={"category": "My Custom Category"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["category"] == "My Custom Category"
    assert body.get("priority_source") == "catalog"
