"""Tests for figma2css.css and figma2css.tokens."""

import pytest

from figma2css.css import mode_selector, tokens_to_css
from figma2css.tokens import TokenBuilder


def test_empty_tokens() -> None:
    assert tokens_to_css({}) == ":root {}"


def test_bare_keys_are_prefixed_with_their_category() -> None:
    css = tokens_to_css({"colors": {"primary": "#fff"}})
    assert css == ":root {\n  /* colors */\n  --colors-primary: #fff;\n}"


def test_double_dash_keys_are_used_verbatim() -> None:
    css = tokens_to_css({"colors": {"--color-brand": "#216bed"}})
    assert "  --color-brand: #216bed;" in css
    assert "--colors---color-brand" not in css


def test_categories_are_grouped_with_comments_and_blank_lines() -> None:
    css = tokens_to_css({"colors": {"--a": "1"}, "spacing": {"--b": "2px"}})
    assert css == (
        ":root {\n  /* colors */\n  --a: 1;\n\n  /* spacing */\n  --b: 2px;\n}"
    )


def test_custom_selector() -> None:
    assert tokens_to_css({"colors": {"--a": "1"}}, selector=".theme").startswith(".theme {")


def test_mode_blocks_follow_the_root_block() -> None:
    css = tokens_to_css(
        {"colors": {"--bg": "#fff"}},
        modes={"Dark": {"colors": {"--bg": "#000"}}},
    )
    assert css.endswith('[data-theme="dark"] {\n  /* colors */\n  --bg: #000;\n}')
    assert css.index(":root") < css.index("[data-theme")


def test_mode_selector_template() -> None:
    assert mode_selector(".{mode}", "Dark Mode") == ".dark mode"
    assert mode_selector('[data-theme="{mode}"]', 'x"y') == '[data-theme="xy"]'


def test_builder_prefix_and_unique_names() -> None:
    builder = TokenBuilder(prefix="--ds-")
    assert builder.add("colors", "--color-a", "#000") == "--ds-color-a"
    assert builder.add("colors", "--color-a", "#111") == "--ds-color-a-2"
    assert builder.result() == {"colors": {"--ds-color-a": "#000", "--ds-color-a-2": "#111"}}


def test_builder_rejects_unknown_category() -> None:
    with pytest.raises(KeyError):
        TokenBuilder().add("nope", "--x", "1")


def test_builder_values_filter_by_name_part() -> None:
    builder = TokenBuilder()
    builder.add("typography", "--font-body-size", "16px")
    builder.add("typography", "--font-body-line-height", "16px")
    builder.add("typography", "--font-size-lg", "20px")
    assert builder.values("typography", "font-size-", "-size") == {"16px", "20px"}
    assert builder.values("typography", "-line-height") == {"16px"}
    assert builder.values("typography") == {"16px", "20px"}
