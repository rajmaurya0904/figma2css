"""Walk a Figma node tree and collect tokens from styles and node properties.

Figma's REST API does not return style definitions as separate objects. The file
response has a ``styles`` map (style id -> name and type) and every node that uses a
style carries ``styles: {"fill": "<id>"}`` plus the actual paint/type/effect values on
the node itself. So a style's value is read from the first visible node that
references it. Anything used without a style is collected as an unnamed token.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .colors import effective_alpha, is_color, to_hex
from .effects import effect_values
from .naming import fmt_number, number_slug, px, slugify
from .paint import node_size, paint_css, visible_paints
from .text import text_properties
from .tokens import TokenBuilder

AUTO_LAYOUT_MODES = ("HORIZONTAL", "VERTICAL")
PADDING_KEYS = ("paddingLeft", "paddingRight", "paddingTop", "paddingBottom")


def _style_ref(node: Mapping[str, Any], *keys: str) -> str | None:
    """Style id a node uses for ``keys`` (the API has used both ``fill`` and ``fills``)."""
    refs = node.get("styles")
    if not isinstance(refs, Mapping):
        return None
    for key in keys:
        value = refs.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _positive(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return None
    return float(value)


class StyleWalker:
    """Collects tokens from one or more Figma documents into a :class:`TokenBuilder`."""

    def __init__(
        self,
        builder: TokenBuilder,
        *,
        styled_only: bool = False,
        warnings: list[str] | None = None,
    ) -> None:
        self.builder = builder
        self.styled_only = styled_only
        self.warnings: list[str] = warnings if warnings is not None else []
        self._styles: dict[str, Mapping[str, Any]] = {}
        self._done_styles: set[str] = set()
        self._colors: dict[str, str] = {}
        self._shadows: set[str] = set()
        self._blurs: set[str] = set()
        self._backdrop_blurs: set[str] = set()
        self._families: dict[str, str] = {}
        self._font_sizes: set[float] = set()
        self._font_weights: set[float] = set()
        self._spacing: set[float] = set()
        self._radii: set[float] = set()

    # -- traversal -------------------------------------------------------------------

    def walk(self, root: Mapping[str, Any], styles: Any = None) -> None:
        """Visit ``root`` and every descendant that is not hidden."""
        if isinstance(styles, Mapping):
            self._styles.update({k: v for k, v in styles.items() if isinstance(v, Mapping)})
        stack: list[Mapping[str, Any]] = [root]
        while stack:
            node = stack.pop()
            if node.get("visible", True) is False:
                continue
            self._visit(node)
            children = node.get("children")
            if isinstance(children, Sequence) and not isinstance(children, str):
                stack.extend(c for c in reversed(children) if isinstance(c, Mapping))

    def _visit(self, node: Mapping[str, Any]) -> None:
        self._fills(node)
        self._strokes(node)
        if node.get("type") == "TEXT":
            self._text(node)
        self._effects(node)
        self._grids(node)
        self._auto_layout(node)
        self._radius(node)

    # -- helpers ---------------------------------------------------------------------

    def _named_style(self, style_id: str | None, expected: str) -> str | None:
        """Slug for a style the first time it is seen, else ``None``.

        Returns ``None`` when there is no style, it is unknown to the ``styles`` map,
        it is the wrong type, or it was already emitted.
        """
        if not style_id:
            return None
        meta = self._styles.get(style_id)
        if meta is None or meta.get("styleType") != expected:
            return None
        if style_id in self._done_styles:
            return None
        self._done_styles.add(style_id)
        return slugify(str(meta.get("name", style_id)), fallback=slugify(style_id))

    def _is_known_style(self, style_id: str | None, expected: str) -> bool:
        meta = self._styles.get(style_id or "")
        return meta is not None and meta.get("styleType") == expected

    # -- colours ---------------------------------------------------------------------

    def _paint_tokens(self, node: Mapping[str, Any], paints: Any, style_id: str | None) -> None:
        layers = visible_paints(paints)
        if not layers:
            return
        if self._is_known_style(style_id, "FILL"):
            slug = self._named_style(style_id, "FILL")
            if slug is None:
                return
            if len(layers) > 1:
                self.warnings.append(
                    f"style {slug!r} has {len(layers)} stacked fills; only the top one is used"
                )
            top = layers[-1]
            css = paint_css(top, node_size(node))
            if css is None:
                self.warnings.append(
                    f"style {slug!r} uses a {top.get('type')!r} paint, which has no CSS value"
                )
                return
            prefix = "gradient" if str(top.get("type", "")).startswith("GRADIENT") else "color"
            if slug.startswith(prefix + "-"):
                slug = slug[len(prefix) + 1 :]
            self.builder.add("colors", f"--{prefix}-{slug}", css)
            return
        if self.styled_only:
            return
        for paint in layers:
            if paint.get("type") != "SOLID" or not is_color(paint.get("color")):
                continue
            css = paint_css(paint)
            if css is None or css in self._colors:
                continue
            alpha = effective_alpha(paint["color"], paint.get("opacity", 1.0))
            suffix = "" if alpha >= 0.9995 else f"-a{int(alpha * 100 + 0.5)}"
            self._colors[css] = f"--color-{to_hex(paint['color'])[1:]}{suffix}"

    def _fills(self, node: Mapping[str, Any]) -> None:
        self._paint_tokens(node, node.get("fills"), _style_ref(node, "fill", "fills"))

    def _strokes(self, node: Mapping[str, Any]) -> None:
        style_id = _style_ref(node, "stroke", "strokes")
        if style_id and self._is_known_style(style_id, "FILL"):
            self._paint_tokens(node, node.get("strokes"), style_id)

    # -- typography ------------------------------------------------------------------

    def _text(self, node: Mapping[str, Any]) -> None:
        props = text_properties(node.get("style"), self.warnings)
        if not props:
            return
        style_id = _style_ref(node, "text")
        if self._is_known_style(style_id, "TEXT"):
            slug = self._named_style(style_id, "TEXT")
            if slug is None:
                return
            for key, value in props.items():
                self.builder.add("typography", f"--font-{slug}-{key}", value)
            return
        if self.styled_only:
            return
        if "family" in props:
            self._families.setdefault(props["family"], props["family"].strip('"'))
        style = node["style"]
        if "size" in props:
            self._font_sizes.add(float(style["fontSize"]))
        if "weight" in props:
            self._font_weights.add(float(style["fontWeight"]))

    # -- effects ---------------------------------------------------------------------

    def _effects(self, node: Mapping[str, Any]) -> None:
        values = effect_values(node.get("effects"), self.warnings)
        if not values:
            return
        style_id = _style_ref(node, "effect", "effects")
        if self._is_known_style(style_id, "EFFECT"):
            slug = self._named_style(style_id, "EFFECT")
            if slug is None:
                return
            for kind, value in values.items():
                self.builder.add("effects", f"--{kind}-{slug}", value)
            return
        if self.styled_only:
            return
        pools = {
            "shadow": self._shadows,
            "blur": self._blurs,
            "backdrop-blur": self._backdrop_blurs,
        }
        for kind, value in values.items():
            pool = pools[kind]
            if value in pool:
                continue
            pool.add(value)
            self.builder.add("effects", f"--{kind}-{len(pool)}", value)

    # -- spacing and layout grids ----------------------------------------------------

    def _grids(self, node: Mapping[str, Any]) -> None:
        grids = visible_paints(node.get("layoutGrids"))
        if not grids:
            return
        style_id = _style_ref(node, "grid", "grids")
        if self._is_known_style(style_id, "GRID"):
            slug = self._named_style(style_id, "GRID")
            if slug is not None:
                self._grid_style(slug, grids)
            return
        if self.styled_only:
            return
        for grid in grids:
            gutter = _positive(grid.get("gutterSize"))
            if gutter is not None:
                self._spacing.add(gutter)

    def _grid_style(self, slug: str, grids: list[Mapping[str, Any]]) -> None:
        seen: set[str] = set()
        for grid in grids:
            pattern = grid.get("pattern")
            if pattern in seen:
                continue
            seen.add(str(pattern))
            if pattern == "COLUMNS":
                prefix, count_name = f"--grid-{slug}", "columns"
            elif pattern == "ROWS":
                prefix, count_name = f"--grid-{slug}-row", "rows"
            elif pattern == "GRID":
                size = _positive(grid.get("sectionSize"))
                if size is not None:
                    self.builder.add("spacing", f"--grid-{slug}-size", px(size))
                continue
            else:
                continue
            for key, suffix in (("gutterSize", "gutter"), ("offset", "margin")):
                value = grid.get(key)
                if isinstance(value, int | float) and not isinstance(value, bool):
                    self.builder.add("spacing", f"{prefix}-{suffix}", px(value))
            count = _positive(grid.get("count"))
            if count is not None:
                self.builder.add("spacing", f"{prefix}-{count_name}", fmt_number(count))

    def _auto_layout(self, node: Mapping[str, Any]) -> None:
        if self.styled_only or node.get("layoutMode") not in AUTO_LAYOUT_MODES:
            return
        keys = list(PADDING_KEYS) + ["counterAxisSpacing"]
        if node.get("primaryAxisAlignItems") != "SPACE_BETWEEN":
            keys.append("itemSpacing")
        for key in keys:
            value = _positive(node.get(key))
            if value is not None:
                self._spacing.add(value)

    def _radius(self, node: Mapping[str, Any]) -> None:
        if self.styled_only:
            return
        values: list[Any] = [node.get("cornerRadius")]
        corners = node.get("rectangleCornerRadii")
        if isinstance(corners, Sequence) and not isinstance(corners, str):
            values.extend(corners)
        for raw in values:
            value = _positive(raw)
            if value is not None:
                self._radii.add(value)

    # -- scales ----------------------------------------------------------------------

    def finish(self) -> None:
        """Emit the unnamed values (colours, families, sizes, weights, spacing, radii).

        A value that a named style or variable already provides is not repeated under
        a second, positional name.
        """
        builder = self.builder
        have = builder.values("colors")
        for css, name in self._colors.items():
            if css not in have:
                builder.add("colors", name, css)
        have = builder.values("typography", "font-family-", "-family")
        for css, family in self._families.items():
            if css not in have:
                builder.add("typography", f"--font-family-{slugify(family)}", css)
        have = builder.values("typography", "font-size-", "-size")
        for size in sorted(self._font_sizes):
            if px(size) not in have:
                builder.add("typography", f"--font-size-{number_slug(size)}", px(size))
        have = builder.values("typography", "font-weight-", "-weight")
        for weight in sorted(self._font_weights):
            if fmt_number(weight) not in have:
                builder.add(
                    "typography", f"--font-weight-{number_slug(weight)}", fmt_number(weight)
                )
        have = builder.values("spacing", "spacing-")
        for value in sorted(self._spacing):
            if px(value) not in have:
                builder.add("spacing", f"--spacing-{number_slug(value)}", px(value))
        have = builder.values("radii")
        for value in sorted(self._radii):
            if px(value) not in have:
                builder.add("radii", f"--radius-{number_slug(value)}", px(value))
