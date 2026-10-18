"""Convert Figma paints (solid and gradient fills) to CSS values."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .colors import is_color, to_css
from .naming import fmt_number

Size = tuple[float, float]


def node_size(node: Mapping[str, Any]) -> Size | None:
    """Width and height of a node in pixels, if the response carried them."""
    box = node.get("absoluteBoundingBox")
    if isinstance(box, Mapping) and box.get("width") and box.get("height"):
        return float(box["width"]), float(box["height"])
    size = node.get("size")
    if isinstance(size, Mapping) and size.get("x") and size.get("y"):
        return float(size["x"]), float(size["y"])
    return None


def visible_paints(paints: Any) -> list[Mapping[str, Any]]:
    """Paints that are mappings and not hidden (``visible: false``)."""
    if not isinstance(paints, Sequence) or isinstance(paints, str):
        return []
    return [p for p in paints if isinstance(p, Mapping) and p.get("visible", True) is not False]


def solid_css(paint: Mapping[str, Any]) -> str | None:
    """CSS colour for a ``SOLID`` paint, folding paint opacity into alpha."""
    if paint.get("type") != "SOLID" or not is_color(paint.get("color")):
        return None
    return to_css(paint["color"], paint.get("opacity", 1.0))


def _stops(paint: Mapping[str, Any], remap: Any) -> list[str] | None:
    raw = paint.get("gradientStops")
    if not isinstance(raw, Sequence) or len(raw) < 2:
        return None
    parts = []
    for stop in raw:
        if not isinstance(stop, Mapping) or not is_color(stop.get("color")):
            return None
        position = remap(float(stop.get("position", 0)))
        parts.append(
            f"{to_css(stop['color'], paint.get('opacity', 1.0))} {fmt_number(position * 100, 2)}%"
        )
    return parts


def _handles(paint: Mapping[str, Any]) -> list[tuple[float, float]] | None:
    raw = paint.get("gradientHandlePositions")
    if not isinstance(raw, Sequence) or len(raw) < 2:
        return None
    try:
        return [(float(h["x"]), float(h["y"])) for h in raw]
    except (KeyError, TypeError, ValueError):
        return None


def linear_gradient_css(paint: Mapping[str, Any], size: Size | None = None) -> str | None:
    """``linear-gradient(...)`` for a ``GRADIENT_LINEAR`` paint.

    Handle positions are normalised to the node box. With the node size known the
    angle and the stop positions are corrected for non-square boxes (CSS measures
    stops along a gradient line that spans the box corner to corner, Figma along
    the line between its two handles). Without a size the box is assumed square.
    """
    handles = _handles(paint)
    if handles is None:
        return None
    width, height = size or (1.0, 1.0)
    (x0, y0), (x1, y1) = handles[0], handles[1]
    dx, dy = (x1 - x0) * width, (y1 - y0) * height
    figma_length = math.hypot(dx, dy)
    if figma_length == 0:
        return None
    angle = math.degrees(math.atan2(dx, -dy)) % 360
    ux, uy = dx / figma_length, dy / figma_length
    css_length = abs(width * ux) + abs(height * uy)
    start_x = width / 2 - ux * css_length / 2
    start_y = height / 2 - uy * css_length / 2
    offset = ((x0 * width - start_x) * ux) + ((y0 * height - start_y) * uy)

    def remap(position: float) -> float:
        return (offset + position * figma_length) / css_length

    stops = _stops(paint, remap)
    if stops is None:
        return None
    return f"linear-gradient({fmt_number(angle, 2)}deg, {', '.join(stops)})"


def radial_gradient_css(paint: Mapping[str, Any], size: Size | None = None) -> str | None:
    """``radial-gradient(...)`` for a ``GRADIENT_RADIAL`` paint (rotation is ignored)."""
    handles = _handles(paint)
    stops = _stops(paint, lambda p: p)
    if handles is None or stops is None or len(handles) < 3:
        return None
    width, height = size or (1.0, 1.0)
    (cx, cy), (x1, y1), (x2, y2) = handles[0], handles[1], handles[2]
    rx = math.hypot((x1 - cx) * width, (y1 - cy) * height)
    ry = math.hypot((x2 - cx) * width, (y2 - cy) * height)
    at = f"{fmt_number(cx * 100, 2)}% {fmt_number(cy * 100, 2)}%"
    if size is None:
        return f"radial-gradient(circle at {at}, {', '.join(stops)})"
    return (
        f"radial-gradient(ellipse {fmt_number(rx, 2)}px {fmt_number(ry, 2)}px at {at}, "
        f"{', '.join(stops)})"
    )


def paint_css(paint: Mapping[str, Any], size: Size | None = None) -> str | None:
    """CSS value for any supported paint, or ``None`` if it cannot be expressed."""
    kind = paint.get("type")
    if kind == "SOLID":
        return solid_css(paint)
    if kind == "GRADIENT_LINEAR":
        return linear_gradient_css(paint, size)
    if kind == "GRADIENT_RADIAL":
        return radial_gradient_css(paint, size)
    return None
