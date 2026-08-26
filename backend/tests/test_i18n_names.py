"""Shared catalog-name resolver — priority chain + any-non-empty fallback."""

from app.core.i18n_names import CATALOG_NAME_PRIORITY, catalog_name


def test_prefers_priority_order():
    names = {"en": "Filling", "es": "Empaste", "ar": "حشوة"}
    assert catalog_name(names) == "Empaste"


def test_arabic_only_item_resolves():
    # Items created under a core-only locale must not degrade to None.
    assert catalog_name({"ar": "تبييض الأسنان"}) == "تبييض الأسنان"


def test_arabic_beats_catchall_when_present():
    names = {"de": "Bleaching", "ar": "تبييض"}
    assert catalog_name(names) == "Bleaching"
    names2 = {"it": "Blanchiment", "ar": "تبييض"}
    # 'ar' is in the priority chain; 'it' only via catch-all
    assert catalog_name(names2) == "تبييض"


def test_empty_strings_skipped():
    assert catalog_name({"es": "", "en": "  ", "fr": "Détartrage"}) == "Détartrage"
    assert catalog_name({"es": "", "en": ""}) is None


def test_none_and_non_dict_inputs():
    assert catalog_name(None) is None
    assert catalog_name({}) is None
    assert catalog_name("not-a-dict") is None


def test_priority_chain_covers_known_locales():
    """CATALOG_NAME_PRIORITY must list the core locales; future locales
    are added by appending to the tuple — this test pins the known set
    without breaking when a new locale is added."""
    for lang in ("es", "en", "fr", "pt", "ta", "de", "hu"):
        assert lang in CATALOG_NAME_PRIORITY, f"{lang} missing from CATALOG_NAME_PRIORITY"
