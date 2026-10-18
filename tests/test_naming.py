"""Tests for figma2css.naming."""

from figma2css.naming import NameRegistry, css_string, fmt_number, number_slug, px, slugify


def test_slugify_splits_style_paths() -> None:
    assert slugify("Brand / Primary Blue") == "brand-primary-blue"
    assert slugify("Heading/H1") == "heading-h1"


def test_slugify_folds_accents_and_falls_back() -> None:
    assert slugify("Crème Brûlée") == "creme-brulee"
    assert slugify("🔥🔥") == "unnamed"
    assert slugify("", fallback="x") == "x"


def test_fmt_number_trims_zeros() -> None:
    assert fmt_number(24.0) == "24"
    assert fmt_number(0.50) == "0.5"
    assert fmt_number(1 / 3) == "0.3333"
    assert fmt_number(-0.0) == "0"


def test_px() -> None:
    assert px(16) == "16px"
    assert px(12.5) == "12.5px"
    assert px(0) == "0"


def test_number_slug() -> None:
    assert number_slug(12.5) == "12-5"
    assert number_slug(8) == "8"
    assert number_slug(-2) == "n2"


def test_css_string_escapes() -> None:
    assert css_string("Inter") == '"Inter"'
    assert css_string('We"ird') == '"We\\"ird"'


def test_registry_suffixes_clashes() -> None:
    reg = NameRegistry()
    assert reg.claim("--a") == "--a"
    assert reg.claim("--a") == "--a-2"
    assert reg.claim("--a") == "--a-3"
    assert "--a-2" in reg
