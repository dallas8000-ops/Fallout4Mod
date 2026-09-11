from mod_manager.core import catalog


def test_order_index_known_mod_is_stable():
    assert catalog.order_index("Buffout 4") < catalog.order_index("BodyTalk")
    assert catalog.order_index("Address Library - All In One") == 0


def test_order_index_unknown_mod_sorts_after_all_known():
    unknown_index = catalog.order_index("Some Brand New Mod Nobody Has Categorized")
    assert unknown_index > catalog.order_index(catalog.ORDER_LOW_TO_HIGH[-1])


def test_get_category_and_tier_matches_known_tier_table():
    # Per server.py's original tier_mods table (adopted verbatim as canonical,
    # see catalog.py's provenance note): "Buffout 4" sits in the "Body Talk &
    # Physics Actors" tier alongside "bodytalk", not "Core Fixes & Frameworks"
    # -- an odd grouping, but it's what's actually persisted in the live
    # mod_data.json today, verified with zero mismatches against all 96
    # currently-installed mods.
    category, tier = catalog.get_category_and_tier("Buffout 4")
    assert category == "Body Talk & Physics Actors"
    assert tier == 6


def test_get_category_and_tier_falls_back_to_hints_not_bare_other():
    # "High Res DLC Black Face Fix" matches no TIER_MODS entry but does match
    # a CATEGORY_HINTS keyword ("texture" via "black face fix"? -> "black face fix" itself
    # is not a hint; use a name guaranteed to hit a hint instead.
    category, tier = catalog.get_category_and_tier("Some Custom Rifle Weapon Pack")
    assert category != catalog.OTHER_CATEGORY  # "rifle"/"weapon" hints should fire


def test_get_category_and_tier_true_unknown_falls_to_other():
    category, tier = catalog.get_category_and_tier("Totally Unrecognizable Mod Name Xyzzy")
    assert category == catalog.OTHER_CATEGORY
    assert tier == catalog.OTHER_TIER_INDEX


def test_build_catalog_sorts_by_order_then_name():
    installed = {"BodyTalk", "Buffout 4", "Address Library - All In One"}
    entries = catalog.build_catalog(installed)
    names = [e.name for e in entries]
    assert names == sorted(names, key=lambda n: (catalog.order_index(n), n))
    assert names[0] == "Address Library - All In One"


def test_disable_if_present_pairs_are_all_in_order_list():
    for older, newer in catalog.DISABLE_IF_PRESENT.items():
        assert older in catalog._ORDER_INDEX, f"{older} missing from ORDER_LOW_TO_HIGH"
        assert newer in catalog._ORDER_INDEX, f"{newer} missing from ORDER_LOW_TO_HIGH"
