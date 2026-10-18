"""Render tokens as CSS custom properties."""

from __future__ import annotations

from collections.abc import Mapping

from .tokens import Tokens

DEFAULT_MODE_SELECTOR = '[data-theme="{mode}"]'


def _property_name(category: str, key: str) -> str:
    """Keys that are already custom properties are used verbatim."""
    return key if key.startswith("--") else f"--{category}-{key}"


def _block(selector: str, tokens: Mapping[str, Mapping[str, str]]) -> str:
    sections = []
    for category, items in tokens.items():
        if not items:
            continue
        lines = [f"  /* {category} */"]
        lines += [f"  {_property_name(category, key)}: {value};" for key, value in items.items()]
        sections.append("\n".join(lines))
    if not sections:
        return f"{selector} {{}}"
    return f"{selector} {{\n" + "\n\n".join(sections) + "\n}"


def mode_selector(template: str, mode: str) -> str:
    """Fill ``{mode}`` in a selector template with the lower-cased mode name."""
    return template.replace("{mode}", mode.strip().lower().replace('"', ""))


def tokens_to_css(
    tokens: Tokens,
    selector: str = ":root",
    modes: Mapping[str, Tokens] | None = None,
    mode_selector_template: str = DEFAULT_MODE_SELECTOR,
) -> str:
    """Format tokens as ``selector { --name: value; }`` blocks.

    Tokens are grouped under a comment per category. A key that already starts with
    ``--``, as produced by :func:`figma2css.core.extract_tokens`, is used verbatim; a
    bare key such as ``primary`` becomes ``--<category>-primary``. ``modes`` maps a
    mode name to the tokens that differ in that mode; each gets its own block.
    """
    blocks = [_block(selector, tokens)]
    for name, mode_tokens in (modes or {}).items():
        blocks.append(_block(mode_selector(mode_selector_template, name), mode_tokens))
    return "\n\n".join(blocks)
