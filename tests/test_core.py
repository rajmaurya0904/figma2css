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


def test_extract_spacing_from_layout_grid() -> None:
    """Extract spacing tokens from layout grids."""
    figma_data = {
        "document": {
            "children": [
                {
                    "layoutGrids": [
                        {
                            "gutterSize": 8,
                            "pattern": "COLUMNS",
                            "alignment": "STRETCH",
                            "gridAlignment": "MIN",
                            "visible": True,
                            "offset": 0,
                            "count": 12,
                        }
                    ],
                    "children": [],
                }
            ]
        }
    }
    tokens = extract_tokens(figma_data)
    assert "spacing" in tokens
    assert "--spacing-1" in tokens["spacing"]
    assert tokens["spacing"]["--spacing-1"] == "8"


def test_extract_spacing_multiple_grids() -> None:
    """Extract spacing tokens from multiple layout grids, deduplicate."""
    figma_data = {
        "document": {
            "children": [
                {
                    "layoutGrids": [
                        {
                            "gutterSize": 16,
                            "pattern": "COLUMNS",
                        },
                        {
                            "gutterSize": 16,  # duplicate
                            "pattern": "ROWS",
                        },
                        {
                            "gutterSize": 24,
                            "pattern": "COLUMNS",
                        },
                    ],
                    "children": [],
                }
            ]
        }
    }
    tokens = extract_tokens(figma_data)
    assert "spacing" in tokens
    # Should have two spacing tokens: 16 and 24
    assert len(tokens["spacing"]) == 2
    assert "--spacing-1" in tokens["spacing"]
    assert "--spacing-2" in tokens["spacing"]
    # Values should be 16 and 24 (order may vary)
    spacing_values = set(tokens["spacing"].values())
    assert spacing_values == {"16", "24"}


def test_extract_spacing_float_gutter() -> None:
    """Extract spacing tokens from layout grids with float gutterSize."""
    figma_data = {
        "document": {
            "children": [
                {
                    "layoutGrids": [
                        {
                            "gutterSize": 8.5,
                            "pattern": "COLUMNS",
                        }
                    ],
                    "children": [],
                }
            ]
        }
    }
    tokens = extract_tokens(figma_data)
    assert "spacing" in tokens
    assert "--spacing-1" in tokens["spacing"]
    assert tokens["spacing"]["--spacing-1"] == "8.5"