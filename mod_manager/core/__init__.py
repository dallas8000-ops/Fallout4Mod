"""Canonical core for the Fallout 4 mod manager.

Every entry point (CLI, Flask server, Tk GUI, diagnostics engine) reads and
writes mod state through this package ONLY. Do not re-implement load/save/
order logic in a top-level script again -- that duplication is what caused
the two mod_data.json files to drift out of sync (see MIGRATION_NOTES.md).
"""
