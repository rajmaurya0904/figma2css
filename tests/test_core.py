"""Tests for figma2css.core."""

from figma2css.core import extract_tokens


def test_extract_tokens_empty() -> None:
    """Extract tokens should return an empty dict for empty input."""
    assert extract_tokens({}) == {}


def test_extract_colors() -> None:
    """Extract colors should return a color token for a red fill."""
    figma_data = {
        "document": {
            "children": [
                {
                    "fills": [
                        {
                            "type": "SOLID",
                            "color": {"r": 1.0, "g": 0.0, "b": 0.0},
                        }
                    ],
                    "children": [],
                }
            ]
        }
    }
    tokens = extract_tokens(figma_data)
    assert "colors" in tokens
    assert "--color-1" in tokens["colors"]
    assert tokens["colors"]["--color-1"] == "#ff0000"