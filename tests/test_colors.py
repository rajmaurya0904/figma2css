"""Tests for figma2css.colors."""

import pytest

from figma2css.colors import effective_alpha, is_color, to_byte, to_css, to_hex


def test_to_byte_rounds_half_up() -> None:
    assert to_byte(0) == 0
    assert to_byte(1) == 255
    assert to_byte(0.5) == 128
    assert to_byte(0.13) == 33


def test_to_byte_clamps_out_of_range_and_bad_values() -> None:
    assert to_byte(-3) == 0
    assert to_byte(7) == 255
    assert to_byte("nope") == 0
    assert to_byte(None) == 0
    assert to_byte(float("nan")) == 0


def test_to_hex_matches_figma_float_values() -> None:
    assert to_hex({"r": 0.13, "g": 0.42, "b": 0.93}) == "#216bed"
    assert to_hex({"r": 1, "g": 1, "b": 1, "a": 0.2}) == "#ffffff"
    assert to_hex({}) == "#000000"


def test_to_css_opaque_is_hex() -> None:
    assert to_css({"r": 1, "g": 0, "b": 0, "a": 1}) == "#ff0000"
    assert to_css({"r": 1, "g": 0, "b": 0}) == "#ff0000"


def test_to_css_uses_rgba_for_alpha() -> None:
    assert to_css({"r": 0, "g": 0, "b": 0, "a": 0.25}) == "rgba(0, 0, 0, 0.25)"


def test_paint_opacity_multiplies_with_colour_alpha() -> None:
    color = {"r": 0, "g": 0, "b": 1, "a": 0.5}
    assert effective_alpha(color, 0.5) == pytest.approx(0.25)
    assert to_css(color, 0.5) == "rgba(0, 0, 255, 0.25)"
    assert to_css({"r": 0, "g": 0, "b": 1}, 0.4) == "rgba(0, 0, 255, 0.4)"


def test_is_color() -> None:
    assert is_color({"r": 0, "g": 0.5, "b": 1, "a": 1})
    assert not is_color({"r": 0, "g": 0})
    assert not is_color({"type": "VARIABLE_ALIAS", "id": "VariableID:1:2"})
    assert not is_color("#fff")
    assert not is_color({"r": True, "g": 0, "b": 0})
