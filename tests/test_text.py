"""Tests for figma2css.text."""

from figma2css.text import line_height_css, text_properties


def test_full_type_style() -> None:
    style = {
        "fontFamily": "Inter",
        "fontWeight": 700,
        "fontSize": 32,
        "letterSpacing": -0.64,
        "lineHeightPx": 40,
        "lineHeightPercentFontSize": 125,
        "lineHeightUnit": "FONT_SIZE_%",
    }
    assert text_properties(style) == {
        "family": '"Inter"',
        "size": "32px",
        "weight": "700",
        "line-height": "1.25",
        "letter-spacing": "-0.64px",
    }


def test_pixel_line_height_stays_in_pixels() -> None:
    assert line_height_css({"lineHeightPx": 16, "lineHeightUnit": "PIXELS"}) == "16px"
    assert line_height_css({"lineHeightPx": 18.5}) == "18.5px"


def test_intrinsic_line_height_is_omitted() -> None:
    style = {"lineHeightPx": 18.5, "lineHeightUnit": "INTRINSIC_%"}
    assert line_height_css(style) is None
    assert "line-height" not in text_properties({"fontSize": 13, **style})


def test_zero_letter_spacing_is_omitted() -> None:
    assert "letter-spacing" not in text_properties({"fontSize": 16, "letterSpacing": 0})


def test_text_case_and_decoration() -> None:
    props = text_properties({"textCase": "UPPER", "textDecoration": "UNDERLINE"})
    assert props == {"text-transform": "uppercase", "text-decoration": "underline"}
    assert text_properties({"textCase": "TITLE"})["text-transform"] == "capitalize"
    assert "text-transform" not in text_properties({"textCase": "ORIGINAL"})


def test_small_caps_warns() -> None:
    warnings: list[str] = []
    assert text_properties({"textCase": "SMALL_CAPS"}, warnings) == {}
    assert len(warnings) == 1


def test_bad_values_are_ignored() -> None:
    style = {"fontFamily": "  ", "fontSize": -4, "fontWeight": "bold", "letterSpacing": True}
    assert text_properties(style) == {}
    assert text_properties(None) == {}
    assert text_properties("Inter") == {}
