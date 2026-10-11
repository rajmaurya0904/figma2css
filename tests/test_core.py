"""Tests for figma2css.core."""

from figma2css.core import extract_tokens


def test_extract_tokens_returns_empty_dict() -> None:
    """Extract tokens should return an empty dict for any input."""
    assert extract_tokens({}) == {}
    assert extract_tokens({"key": "value"}) == {}