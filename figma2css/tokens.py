"""The token container shared by the style walker and the variables reader."""

from __future__ import annotations

from .naming import NameRegistry

CATEGORIES = ("colors", "typography", "spacing", "radii", "effects", "other")

Tokens = dict[str, dict[str, str]]


class TokenBuilder:
    """Collects tokens per category and guarantees unique custom-property names."""

    def __init__(self, prefix: str = "") -> None:
        """``prefix`` (for example ``"ds"``) turns ``--color-x`` into ``--ds-color-x``."""
        self._tokens: Tokens = {category: {} for category in CATEGORIES}
        self._names = NameRegistry()
        cleaned = prefix.strip().strip("-")
        self._prefix = f"--{cleaned}-" if cleaned else "--"

    def reserve(self, name: str) -> str:
        """Claim a unique name without storing a value yet."""
        if name.startswith("--"):
            name = self._prefix + name[2:]
        return self._names.claim(name)

    def add(self, category: str, name: str, value: str) -> str:
        """Store ``value`` under a unique version of ``name`` and return the final name."""
        final = self.reserve(name)
        self.set(category, final, value)
        return final

    def set(self, category: str, name: str, value: str) -> None:
        """Store a value under an already reserved name."""
        if category not in self._tokens:
            raise KeyError(f"unknown token category {category!r}")
        self._tokens[category][name] = value

    def values(self, category: str, *name_parts: str) -> set[str]:
        """Values already stored in ``category``.

        With ``name_parts`` only tokens whose name matches one of them count, so a font
        size is not compared with a line height. A part ending in ``-`` matches
        anywhere in the name (``font-size-``); one starting with ``-`` matches the end.
        """

        def matches(name: str) -> bool:
            return not name_parts or any(
                part in name if part.endswith("-") else name.endswith(part)
                for part in name_parts
            )

        return {value for name, value in self._tokens[category].items() if matches(name)}

    def result(self) -> Tokens:
        """Non-empty categories, in the canonical category order."""
        return {category: dict(items) for category, items in self._tokens.items() if items}
