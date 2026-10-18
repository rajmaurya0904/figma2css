---
name: figma2css
description: Extract design tokens (colours, gradients, typography, spacing, radii, shadows, blurs, variables) from a Figma file and write them as CSS custom properties. Use when the user shares a Figma file URL, key or saved JSON and wants a :root block or a theme stylesheet.
---

# figma2css

Turns a Figma file into CSS custom properties with the `figma2css` command. Install it
once from the repository with `pip install -e .`.

## When to use

The user gives you a figma.com file URL, a file key, or a JSON file saved from the
Figma REST API, and wants design tokens as CSS.

## Steps

1. If the input is a saved JSON file, run `figma2css path/to/file.json`.
2. If it is a Figma URL or key, check that `FIGMA_TOKEN` is set in the environment
   (`echo` its length, never its value). If it is not set, stop and ask the user to
   create a personal access token in Figma (Settings, Security) with the
   `file_content:read` scope and export it as `FIGMA_TOKEN`. Never ask the user to
   paste a token into the chat and never put one on a command line or in a file.
3. Run `figma2css "<url>" -o tokens.css`. Add `--save raw/` to keep the API responses
   so later runs work offline.
4. Variables (with Light/Dark modes) are fetched too when the plan allows it; add
   `--variables vars.json` to use a saved response. Other modes come out as
   `[data-theme="dark"]` blocks.
5. Read the output before wiring it in. Tokens named after a Figma style or variable
   are semantic (`--color-brand-primary`); values with no style are named after the
   value (`--color-ff5a1f`) and probably deserve a proper name.

## Useful flags

- `--styled-only` keeps only tokens that have a name in Figma.
- `--only colors,typography` limits the categories.
- `--prefix ds` namespaces every property as `--ds-...`.
- `--format json` prints the tokens as JSON instead of CSS.

## Exit codes

0 ok, 1 bad input, 2 bad arguments, 3 token missing or rejected, 4 network or API
error. A missing token is reported with instructions, not a stack trace.

## Limits to tell the user about

Image fills, angular and diamond gradients, text-range overrides and component
variants are not read. Radial gradient rotation is ignored. See README.md.
