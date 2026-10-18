"""Convert Figma effects (shadows and blurs) to CSS values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .colors import is_color, to_css
from .naming import fmt_number, px

SHADOW_TYPES = ("DROP_SHADOW", "INNER_SHADOW")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(value)


def shadow_css(effect: Mapping[str, Any]) -> str | None:
    """One ``box-shadow`` layer: ``[inset] x y blur spread colour``.

    Figma's shadow radius is the CSS blur radius one to one. ``spread`` defaults to 0.
    """
    kind = effect.get("type")
    if kind not in SHADOW_TYPES or not is_color(effect.get("color")):
        return None
    offset = effect.get("offset") if isinstance(effect.get("offset"), Mapping) else {}
    parts = [
        px(_number(offset.get("x"))),
        px(_number(offset.get("y"))),
        px(max(0.0, _number(effect.get("radius")))),
        px(_number(effect.get("spread"))),
        to_css(effect["color"]),
    ]
    prefix = "inset " if kind == "INNER_SHADOW" else ""
    return prefix + " ".join(parts)


def blur_css(effect: Mapping[str, Any]) -> str | None:
    """``blur(...)`` for a layer or background blur.

    Figma's blur radius is twice the Gaussian standard deviation that CSS ``blur()``
    takes, so the radius is halved.
    """
    if effect.get("type") not in ("LAYER_BLUR", "BACKGROUND_BLUR"):
        return None
    radius = max(0.0, _number(effect.get("radius")))
    return f"blur({fmt_number(radius / 2, 2)}px)"


def effect_values(effects: Any, warnings: list[str] | None = None) -> dict[str, str]:
    """Group a node's visible effects into CSS values.

    Returns a mapping with any of the keys ``shadow`` (comma-joined ``box-shadow``
    layers), ``blur`` (layer blur, for ``filter``) and ``backdrop-blur`` (background
    blur, for ``backdrop-filter``). Effect types with no CSS equivalent are reported
    through ``warnings``.
    """
    if not isinstance(effects, Sequence) or isinstance(effects, str):
        return {}
    shadows: list[str] = []
    result: dict[str, str] = {}
    for effect in effects:
        if not isinstance(effect, Mapping) or effect.get("visible", True) is False:
            continue
        kind = effect.get("type")
        if kind in SHADOW_TYPES:
            css = shadow_css(effect)
            if css:
                shadows.append(css)
        elif kind == "LAYER_BLUR":
            result.setdefault("blur", blur_css(effect) or "")
        elif kind == "BACKGROUND_BLUR":
            result.setdefault("backdrop-blur", blur_css(effect) or "")
        elif warnings is not None:
            warnings.append(f"effect type {kind!r} has no CSS equivalent and was skipped")
    if shadows:
        result["shadow"] = ", ".join(shadows)
    return {key: value for key, value in result.items() if value}
