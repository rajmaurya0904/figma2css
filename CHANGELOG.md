# Changelog

## [Unreleased]

## [0.1.0]

- `figma2css` command: reads a saved Figma file or nodes response (path or stdin) or
  fetches one live with `FIGMA_TOKEN`, and prints CSS custom properties or JSON.
- Reads fill styles (solid, linear and radial gradients, alpha), text styles, effect
  styles (drop and inner shadows, layer and background blur) and layout grid styles.
- Collects unstyled spacing (auto layout gap and padding, grid gutters), corner radii
  and fonts as value scales.
- Reads local variables with modes, aliases and type-based categories.
- Clear errors and distinct exit codes for a missing or rejected token, unreachable
  API, bad input files and bad JSON.
