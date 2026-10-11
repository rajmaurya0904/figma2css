"""Tests for figma2css.core."""

from figma2css.core import extract_tokens


def test_extract_tokens_empty() -> None:
    """Extract tokens should return an empty dict for empty input."""
    assert extract_tokens({}) == {}