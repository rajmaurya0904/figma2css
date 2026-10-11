"""Smoke test: package imports cleanly. Replace/extend as modules land."""

import figma2css


def test_version_is_set() -> None:
    assert figma2css.__version__
