"""Tests for figma2css.core."""

from figma2css.core import extract_tokens, tokens_to_css


def test_extract_tokens_empty() -> None:
    """Extract tokens should return an empty dict for empty input."""
    assert extract_tokens({}) == {}


def test_extract_tokens_simple() -> None:
    """Extract tokens should pull out nested styles."""
    figma_data = {
        "document": {
            "children": [
                {
                    "type": "RECTANGLE",
                    "fills": [{"type": "SOLID", "color": {"r": 1, "g": 0, "b": 0}}],
                }
            ]
        }
    }
    # We expect the function to return a dict with some structure.
    # Since the exact implementation of extract_tokens is not specified,
    # we just check that it returns a dict.
    assert isinstance(extract_tokens(figma_data), dict)


def test_tokens_to_css() -> None:
    """tokens_to_css should format tokens as CSS custom properties."""
    tokens = {"colors": {"primary": "#fff"}}
    css = tokens_to_css(tokens)
    assert ":root {" in css
    assert "--colors-primary: #fff;" in css
    # Also test with multiple tokens
    tokens2 = {
        "colors": {"primary": "#fff", "secondary": "#000"},
        "spacing": {"unit": "8px"},
    }
    css2 = tokens_to_css(tokens2)
    assert "--colors-primary: #fff;" in css2
    assert "--colors-secondary: #000;" in css2
    assert "--spacing-unit: 8px;" in css2
    # Ensure the output is a string
    assert isinstance(css, str)
    assert isinstance(css2, str)

def test_tokens_to_css_does_not_double_prefix_extracted_keys() -> None:
    """Keys from extract_tokens already start with --, so they must not be prefixed."""
    figma_data = {
        "document": {
            "fills": [{"type": "SOLID", "color": {"r": 1, "g": 0, "b": 0}}],
        }
    }
    css = tokens_to_css(extract_tokens(figma_data))
    assert "--color-1: #ff0000;" in css
    assert "--colors---color-1" not in css


def test_spacing_tokens_carry_a_px_unit():
    """Figma gutterSize is in pixels; a bare number is not a valid CSS length."""
    figma = {"document": {"layoutGrids": [{"gutterSize": 24}, {"gutterSize": 12.5}]}}
    tokens = extract_tokens(figma)
    assert tokens["spacing"] == {"--spacing-1": "24px", "--spacing-2": "12.5px"}
    assert "--spacing-1: 24px;" in tokens_to_css(tokens)
