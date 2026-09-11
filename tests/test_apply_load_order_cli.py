from helpers import make_mod_folder

from mod_manager.apply_load_order import main
from mod_manager.core import config, mod_data_store


def test_dry_run_default_writes_nothing(patch_config, capsys):
    make_mod_folder(patch_config.mods, "Buffout 4")

    exit_code = main([])

    assert exit_code == 0
    assert not config.MOD_DATA_PATH.exists()
    assert not config.MO2_MODLIST.exists()
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "Re-run with --apply" in out


def test_apply_flag_writes_and_reports_newly_seeded_mod(patch_config, capsys):
    make_mod_folder(patch_config.mods, "Buffout 4")

    exit_code = main(["--apply"])

    assert exit_code == 0
    assert config.MOD_DATA_PATH.exists()
    assert config.MO2_MODLIST.exists()
    out = capsys.readouterr().out
    assert "Resynced catalog priority for 1 mod(s)" in out
    assert "Buffout 4" in out


def test_second_run_with_no_new_mods_reports_no_resequence(patch_config, capsys):
    make_mod_folder(patch_config.mods, "Buffout 4")
    main(["--apply"])
    capsys.readouterr()  # discard first run's output

    exit_code = main(["--apply"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Resynced catalog priority" not in out


def test_adding_a_mod_between_runs_only_resequences_the_new_one(patch_config, capsys):
    make_mod_folder(patch_config.mods, "Buffout 4")
    main(["--apply"])
    original_priority = mod_data_store.load(config.MOD_DATA_PATH)["Buffout 4"]["priority"]
    capsys.readouterr()

    make_mod_folder(patch_config.mods, "Unofficial Fallout 4 Patch")
    main(["--apply"])

    mod_data = mod_data_store.load(config.MOD_DATA_PATH)
    assert mod_data["Buffout 4"]["priority"] == original_priority
    out = capsys.readouterr().out
    assert "Resynced catalog priority for 1 mod(s)" in out
    assert "Unofficial Fallout 4 Patch" in out
    # Buffout 4 was untouched -- it must not appear in the resync line.
    resync_line = next(line for line in out.splitlines() if "Resynced catalog priority" in line)
    assert "Buffout 4" not in resync_line
