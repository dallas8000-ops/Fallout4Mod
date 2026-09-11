"""Flask web UI. Same routes as before; all mod-data logic now goes through
core/ instead of duplicating server.py's own load/save/categorize.

Security note (flagged in the review, fixed here): this used to run with
`app.run(host='0.0.0.0', port=5000, debug=True)`. Binding 0.0.0.0 exposes
the dev server to the whole local network, and Werkzeug's debug=True mode
serves an interactive Python console on any unhandled exception -- reachable
by anyone who can hit that port, with no auth. That's remote code execution
on this machine if it's ever on a shared network (coffee shop wifi, a
dorm/office LAN, a VPN that routes other clients through it). Defaults are
now 127.0.0.1 (localhost-only) with debug off; override explicitly via
env vars only if you understand the exposure.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

from mod_manager.core import catalog, config, loadorder_io, mod_data_store  # noqa: E402

app = Flask(__name__, static_folder="static")


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/mods", methods=["GET"])
def get_mods():
    installed = mod_data_store.scan_installed_mods()
    mod_data = mod_data_store.load()
    mod_data, changed = mod_data_store.sync_with_installed(mod_data, installed)

    entries = catalog.build_catalog(installed)
    for entry in entries:
        mod_data.setdefault(entry.name, {})
        # Priority is user-owned once PUT /mods/<name> below tags it
        # priority_source="manual" -- never touch it again after that. Any
        # other entry -- newly seeded, or a legacy one with no
        # priority_source key at all -- is catalog-owned and kept in sync
        # with catalog.py's current order on every read, so a corrected
        # catalog actually takes effect instead of being frozen at
        # whatever value was seeded before the correction (see resolver.py
        # for the full rationale -- this mirrors its logic).
        if mod_data[entry.name].get("priority_source") != "manual":
            if mod_data[entry.name].get("priority") != entry.order:
                mod_data[entry.name]["priority"] = entry.order
                changed = True
            if mod_data[entry.name].get("priority_source") != "catalog":
                mod_data[entry.name]["priority_source"] = "catalog"
                changed = True
        if mod_data[entry.name].get("category") != entry.category:
            mod_data[entry.name]["category"] = entry.category
            changed = True
        if mod_data[entry.name].get("tier") != entry.tier:
            mod_data[entry.name]["tier"] = entry.tier
            changed = True

    for older, newer in catalog.DISABLE_IF_PRESENT.items():
        if older in mod_data and newer in mod_data:
            if mod_data[older].get("enabled", True):
                mod_data[older]["enabled"] = False
                changed = True
            if not mod_data[newer].get("enabled", True):
                mod_data[newer]["enabled"] = True
                changed = True

    if changed:
        mod_data_store.save(mod_data)

    def sort_key(name: str):
        entry = mod_data[name]
        return (entry.get("priority", catalog.order_index(name)), name)

    from collections import OrderedDict

    ordered = sorted(mod_data.keys(), key=sort_key)
    return jsonify(OrderedDict((m, mod_data[m]) for m in ordered))


@app.route("/mods/<mod_name>", methods=["PUT"])
def edit_mod(mod_name):
    mod_data = mod_data_store.load()
    if mod_name not in mod_data:
        return jsonify({"error": "Mod not found"}), 404
    data = request.json or {}
    for field in ("category", "priority", "enabled"):
        if field in data:
            mod_data[mod_name][field] = data[field]
    if "priority" in data:
        # A human just set this explicitly -- protect it from ever being
        # silently resynced back to the catalog value (see get_mods() and
        # core/resolver.py).
        mod_data[mod_name]["priority_source"] = "manual"
    mod_data_store.save(mod_data)
    return jsonify(mod_data[mod_name])


@app.route("/mods/<mod_name>/toggle", methods=["POST"])
def toggle_mod(mod_name):
    mod_data = mod_data_store.load()
    if mod_name not in mod_data:
        return jsonify({"error": "Mod not found"}), 404
    mod_data[mod_name]["enabled"] = not mod_data[mod_name].get("enabled", True)
    mod_data_store.save(mod_data)
    return jsonify({"mod": mod_name, "enabled": mod_data[mod_name]["enabled"]})


@app.route("/save_loadorder", methods=["POST"])
def save_loadorder_endpoint():
    mod_data = mod_data_store.load()
    ordered = sorted(
        mod_data.keys(),
        key=lambda m: (mod_data[m].get("priority", catalog.order_index(m)), m),
    )
    backup = loadorder_io.write_modlist(ordered, mod_data)
    mod_data_store.save(mod_data)
    return jsonify({"status": "ok", "count": len(ordered), "backup": str(backup) if backup else None})


if __name__ == "__main__":
    host = os.environ.get("MOD4_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("MOD4_SERVER_PORT", "5000"))
    debug = os.environ.get("MOD4_SERVER_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
