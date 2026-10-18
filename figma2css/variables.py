"""Read the response of ``GET /v1/files/:key/variables/local`` into tokens.

Variables are Figma's native design tokens: named, typed values grouped into
collections, with one value per mode (Light/Dark, Compact/Comfortable, ...). A value
can also be an alias that points at another variable.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .colors import is_color, to_css
from .naming import css_string, fmt_number, px, slugify
from .tokens import TokenBuilder, Tokens

MAX_ALIAS_DEPTH = 32

# (category, custom-property prefix, value kind, redundant leading name words)
_COLOR = ("colors", "--color-", "color", ("color", "colors"))
_RADIUS = ("radii", "--radius-", "px", ("radius", "radii"))
_FONT_SIZE = ("typography", "--font-size-", "px", ("font-size", "font-sizes"))
_FONT_WEIGHT = ("typography", "--font-weight-", "number", ("font-weight", "font-weights"))
_LINE_HEIGHT = ("typography", "--line-height-", "px", ("line-height", "line-heights"))
_LETTER_SPACING = ("typography", "--letter-spacing-", "px", ("letter-spacing",))
_SPACING = ("spacing", "--spacing-", "px", ("spacing", "space", "spaces"))
_FONT_FAMILY = ("typography", "--font-family-", "string", ("font-family", "font-families"))
_NUMBER = ("other", "--number-", "number", ("number",))
_STRING = ("other", "--string-", "string", ("string",))

_SPACING_NAME = re.compile(r"(space|spacing|gap|padding|margin)")
_RADIUS_NAME = re.compile(r"radius|radii|corner")
_FONT_FAMILY_NAME = re.compile(r"font[-_/ ]?famil|typeface")
_FONT_SIZE_NAME = re.compile(r"font[-_/ ]?size")
_FONT_WEIGHT_NAME = re.compile(r"font[-_/ ]?weight")


class VariableError(ValueError):
    """The variables payload is unusable (wrong shape or an API error)."""


@dataclass(frozen=True)
class _Kind:
    category: str
    prefix: str
    value_kind: str
    strip: tuple[str, ...]


def _classify(variable: Mapping[str, Any]) -> _Kind | None:
    """Pick a token category for a variable, or ``None`` if it has no CSS meaning."""
    resolved = variable.get("resolvedType")
    scopes = {s for s in variable.get("scopes", []) if isinstance(s, str)}
    name = str(variable.get("name", "")).lower()
    if resolved == "COLOR":
        return _Kind(*_COLOR)
    if resolved == "FLOAT":
        if "CORNER_RADIUS" in scopes or _RADIUS_NAME.search(name):
            return _Kind(*_RADIUS)
        if "FONT_SIZE" in scopes or _FONT_SIZE_NAME.search(name):
            return _Kind(*_FONT_SIZE)
        if "FONT_WEIGHT" in scopes or _FONT_WEIGHT_NAME.search(name):
            return _Kind(*_FONT_WEIGHT)
        if "LINE_HEIGHT" in scopes:
            return _Kind(*_LINE_HEIGHT)
        if "LETTER_SPACING" in scopes:
            return _Kind(*_LETTER_SPACING)
        if scopes & {"GAP", "WIDTH_HEIGHT"} or _SPACING_NAME.search(name):
            return _Kind(*_SPACING)
        return _Kind(*_NUMBER)
    if resolved == "STRING":
        if "FONT_FAMILY" in scopes or _FONT_FAMILY_NAME.search(name):
            return _Kind(*_FONT_FAMILY)
        return _Kind(*_STRING)
    return None


def _token_name(variable: Mapping[str, Any], kind: _Kind) -> str:
    slug = slugify(str(variable.get("name", "")), fallback=slugify(str(variable.get("id", ""))))
    for word in kind.strip:
        if slug.startswith(word + "-"):
            slug = slug[len(word) + 1 :]
            break
    return kind.prefix + slug


def _format(value: Any, kind: _Kind) -> str | None:
    if kind.value_kind == "color":
        return to_css(value) if is_color(value) else None
    if kind.value_kind == "string":
        return css_string(value) if isinstance(value, str) else None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return px(value) if kind.value_kind == "px" else fmt_number(value)


def _is_alias(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("type") == "VARIABLE_ALIAS"


class _Resolver:
    def __init__(
        self,
        variables: Mapping[str, Mapping[str, Any]],
        collections: Mapping[str, Mapping[str, Any]],
        names: dict[str, str],
        kinds: dict[str, _Kind],
        warnings: list[str],
        inline_aliases: bool,
    ) -> None:
        self.variables = variables
        self.collections = collections
        self.names = names
        self.kinds = kinds
        self.warnings = warnings
        self.inline_aliases = inline_aliases

    def mode_id(self, variable: Mapping[str, Any], mode_name: str | None) -> str | None:
        """The mode of ``variable``'s collection called ``mode_name``, else its default."""
        collection = self.collections.get(variable.get("variableCollectionId", ""))
        if not collection:
            return None
        if mode_name:
            for mode in collection.get("modes", []):
                if str(mode.get("name", "")).lower() == mode_name.lower():
                    return mode.get("modeId")
        return collection.get("defaultModeId")

    def value(
        self,
        variable: Mapping[str, Any],
        mode_name: str | None,
        _seen: frozenset[str] = frozenset(),
        mode_id: str | None = None,
    ) -> str | None:
        """CSS value for ``variable`` in the named mode (``var(...)`` for aliases)."""
        var_id = str(variable.get("id", ""))
        kind = self.kinds.get(var_id)
        if kind is None:
            return None
        if var_id in _seen or len(_seen) > MAX_ALIAS_DEPTH:
            self.warnings.append(f"alias cycle through variable {variable.get('name')!r}")
            return None
        values = variable.get("valuesByMode")
        if not isinstance(values, Mapping):
            return None
        chosen = mode_id or self.mode_id(variable, mode_name)
        raw = values.get(chosen)
        if raw is None:
            collection = self.collections.get(variable.get("variableCollectionId", ""), {})
            raw = values.get(collection.get("defaultModeId"))
        if _is_alias(raw):
            target = self.variables.get(raw.get("id", ""))
            if target is None or str(target.get("id", "")) not in self.kinds:
                self.warnings.append(
                    f"variable {variable.get('name')!r} aliases {raw.get('id')!r}, which is not "
                    "in this response (remote library variable?); skipped"
                )
                return None
            if not self.inline_aliases:
                return self._checked_reference(variable, target, mode_name)
            return self.value(target, mode_name, _seen | {var_id})
        css = _format(raw, kind)
        if css is None:
            self.warnings.append(
                f"variable {variable.get('name')!r} has a value that is not a valid "
                f"{variable.get('resolvedType')} ; skipped"
            )
        return css

    def _checked_reference(
        self, variable: Mapping[str, Any], target: Mapping[str, Any], mode_name: str | None
    ) -> str | None:
        """``var(--target)`` after making sure the alias chain terminates."""
        probe: Mapping[str, Any] = target
        seen = {str(variable.get("id", ""))}
        for _ in range(MAX_ALIAS_DEPTH):
            probe_id = str(probe.get("id", ""))
            if probe_id in seen:
                self.warnings.append(f"alias cycle through variable {variable.get('name')!r}")
                return None
            seen.add(probe_id)
            values = probe.get("valuesByMode")
            raw = None
            if isinstance(values, Mapping):
                raw = values.get(self.mode_id(probe, mode_name))
            if not _is_alias(raw):
                return f"var({self.names[str(target.get('id', ''))]})"
            nxt = self.variables.get(raw.get("id", ""))
            if nxt is None:
                self.warnings.append(
                    f"variable {probe.get('name')!r} aliases a variable that is not in "
                    "this response; skipped"
                )
                return None
            probe = nxt
        self.warnings.append(f"alias chain from {variable.get('name')!r} is too deep; skipped")
        return None


def extract_variables(
    payload: Any,
    builder: TokenBuilder,
    *,
    mode: str | None = None,
    inline_aliases: bool = False,
    warnings: list[str] | None = None,
) -> dict[str, Tokens]:
    """Add every usable variable to ``builder``; return per-mode overrides.

    ``mode`` names the mode to use as the base value in every collection that has it
    (others use their default mode). The return value maps each *other* mode name to
    the tokens whose value differs from the base, ready to be wrapped in a selector.
    Aliases become ``var(--target)`` unless ``inline_aliases`` is set.
    """
    warn = warnings if warnings is not None else []
    if not isinstance(payload, Mapping):
        raise VariableError("variables payload must be a JSON object")
    if payload.get("error") is True:
        raise VariableError(f"Figma returned an error: {payload.get('message', 'unknown error')}")
    meta = payload.get("meta") if isinstance(payload.get("meta"), Mapping) else payload
    variables = meta.get("variables")
    collections = meta.get("variableCollections")
    if not isinstance(variables, Mapping) or not isinstance(collections, Mapping):
        raise VariableError(
            "not a variables response: expected meta.variables and meta.variableCollections"
        )

    kinds: dict[str, _Kind] = {}
    names: dict[str, str] = {}
    skipped = 0
    for var_id, variable in variables.items():
        if not isinstance(variable, Mapping):
            continue
        variable = {**variable, "id": variable.get("id", var_id)}
        kind = _classify(variable)
        if kind is None:
            skipped += 1
            continue
        kinds[str(variable["id"])] = kind
        names[str(variable["id"])] = builder.reserve(_token_name(variable, kind))
    if skipped:
        warn.append(f"skipped {skipped} boolean variable(s): they have no CSS value")

    index = {
        str(v.get("id", k)): {**v, "id": v.get("id", k)}
        for k, v in variables.items()
        if isinstance(v, Mapping)
    }
    if mode and not any(
        str(m.get("name", "")).lower() == mode.lower()
        for c in collections.values()
        if isinstance(c, Mapping)
        for m in c.get("modes", [])
    ):
        warn.append(f"no variable collection has a mode called {mode!r}; using default modes")
    resolver = _Resolver(index, collections, names, kinds, warn, inline_aliases)

    overrides: dict[str, Tokens] = {}
    for var_id, variable in index.items():
        kind = kinds.get(var_id)
        if kind is None:
            continue
        base = resolver.value(variable, mode)
        if base is None:
            continue
        builder.set(kind.category, names[var_id], base)
        collection = collections.get(variable.get("variableCollectionId", ""), {})
        base_mode = resolver.mode_id(variable, mode)
        for other in collection.get("modes", []):
            if other.get("modeId") == base_mode:
                continue
            other_name = str(other.get("name", other.get("modeId")))
            value = resolver.value(variable, other_name, mode_id=other.get("modeId"))
            if value is not None and value != base:
                slot = overrides.setdefault(other_name, {})
                slot.setdefault(kind.category, {})[names[var_id]] = value
    return overrides
