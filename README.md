# figma2css

**Reads a Figma file (saved JSON or fetched live with your own token) and prints its styles and variables as CSS custom properties, for frontend developers who are tired of copying hex codes out of the inspector.**

## The problem

The handoff is always the same: a Figma frame, and you with the colour picker open,
typing `#216bed` into a stylesheet for the fourth time and quietly getting one digit
wrong. The values are already in the file's JSON, as 0-1 floats, nested a dozen nodes
deep, with the names your designer carefully chose sitting in a different map. This
joins them back up and gives you `--color-brand-primary` instead of `--color-1`.

## Real output

Run against the sample file in `tests/fixtures` (a Figma file response plus a local
variables response; first 24 lines of the real output):

```console
$ figma2css tests/fixtures/file_response.json --variables tests/fixtures/variables_local.json | head -n 24
warning: skipped 1 boolean variable(s): they have no CSS value
:root {
  /* colors */
  --color-bg-page: #ffffff;
  --color-text-default: #111724;
  --color-accent: var(--color-blue-600);
  --color-blue-600: #216bed;
  --color-blue-400: #699ef7;
  --color-brand-primary: #216bed;
  --color-brand-surface: #ffffff;
  --color-neutral-text: #111724;
  --gradient-hero: linear-gradient(90deg, #216bed 0%, #7c3aed 100%);
  --color-overlay-scrim: rgba(0, 0, 0, 0.5);
  --color-ff5a1f: #ff5a1f;

  /* typography */
  --font-family-sans: "Inter";
  --font-size-lg: 20px;
  --font-label-caps-family: "Inter";
  --font-label-caps-size: 12px;
  --font-label-caps-weight: 600;
  --font-label-caps-line-height: 16px;
  --font-label-caps-letter-spacing: 0.6px;
  --font-label-caps-text-transform: uppercase;
```

The same run goes on to emit spacing, radii, shadows and a `[data-theme="dark"]` block
for the variables that change in dark mode. A smaller slice:

```console
$ figma2css tests/fixtures/file_response.json --variables tests/fixtures/variables_local.json --only effects,radii -q
:root {
  /* radii */
  --radius-md: 8px;
  --radius-4: 4px;
  --radius-12: 12px;

  /* effects */
  --shadow-elevation-card: 0 1px 2px 0 rgba(0, 0, 0, 0.08), 0 8px 24px -4px rgba(17, 23, 36, 0.16);
  --backdrop-blur-glass-blur: blur(10px);
}
```

Without a token, a live fetch refuses to run and says what to do (exit code 3):

```console
$ figma2css https://www.figma.com/design/AbCdEfGhIjKlMnOp/Acme
Error: FIGMA_TOKEN is not set. Create a personal access token in Figma (Settings > Security > Personal access tokens, scope file_content:read), export it as FIGMA_TOKEN, and run again. Or pass a JSON file you saved earlier instead of a Figma URL.
```

## Install

Not on PyPI. Clone the repository and install from the working tree (Python 3.11+,
no runtime dependencies):

```bash
pip install -e .
```

## Usage

```bash
figma2css file.json                                   # a file saved from GET /v1/files/:key
figma2css file.json --variables vars.json -o tokens.css   # add Figma variables, write a file
figma2css "https://www.figma.com/design/<key>/Name" --save raw/   # live fetch, keep the raw JSON
figma2css file.json --styled-only --prefix ds --format json       # named tokens only, as JSON
```

For a live fetch, create a personal access token in Figma (Settings, Security) and
export it. The token is read only from the environment, never from an argument:

```bash
export FIGMA_TOKEN=...        # PowerShell: $env:FIGMA_TOKEN = "..."
figma2css "https://www.figma.com/design/<key>/Name?node-id=12-34"   # just that node
```

Other flags: `--mode Dark` (base values from another variable mode), `--inline-aliases`
(write values instead of `var(--other)`), `--only colors,spacing`, `--selector .theme`,
`--mode-selector '.{mode}'`, `-q`. Exit codes: 0 ok, 1 bad input, 2 bad arguments,
3 token missing or rejected, 4 network or API error.

## How it works

- A Figma file response keeps style names in a `styles` map and the values on the nodes
  that use them. The walker reads each named style's value from the first visible node
  that references it: fills, text, effects and layout grids.
- Fill styles become `--color-<name>` (solid, with paint opacity as `rgba()`) or
  `--gradient-<name>` (linear and radial; stop positions are corrected for the box shape).
  Text styles expand to `--font-<name>-family/size/weight/line-height/letter-spacing`.
  Effect styles become `box-shadow` lists and `blur()` values.
- Things used without a style are collected as scales: colours named by hex, font
  families, sizes and weights, auto-layout gaps and padding, grid gutters and corner
  radii. A value that a named token already provides is not repeated.
- Local variables (`GET /v1/files/:key/variables/local`) are classified by type and scope
  into colours, spacing, radii, typography and other. Aliases become `var()` references,
  and every non-default mode becomes a block with only the values that differ.
- Hidden nodes and paints are skipped, and names are unique across styles and variables.

## Limitations

- **The live fetch has not been run against api.figma.com.** No real token was available
  while building this. The client is tested against a local HTTP server that imitates the
  documented endpoints, and the JSON fixtures were written by hand to match the documented
  response shapes, not exported from a real account. Treat the first real run as a test.
- Variables need the `file_variables:read` scope and an Enterprise plan. If the endpoint
  refuses, the run continues with styles and prints a warning.
- Not read: image fills, angular and diamond gradients, text-range overrides, component
  variants, boolean variables, and node-level opacity. Radial gradient rotation is ignored.
- Layered fills in one style use only the top layer (with a warning).
- Layer blur is written as `blur(radius / 2)`, the usual equivalence between Figma's
  radius and CSS's standard deviation. Check it against your design.
- Remote library variables that are not in the response are skipped with a warning.
- Spacing and sizes assume Figma pixels and are written in `px`.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

The golden file `tests/fixtures/expected.css` pins the CLI output; the comment at the
top of `tests/test_golden.py` shows how to regenerate it.

MIT, see [LICENSE](LICENSE).
