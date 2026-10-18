"""Turn Figma REST API responses into design tokens.

The entry point is :func:`extract`. It accepts the parsed JSON of a file response
(``GET /v1/files/:key``), a node subset (``GET /v1/files/:key/nodes``), and optionally
a local variables response (``GET /v1/files/:key/variables/local``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .css import tokens_to_css
from .nodes import StyleWalker
from .tokens import CATEGORIES, TokenBuilder, Tokens
from .variables import extract_variables

__all__ = [
    "CATEGORIES",
    "Extraction",
    "FigmaDataError",
    "extract",
    "extract_tokens",
    "tokens_to_css",
]


class FigmaDataError(ValueError):
    """The input is not a recognisable Figma file or nodes response."""


@dataclass
class Extraction:
    """Result of :func:`extract`."""

    tokens: Tokens = field(default_factory=dict)
    modes: dict[str, Tokens] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _api_error(data: Mapping[str, Any]) -> str | None:
    """Message of a Figma error body such as ``{"status": 403, "err": "..."}``."""
    status = data.get("status")
    if isinstance(status, int) and status >= 400:
        detail = data.get("err") or data.get("message") or "no message"
        return f"Figma API error {status}: {detail}"
    if data.get("error") is True:
        return f"Figma API error: {data.get('message') or data.get('err') or 'no message'}"
    return None


def _roots(data: Mapping[str, Any], warnings: list[str]) -> list[tuple[Mapping[str, Any], Any]]:
    """(root node, styles map) pairs for each supported response shape."""
    document = data.get("document")
    if isinstance(document, Mapping):
        return [(document, data.get("styles"))]
    nodes = data.get("nodes")
    if isinstance(nodes, Mapping):
        roots = []
        for node_id, entry in nodes.items():
            if isinstance(entry, Mapping) and isinstance(entry.get("document"), Mapping):
                roots.append((entry["document"], entry.get("styles")))
            else:
                warnings.append(f"node {node_id!r} was not found in the response")
        return roots
    if isinstance(data.get("type"), str) and "id" in data:
        return [(data, data.get("styles"))]
    raise FigmaDataError(
        "input is not a Figma file response: expected a top-level 'document' or 'nodes' key"
    )


def extract(
    figma_data: Any = None,
    variables: Any = None,
    *,
    mode: str | None = None,
    styled_only: bool = False,
    inline_aliases: bool = False,
    prefix: str = "",
) -> Extraction:
    """Extract design tokens from Figma API responses.

    Args:
        figma_data: Parsed file or nodes response, or ``None`` to use variables only.
        variables: Parsed ``variables/local`` response, or ``None``.
        mode: Variable mode used as the base value (default: each collection's default).
        styled_only: Only emit tokens backed by a named style or variable.
        inline_aliases: Resolve variable aliases to their final value instead of ``var()``.
        prefix: Namespace for every custom property, e.g. ``"ds"`` gives ``--ds-color-x``.

    Raises:
        FigmaDataError: ``figma_data`` is not a Figma file/nodes response, or is an error body.
        figma2css.variables.VariableError: ``variables`` is not a variables response.
    """
    result = Extraction()
    builder = TokenBuilder(prefix)
    if variables is not None:
        result.modes = extract_variables(
            variables,
            builder,
            mode=mode,
            inline_aliases=inline_aliases,
            warnings=result.warnings,
        )
    if figma_data is not None:
        if not isinstance(figma_data, Mapping):
            raise FigmaDataError("input must be a JSON object")
        if figma_data:
            message = _api_error(figma_data)
            if message:
                raise FigmaDataError(message)
            walker = StyleWalker(builder, styled_only=styled_only, warnings=result.warnings)
            for root, styles in _roots(figma_data, result.warnings):
                walker.walk(root, styles)
            walker.finish()
    result.tokens = builder.result()
    result.warnings = list(dict.fromkeys(result.warnings))
    return result


def extract_tokens(figma_data: dict, variables: dict | None = None, **options: Any) -> Tokens:
    """Convenience wrapper around :func:`extract` that returns only the tokens.

    ``extract_tokens({})`` returns ``{}``. Keys are ``colors``, ``typography``,
    ``spacing``, ``radii``, ``effects`` and ``other``; empty categories are left out.
    """
    return extract(figma_data, variables, **options).tokens
