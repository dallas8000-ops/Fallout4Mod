from helpers import make_mod_folder

from mod_manager.core import actions, config, mod_data_store, resolver


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
