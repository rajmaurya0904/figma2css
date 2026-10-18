"""Turn Figma layer/style/variable names and numbers into CSS-safe pieces."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(name: str, fallback: str = "unnamed") -> str:
    """Lower-case, ASCII-fold and hyphenate a name.

    ``"Brand / Primary Blue"`` becomes ``"brand-primary-blue"``. A name with no
    usable characters (for example only emoji) becomes ``fallback``.
    """
    folded = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    slug = _NON_ALNUM.sub("-", folded.lower()).strip("-")
    return slug or fallback


def fmt_number(value: float | int, places: int = 4) -> str:
    """Format a number without trailing zeros: ``24.0`` -> ``24``, ``0.50`` -> ``0.5``."""
    number = round(float(value), places)
    if number == int(number):
        return str(int(number))
    return f"{number:.{places}f}".rstrip("0").rstrip(".")


def px(value: float | int) -> str:
    """Format a pixel length. Zero is written as ``0`` per CSS convention."""
    text = fmt_number(value)
    return "0" if text in ("0", "-0") else f"{text}px"


def number_slug(value: float | int) -> str:
    """Slug for a numeric value, used for scale names: ``12.5`` -> ``12-5``."""
    text = fmt_number(value)
    if text.startswith("-"):
        text = "n" + text[1:]
    return text.replace(".", "-")


def css_string(text: str) -> str:
    """Quote ``text`` as a CSS string, escaping quotes, backslashes and newlines."""
    escaped = str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\A ")
    return f'"{escaped}"'


class NameRegistry:
    """Hands out unique custom-property names, suffixing ``-2``, ``-3`` on clashes."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def claim(self, name: str) -> str:
        candidate = name
        counter = 2
        while candidate in self._used:
            candidate = f"{name}-{counter}"
            counter += 1
        self._used.add(candidate)
        return candidate

    def __contains__(self, name: str) -> bool:
        return name in self._used
