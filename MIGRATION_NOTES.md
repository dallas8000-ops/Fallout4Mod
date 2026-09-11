# Migration notes: why this refactor, and what changed

## The bug this project actually had

You asked for an "AI" that automates diagnosis when something breaks
(graphics glitches, failure to load). The blocker wasn't a missing AI
layer -- it was that the six existing scripts didn't agree with each other
about what state your mod list was in, so nothing could be built on top of
them safely. Concretely:

**Two `mod_data.json` files, silently diverging.** `main.py`,
`mod_manager_gui.py`, and `set_mod_priorities.py` resolved the path as the
bare string "mod_data.json" (or "mod_manager/mod_data.json") -- a path
relative to whatever directory the shell happened to be in when you ran
`python main.py`. `server.py` and the fix scripts hardcoded the
`mod_manager/` copy. The result: a root-level `mod_data.json` with every
one of its 80 entries at `priority: 100, category: "Uncategorized"` (i.e.
`main.py`'s untouched defaults, never fed any of the tiered ordering work),
sitting right next to the real, tiered `mod_manager/mod_data.json` used by
everything else. **Running `python main.py` from the repo root -- exactly
what the old README told you to do -- would read the flat file, sort
everyone alphabetically, and overwrite `modlist.txt` with it**, destroying
whatever careful order `apply_optimal_load_order.py` or the fix scripts had
just built. That is a fully sufficient explanation for "I fixed it and it
broke again" on its own, with no missing AI required.

**Three incompatible AAF conflict resolutions, none recorded as current.**
`fix_aaf_alignment.py` disabled One Patch/Extended/SquirtCum and kept
Ultimate AAF Patch enabled. `fix_aaf_alignment_v2.py` did the *opposite* --
disabled Ultimate/Extended/SquirtCum, enabled One Patch -- after correctly
root-causing the actual bug (Ultimate's Override XMLs default to
`offset="0,50,180"`, a 180-degree yaw that fights position IDs still
started by HotC/AAF). `align_mods_compatibility.py` then refined that a
third way: keep every mod *enabled*, and hide only the specific offending
files. Nothing recorded which of these three was the last word, so a
later run of `apply_optimal_load_order.py` (which knows about none of
them) could silently reset the whole thing.

**Three incompatible category taxonomies**, one hand-maintained per
script (`server.py`'s `tier_names`/`tier_mods`, `apply_optimal_load_order.py`'s
`CAT_*`/`categorize()`, and no taxonomy at all in the others), none of
which matched what was actually persisted to disk 84 times out of 96 when
checked against `apply_optimal_load_order.py`'s categorizer.

**No actual conflict detection.** `check_mod_conflicts.py` only pattern-
matches mod *folder names* against a hardcoded list of problems already
diagnosed by hand once. It never opens a plugin file, never checks for a
missing master, never reads a crash log, and cannot discover anything it
hasn't already been told about. That is the concrete gap between "checker"
and "diagnoses new issues" that prompted this whole request.

## What changed

- `mod_manager/core/` is now the *only* place that loads or saves
  `mod_data.json`, reads or writes `modlist.txt`/`plugins.txt`, or defines
  mod ordering/categorization. `main.py`, `server.py`, and
  `mod_manager_gui.py` all call into it instead of each keeping their own
  copy.
- `core/catalog.py` is the single canonical order + category table,
  reconciled programmatically (not hand-transcribed) from the two order
  lists (verified identical as sets) and server.py's tier table (verified
  to reproduce all 96 currently-installed mods' live categories exactly,
  with a documented, opt-in fallback for the 16 mods that were falling
  into "Other" with no recourse).
- `core/resolution_policy.py` picks **one** current AAF resolution --
  `align_mods_compatibility.py`'s file-hide approach -- as canonical, with
  the reasoning written down: file hides don't depend on `modlist.txt`
  enable flags, so a later reordering script can't silently undo them the
  way it undid the two disable-based fixes. If you decide differently,
  change it in that one file; do not add a seventh script.
- `core/mod_data_store.py` writes atomically (temp file + `os.replace`) so
  a crash mid-write can't leave a truncated, unparseable `mod_data.json`.
- `core/loadorder_io.py` takes a timestamped, rotating backup (default:
  last 10) before every write, instead of five different fixed backup
  filenames that overwrite each other.
- `mod_manager/diagnostics/` is the new deterministic diagnosis engine:
  symptom -> real signal collection (plugin activation, actual binary
  `.esp`/`.esm` header parsing for missing/inactive masters, file-conflict
  winners) -> ranked findings, each with evidence and either a manual fix
  or a pointer at the resolution policy. No LLM, no network call -- every
  finding traces to a rule you can read in `diagnostics/rules.py`.

## Prior art check (2026-09-08)

Before extending this further I searched for existing tools rather than
assuming the gap was unfilled. Two results changed what's in this repo:

- **CLASSIC** (Crash Log Auto-Scanner And Setup Integrity Checker --
  github.com/GuidanceOfGrace/CLASSIC-Fallout4, 6,300+ endorsements,
  actively maintained, v9.0.0 as of July 2026) already does full Buffout 4
  crash-log analysis: ~250 checks against a real known-issue database,
  FormID lookups, per-crash markdown reports. An earlier version of this
  engine had a two-regex crash-log scanner bolted onto the CTD symptoms.
  It's been removed -- it was a strictly worse reimplementation of a
  maintained tool, not a design decision worth keeping. The CTD symptoms
  now end with a low-confidence pointer at CLASSIC instead
  (`rules.py::_classic_recommendation`). It is **not** currently installed
  on this machine (checked `C:\Modding\MO2` -- no CLASSIC folder there or
  alongside it); it has to be grabbed separately from the link above.
- **xEdit (FO4Edit)** is the actual standard for FormID/record-level
  plugin conflict resolution (last-loaded-wins per record, with full
  sub-record diffing). This project's `file_conflict_winner()` only
  resolves *loose-file* overwrites (textures, meshes, AAF XML) through
  MO2's virtual filesystem layer -- a different, narrower thing it was
  always correctly scoped to. It was never extended to pretend it does
  what xEdit does, and it still isn't.
- MO2 itself ships a `IPluginDiagnose`/`IPluginTool` Python plugin
  interface (confirmed present in `C:\Modding\MO2\plugins\`, alongside the
  stock `diagnose_basic.dll` -- MO2's own missing-master warnings run
  through this same mechanism). This project intentionally stays as
  standalone scripts for now rather than becoming an MO2 plugin; revisit
  if the standalone version proves out.

## AAF crash-on-animation-start findings folded in (2026-09-11)

A live debugging session on the actual install (not this one) root-caused a
real crash when initiating an AAF animation scene, working from real
`xmlutility.log`/ini/file evidence rather than guesses. Two genuinely
distinct causes, both now covered by this engine instead of living only in
that session's notes:

- **`xmlutility.ini`'s `UseSignatures` flag.** The file's own comment
  documents `Default: false, disabled until fully tested` -- it was set to
  `true` on the live install. Every third-party AAF content pack predates
  the signing scheme it enables and is never signed, so `xmlutility.dll`
  reads their registered XML as 0 bytes across the board with this left
  true. Added as `resolution_policy.XMLUTILITY_SIGNATURES_PATCH`
  (`xmlutility.ini`, `UseSignatures=false`) -- it sits at the AAF mod's
  root, **not** under `AAF/` like `AAF_settings.ini`, verified against the
  real folder layout. Covered by `--apply` like every other `IniSetting`.
- **Genuine multi-mod load-order collisions**, independent of the flag
  above: `Atomic Lust_mfgSetData.xml`, `rxl_bp70_anims_morphSetData.xml`,
  and `rxl_bp70_furnitureData_MidCenturyModern.xml` all have real,
  non-empty source content in their owning mods' own folders, yet some
  higher-MO2-priority mod was shadowing them -- per AAF author dagobaking's
  own changelog, this is a documented pattern, not this project's
  invention. The live session had to find the winner by hand via MO2's
  Information -> Filetree per-filename search. `signals.find_aaf_multi_owner_files()`
  now does that scan automatically: every `AAF/*.xml` relative path shipped
  by 2+ mods, plus the current `modlist.txt` priority winner, surfaced as a
  MANUAL finding (the tool won't guess which owner *should* win).
- `signals.collect_aaf_integrity()` also flags 0-byte AAF XML files
  directly off disk (not by parsing `xmlutility.log` -- that stays out of
  scope for the same reason crash-log parsing does, see the CLASSIC section
  above) and a missing `aaf.xsd` schema file. The schema's exact expected
  location wasn't confirmed against a working install, so both the AAF mod
  root and its `AAF/` subfolder are checked rather than asserting one --
  documented as a caveat in the finding's own evidence text, not silently
  assumed.

All three wire into `CTD_INGAME` (`rules.py::rules_for_ctd_ingame`) -- the
closest existing symptom to "crashes when an animation starts"; no new
`Symptom` was needed. Covered by `tests/test_signals.py` (signal-level) and
new cases in `tests/test_diagnostics_engine.py` / `tests/test_resolver.py`
(end-to-end, including a fixture reproducing the real multi-owner
collision and confirming `set_key_in_ini` still refuses to invent a missing
`xmlutility.ini`).

Deliberately not attempted here, because they need the live machine, not a
code change: locating the actual Buffout 4 `crash-<timestamp>.log` (only
the plugin's own startup log was reviewed), and an unexplained "network"
error reference with no supporting log evidence yet.

## How to migrate

1. Read the report first, without changing anything:
   ```
   python migrate_legacy.py
   ```
2. Once it looks right, apply it. This backs up both source `mod_data.json`
   files, writes the single canonical one, and archives the six legacy
   scripts to `legacy/` (kept, not deleted -- two of them contain the root-
   cause reasoning now encoded in `resolution_policy.py`):
   ```
   python migrate_legacy.py --apply
   ```
3. Try the diagnostics engine:
   ```
   python -m mod_manager.diagnostics.cli list-symptoms
   python -m mod_manager.diagnostics.cli report --symptom animation_misalign
   python -m mod_manager.diagnostics.cli report --symptom ctd_on_launch
   ```
   Add `--apply` to a `report` command to have it execute the fixes that
   the resolution policy already covers (file hides, ini settings, text
   patches). It will not touch anything a finding marked "manual" --
   installing a missing master, enabling a plugin in MO2's UI, and
   reducing an over-limit plugin count all need a human decision.
4. The CLI, GUI, and web server (`main.py`, `mod_manager_gui.py`,
   `server.py`) work exactly as before from the user's perspective --
   same prompts, same web UI -- just backed by the shared core now.
