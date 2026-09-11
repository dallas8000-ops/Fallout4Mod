
# Fallout 4 Mod Manager

Load-order tooling for a Mod Organizer 2 profile, plus a deterministic
diagnostics engine that turns a symptom ("actors facing the wrong way",
"crash on launch") into ranked, evidence-backed findings and, where the
fix is already policy, an `--apply` that performs it.

See `../MIGRATION_NOTES.md` (project root) for why this project was
restructured and what changed if you used the older per-script tools.

## First-time setup after pulling this version

```
python ../migrate_legacy.py            # dry run: see what it would do
python ../migrate_legacy.py --apply    # reconcile mod_data.json, archive old scripts
```

## Everyday use

CLI (interactive, same as before):
```
python main.py
```

Desktop GUI:
```
python mod_manager_gui.py
```

Web UI (now binds to localhost only by default -- see server.py's
docstring for why the old `0.0.0.0` + `debug=True` combination was a real
vulnerability, not just noise):
```
python server.py
```

## Diagnostics

```
python -m mod_manager.diagnostics.cli list-symptoms
python -m mod_manager.diagnostics.cli report --symptom ctd_on_launch
python -m mod_manager.diagnostics.cli report --symptom animation_misalign --apply
```

`--apply` only executes findings the current resolution policy already
covers (`core/resolution_policy.py`) -- file hides, `.ini` settings, and
the diagnosed offset-bug text patch, each with an automatic timestamped
backup first. Findings marked "manual" (a missing master, an inactive
plugin, too many active plugins) are never auto-applied; they need a
decision only you can make.

For crash-to-desktop symptoms, this engine checks plugin masters/activation
and known duplicate pairs, then points you at
[CLASSIC](https://www.nexusmods.com/fallout4/mods/56255) for the actual
crash-log analysis -- it isn't reimplemented here on purpose (see
`MIGRATION_NOTES.md`'s "Prior art check"). CLASSIC isn't installed on this
machine yet; grab it separately if you haven't.

`ctd_ingame` additionally checks AAF's animation-scene-crash surface
directly off disk (see `MIGRATION_NOTES.md`'s "AAF crash-on-animation-start
findings folded in" for the real-world bug this came from):
`xmlutility.ini`'s `UseSignatures` flag (auto-fixable via `--apply`), a
missing `aaf.xsd`, 0-byte AAF content XML files, and AAF `.xml` files
shipped by more than one mod -- a real load-order collision this engine
can point at but won't silently pick a winner for.

## MO2 paths

Defaults point at this machine's install (`C:\Users\Ray\AppData\Local\...`).
Override any of them with an environment variable if you ever run this
against a different profile or machine -- see `core/config.py` for the
full list (`MOD4_MO2_ROOT`, `MOD4_MO2_MODS`, `MOD4_MO2_MODLIST`, etc.).

## Tests

```
pip install pytest
pytest ../tests
```

Every test runs against a fabricated MO2 install under `tmp_path` --
nothing in the suite touches your real game folder.
