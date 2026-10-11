# figma2css

**Walks a Figma REST API file dump and turns the solid fills and column-grid gutters it finds into a block of CSS custom properties.**

**Status: early and incomplete.** The extraction and formatting functions work on a
Figma JSON document you have already downloaded. The `figma2css` command exists but
is a stub — it prints `figma2css CLI` and exits, whatever you pass it. Nothing talks
to the Figma API, and `SKILL.md` is still a placeholder.

## The problem

The handoff is always the same: a Figma frame, and you with the colour picker open,
typing `#216bed` into a stylesheet for the fourth time and quietly getting one digit
wrong. The hex values are already in the file's JSON, as floats, nested a dozen nodes
deep. This pulls them out and dedupes them.

## Real output

A trimmed Figma document — three distinct fills (one repeated) and a column grid:

```json
{
  "document": {
    "layoutGrids": [{"pattern": "COLUMNS", "gutterSize": 24}],
    "children": [
      {"name": "Button", "fills": [{"type": "SOLID", "color": {"r": 0.13, "g": 0.42, "b": 0.93}}]},
      {"name": "Card", "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}}],
       "children": [
         {"name": "Label", "fills": [{"type": "SOLID", "color": {"r": 0.07, "g": 0.09, "b": 0.14}}]},
         {"name": "Dup", "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}}]}
       ]}
    ]
  }
}
```

```console
$ python run.py
{
  "colors": {
    "--color-1": "#216bed",
    "--color-2": "#ffffff",
    "--color-3": "#121724"
  },
  "spacing": {
    "--spacing-1": "24"
  }
}

:root { --color-1: #216bed; --color-2: #ffffff; --color-3: #121724; --spacing-1: 24; }
```

Note that the repeated white fill collapsed into a single token, and that
`--spacing-1` has no unit — see Limitations.

`run.py`:

```python
import json

from figma2css.core import extract_tokens, tokens_to_css

tokens = extract_tokens(json.load(open("file.json")))
print(json.dumps(tokens, indent=2))
print()
print(tokens_to_css(tokens))
```

## Install

Not on PyPI. Clone it and install from the working tree:

```bash
pip install -e ".[dev]"
```

## Usage

```python
extract_tokens(figma_data)   # dict -> {"colors": {...}, "spacing": {...}}
tokens_to_css(tokens)        # -> ":root { --color-1: #216bed; ... }"
```

```bash
figma2css                    # prints "figma2css CLI" and exits; it reads no input
```

Fetch the JSON yourself, for example with
`curl -H "X-Figma-Token: $TOKEN" https://api.figma.com/v1/files/<key>`, and hand the
parsed dict to `extract_tokens`.

## How it works

- Starts at `figma_data["document"]` and recurses through each node's `children`.
  No `document` key means an empty result.
- For every `fills` entry of `"type": "SOLID"`, reads `color.r/g/b` as 0–1 floats,
  clamps them, rounds to 0–255 and formats `#rrggbb`.
- Colours are deduped by hex and numbered in encounter order: `--color-1`,
  `--color-2`, and so on.
- For every `layoutGrids` entry, takes a non-zero `gutterSize`, dedupes it, and
  numbers it `--spacing-1` upward. Whole floats are printed without the `.0`.
- `tokens_to_css` joins everything onto one `:root { ... }` line, using keys that
  already start with `--` verbatim and prefixing bare keys with their category.
- Empty input gives `:root {}`.

## Limitations

- **No Figma API client.** You supply the JSON; nothing authenticates or downloads.
- The CLI is a stub: no arguments, no file input, no `--help` handling, no output.
- Token names are positional (`--color-1`), not semantic. Figma layer, style and
  variable names are never read, so the output needs renaming by hand.
- `--spacing-*` values carry no unit, so `--spacing-1: 24` is not valid CSS as it
  stands.
- Only solid fills are read. Gradients, images, strokes and effects are skipped, and
  `fill.opacity` and node opacity are ignored — so a 50%-opaque colour is recorded as
  if it were opaque.
- Only `gutterSize` is read from a layout grid. `sectionSize`, `offset` and
  `alignment` are dropped, and padding and auto-layout spacing are not examined
  at all.
- No typography, radius, shadow or breakpoint tokens.
- Output is a single long line with no sorting, grouping or trailing newline.
- `SKILL.md` has no instructions in it, so the "Claude Code skill" in the project
  description does not exist yet.

## Development

```bash
pip install -e ".[dev]"
pytest -q        # 5 tests
ruff check .
```

MIT — see [LICENSE](LICENSE).
