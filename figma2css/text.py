"""Convert a Figma ``TypeStyle`` object to CSS typography values."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .naming import css_string, fmt_number, px

TEXT_TRANSFORMS = {"UPPER": "uppercase", "LOWER": "lowercase", "TITLE": "capitalize"}
TEXT_DECORATIONS = {"UNDERLINE": "underline", "STRIKETHROUGH": "line-through"}


def _positive(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return None
    return float(value)


def line_height_css(style: Mapping[str, Any]) -> str | None:
    """CSS ``line-height`` for a type style.

    Pixel line heights stay in pixels, percent-of-font-size becomes a unitless ratio,
    and Figma's automatic ("intrinsic") line height is left out so the browser's
    ``normal`` applies.
    """
    unit = style.get("lineHeightUnit")
    if unit == "INTRINSIC_%":
        return None
    if unit == "FONT_SIZE_%":
        percent = _positive(style.get("lineHeightPercentFontSize"))
        if percent is not None:
            return fmt_number(percent / 100, 3)
    pixels = _positive(style.get("lineHeightPx"))
    if pixels is not None and unit in (None, "PIXELS", "FONT_SIZE_%"):
        return px(pixels)
    return None


def text_properties(style: Any, warnings: list[str] | None = None) -> dict[str, str]:
    """Return CSS values keyed ``family``, ``size``, ``weight``, ``line-height``,
    ``letter-spacing``, ``text-transform`` and ``text-decoration``.

    Only keys the style actually specifies are present. A non-mapping yields ``{}``.
    """
    if not isinstance(style, Mapping):
        return {}
    props: dict[str, str] = {}
    family = style.get("fontFamily")
    if isinstance(family, str) and family.strip():
        props["family"] = css_string(family.strip())
    size = _positive(style.get("fontSize"))
    if size is not None:
        props["size"] = px(size)
    weight = _positive(style.get("fontWeight"))
    if weight is not None:
        props["weight"] = fmt_number(weight)
    line_height = line_height_css(style)
    if line_height:
        props["line-height"] = line_height
    spacing = style.get("letterSpacing")
    if isinstance(spacing, int | float) and not isinstance(spacing, bool) and spacing != 0:
        props["letter-spacing"] = px(spacing)
    case = style.get("textCase")
    if case in TEXT_TRANSFORMS:
        props["text-transform"] = TEXT_TRANSFORMS[case]
    elif case == "SMALL_CAPS" and warnings is not None:
        warnings.append("textCase SMALL_CAPS was skipped (needs font-variant support)")
    decoration = style.get("textDecoration")
    if decoration in TEXT_DECORATIONS:
        props["text-decoration"] = TEXT_DECORATIONS[decoration]
    return props
