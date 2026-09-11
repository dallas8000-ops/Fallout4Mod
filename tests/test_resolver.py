from helpers import make_mod_folder

from mod_manager.core import actions, catalog, config, mod_data_store, resolver


def _setup_aaf_fixture(mods_path):
    make_mod_folder(
        mods_path,
        "Atomic Muscle",
        {
            "Meshes/Actors/Character/CharacterAssets/skeleton.nif": b"AM_SKELETON",
            "Meshes/Actors/Character/CharacterAssets/skeleton.hkx": b"AM_SKELETON_HKX",
        },
    )
    make_mod_folder(
        mods_path,
        "ZeX - ZaZ Extended Skeleton",
        {"Meshes/Actors/Character/CharacterAssets/skeleton.nif": b"ZEX_SKELETON"},
    )
    make_mod_folder(
        mods_path,
        "Ultimate AAF Patch",
        {"AAF/UAP_Atomic_Lust_Override-positionData.xml": b'<data offset="0,50,180"/>'},
    )
    make_mod_folder(
        mods_path,
        "Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0",
        {"AAF/Atomic Lust_positionData.xml": b'<data offset="0,50,180"/>'},
    )
    make_mod_folder(
        mods_path,
        "Advanced Animation Framework",
        {"AAF/AAF_settings.ini": b"scale_actors_for_animations = false\nenforce_race_scale = true\n"},
    )


def test_dry_run_makes_no_filesystem_changes(patch_config):
    _setup_aaf_fixture(patch_config.mods)
    before = {
        p: p.read_bytes()
        for p in patch_config.mods.rglob("*")
        if p.is_file()
    }

    report = resolver.apply(dry_run=True)

    assert report.dry_run is True
    after = {p: p.read_bytes() for p in patch_config.mods.rglob("*") if p.is_file()}
    assert before == after
    assert not config.MOD_DATA_PATH.exists()
    assert not config.MO2_MODLIST.exists()


def test_apply_hides_atomic_muscle_skeleton(patch_config):
    _setup_aaf_fixture(patch_config.mods)
    resolver.apply(dry_run=False)

    am_skeleton = patch_config.mods / "Atomic Muscle" / "Meshes/Actors/Character/CharacterAssets/skeleton.nif"
    assert not am_skeleton.exists()
    assert actions.is_hidden(am_skeleton)

    zex_skeleton = patch_config.mods / "ZeX - ZaZ Extended Skeleton" / "Meshes/Actors/Character/CharacterAssets/skeleton.nif"
    assert zex_skeleton.exists()


def test_apply_hides_ultimate_override_files(patch_config):
    _setup_aaf_fixture(patch_config.mods)
    resolver.apply(dry_run=False)

    override = patch_config.mods / "Ultimate AAF Patch" / "AAF" / "UAP_Atomic_Lust_Override-positionData.xml"
    assert not override.exists()
    assert actions.is_hidden(override)


def test_apply_strips_squirtcum_offset_bug(patch_config):
    _setup_aaf_fixture(patch_config.mods)
    resolver.apply(dry_run=False)

    target = (
        patch_config.mods
        / "Patch for animations (SquirtCum Effects, cum overlays, stages, fixes) 11.0"
        / "AAF"
        / "Atomic Lust_positionData.xml"
    )
    text = target.read_text(encoding="utf-8")
    assert 'offset="0,50,180"' not in text


def test_apply_sets_aaf_ini_settings(patch_config):
    _setup_aaf_fixture(patch_config.mods)
    resolver.apply(dry_run=False)

    ini = patch_config.mods / "Advanced Animation Framework" / "AAF" / "AAF_settings.ini"
    text = ini.read_text(encoding="utf-8")
    assert "scale_actors_for_animations = true" in text
    assert "enforce_race_scale = false" in text


def test_apply_corrects_xmlutility_use_signatures(patch_config):
    # Confirmed root cause (2026-09-08) of a real crash-when-initiating-an-
    # animation-scene bug: UseSignatures=true rejects unsigned third-party
    # AAF content as 0-byte. xmlutility.ini sits at the AAF mod's root, not
    # under AAF/ -- distinct from AAF_settings.ini above.
    _setup_aaf_fixture(patch_config.mods)
    xmlutility_ini = patch_config.mods / "Advanced Animation Framework" / "xmlutility.ini"
    xmlutility_ini.write_text("[Settings]\nUseSignatures = true\n", encoding="utf-8")

    resolver.apply(dry_run=False)

    text = xmlutility_ini.read_text(encoding="utf-8")
    assert "UseSignatures = false" in text


def test_apply_does_not_invent_xmlutility_ini_if_absent(patch_config):
    # set_key_in_ini never creates a missing file/key -- an AAF install that
    # doesn't ship xmlutility.ini yet must not have one silently fabricated.
    _setup_aaf_fixture(patch_config.mods)
    xmlutility_ini = patch_config.mods / "Advanced Animation Framework" / "xmlutility.ini"
    assert not xmlutility_ini.exists()

    resolver.apply(dry_run=False)

    assert not xmlutility_ini.exists()


def test_apply_is_idempotent(patch_config):
    _setup_aaf_fixture(patch_config.mods)
    resolver.apply(dry_run=False)
    report_2 = resolver.apply(dry_run=False)  # should not raise, should be a no-op on the file layer
    assert any("already hidden" in n for n in report_2.notes)


def test_apply_disables_true_duplicate_pair(patch_config):
    make_mod_folder(patch_config.mods, "Address Library")
    make_mod_folder(patch_config.mods, "Address Library - All In One")
    resolver.apply(dry_run=False)

    mod_data = mod_data_store.load(config.MOD_DATA_PATH)
    assert mod_data["Address Library"]["enabled"] is False
    assert mod_data["Address Library - All In One"]["enabled"] is True


def test_apply_writes_modlist_with_backup(patch_config):
    make_mod_folder(patch_config.mods, "Buffout 4")

    first_report = resolver.apply(dry_run=False)
    assert config.MO2_MODLIST.exists()
    assert first_report.modlist_backup is None  # nothing existed yet to back up

    second_report = resolver.apply(dry_run=False)
    assert second_report.modlist_backup is not None
    assert second_report.modlist_backup.exists()


def test_apply_preserves_manual_priority_override(patch_config):
    # Regression test for the priority-clobbering bug: apply() used to
    # unconditionally overwrite every installed mod's priority from its
    # static catalog position on every single call, so a manual re-priority
    # made through the web UI (PUT /mods/<name>) or main.py's CLI was
    # silently discarded the next time apply() ran -- including from the
    # scheduled automation job, with no warning it had happened.
    make_mod_folder(patch_config.mods, "Buffout 4")
    make_mod_folder(patch_config.mods, "Scrap scrap 1.1")

    resolver.apply(dry_run=False)  # first run: seeds catalog priorities

    mod_data = mod_data_store.load(config.MOD_DATA_PATH)
    assert mod_data["Buffout 4"]["priority"] == catalog.order_index("Buffout 4")
    assert mod_data["Buffout 4"]["priority_source"] == "catalog"

    # Simulate a manual re-priority via the web UI: server.py's PUT
    # /mods/<name> tags priority_source="manual" the instant a human sets
    # priority -- that tag, not just the presence of a priority key, is
    # what earns permanent protection from being resynced.
    mod_data["Buffout 4"]["priority"] = 999999
    mod_data["Buffout 4"]["priority_source"] = "manual"
    mod_data_store.save(mod_data, config.MOD_DATA_PATH)

    resolver.apply(dry_run=False)  # second run must NOT reset it

    mod_data = mod_data_store.load(config.MOD_DATA_PATH)
    assert mod_data["Buffout 4"]["priority"] == 999999
    assert mod_data["Buffout 4"]["priority_source"] == "manual"

    # And it must actually take effect in the written modlist.txt, not just
    # sit unused in mod_data.json -- highest priority is written first.
    lines = config.MO2_MODLIST.read_text(encoding="utf-8").splitlines()
    mod_lines = [line[1:] for line in lines if line[:1] in ("+", "-")]
    assert mod_lines[0] == "Buffout 4"


def test_apply_still_seeds_priority_for_a_newly_added_mod(patch_config):
    make_mod_folder(patch_config.mods, "Buffout 4")
    resolver.apply(dry_run=False)

    mod_data = mod_data_store.load(config.MOD_DATA_PATH)
    original_buffout_priority = mod_data["Buffout 4"]["priority"]

    # A second mod appears later (freshly installed in MO2 between runs).
    # It must still be seeded from the catalog on the next apply(), without
    # disturbing Buffout 4's already-assigned priority.
    make_mod_folder(patch_config.mods, "Unofficial Fallout 4 Patch")
    resolver.apply(dry_run=False)

    mod_data = mod_data_store.load(config.MOD_DATA_PATH)
    assert mod_data["Buffout 4"]["priority"] == original_buffout_priority
    assert mod_data["Unofficial Fallout 4 Patch"]["priority"] == catalog.order_index(
        "Unofficial Fallout 4 Patch"
    )


def test_apply_resyncs_stale_catalog_priority_when_not_manually_set(patch_config):
    # Regression test for the exact bug the priority_source model exists to
    # prevent: confirmed in production, a web UI screenshot showed two
    # unrelated mods (Address Library, Buffout 4) sharing priority 1 --
    # stale, mixed-vintage auto-seeded values left behind after catalog.py's
    # order was corrected (2026-09-11) to match the user's real MO2 profile.
    # A priority that was never manually set must track the catalog, not
    # freeze at whatever value happened to be seeded before a correction.
    make_mod_folder(patch_config.mods, "Buffout 4")
    resolver.apply(dry_run=False)

    mod_data = mod_data_store.load(config.MOD_DATA_PATH)
    correct_priority = mod_data["Buffout 4"]["priority"]
    assert mod_data["Buffout 4"]["priority_source"] == "catalog"

    # Simulate the exact production scenario: a stale priority sitting in
    # mod_data.json with nothing to indicate a human ever set it (e.g. it
    # predates the priority_source field, or catalog.py's order has since
    # been corrected).
    mod_data["Buffout 4"]["priority"] = correct_priority + 500
    del mod_data["Buffout 4"]["priority_source"]
    mod_data_store.save(mod_data, config.MOD_DATA_PATH)

    report = resolver.apply(dry_run=False)

    mod_data = mod_data_store.load(config.MOD_DATA_PATH)
    assert mod_data["Buffout 4"]["priority"] == correct_priority
    assert mod_data["Buffout 4"]["priority_source"] == "catalog"
    assert any("Resynced catalog priority" in n and "Buffout 4" in n for n in report.notes)
