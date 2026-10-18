"""Colour conversion from Figma's 0-1 float RGBA to CSS."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .naming import fmt_number


def _clamp01(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number:  # NaN
        return 0.0
    return max(0.0, min(1.0, number))


def to_byte(value: Any) -> int:
    """Convert a 0-1 float channel to a 0-255 integer, rounding half up."""
    return int(_clamp01(value) * 255 + 0.5)


def effective_alpha(color: Mapping[str, Any], opacity: Any = 1.0) -> float:
    """Combine the colour's own alpha with a paint/fill ``opacity``."""
    alpha = _clamp01(color.get("a", 1.0))
    return alpha * _clamp01(1.0 if opacity is None else opacity)


def to_hex(color: Mapping[str, Any]) -> str:
    """Return ``#rrggbb`` for a Figma colour, ignoring alpha."""
    r, g, b = (to_byte(color.get(c, 0)) for c in "rgb")
    return f"#{r:02x}{g:02x}{b:02x}"


def to_css(color: Mapping[str, Any], opacity: Any = 1.0) -> str:
    """Return a CSS colour: ``#rrggbb`` when opaque, ``rgba(...)`` otherwise."""
    alpha = effective_alpha(color, opacity)
    if alpha >= 0.9995:
        return to_hex(color)
    r, g, b = (to_byte(color.get(c, 0)) for c in "rgb")
    return f"rgba({r}, {g}, {b}, {fmt_number(alpha, 3)})"


def is_color(value: Any) -> bool:
    """True if ``value`` looks like a Figma RGBA colour object."""
    return isinstance(value, Mapping) and all(
        isinstance(value.get(c), int | float) and not isinstance(value.get(c), bool)
        for c in "rgb"
    )
