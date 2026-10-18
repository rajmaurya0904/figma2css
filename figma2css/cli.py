"""Command line interface: ``figma2css SOURCE``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .api import (
    TOKEN_ENV,
    FigmaApiError,
    FigmaClient,
    get_token,
    parse_source,
)
from .core import CATEGORIES, FigmaDataError, extract
from .css import DEFAULT_MODE_SELECTOR, tokens_to_css
from .variables import VariableError

EXIT_OK = 0
EXIT_INPUT = 1  # bad file, bad JSON, not Figma data
EXIT_USAGE = 2  # argparse's own code for bad arguments
EXIT_AUTH = 3  # missing, rejected or under-scoped token
EXIT_API = 4  # network failure, rate limit, server error, missing file

DESCRIPTION = """\
Extract design tokens from a Figma file and print them as CSS custom properties.

SOURCE is one of:
  PATH        a JSON file saved from GET /v1/files/:key (or /nodes)
  -           the same JSON on standard input
  URL or KEY  a figma.com file URL or file key; fetched live with the token in
              the FIGMA_TOKEN environment variable
"""

EPILOG = f"""\
exit codes: 0 ok, 1 bad input, 2 bad arguments, 3 token missing or rejected,
4 network or API error. The token is read only from ${TOKEN_ENV}, never from
an argument. Variables need an Enterprise plan and the file_variables:read scope.
"""


class InputError(Exception):
    """A problem with the user's input, reported as ``Error: ...``."""

    def __init__(self, message: str, code: int = EXIT_INPUT) -> None:
        super().__init__(message)
        self.code = code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="figma2css",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source", metavar="SOURCE", help="JSON file, '-' for stdin, or Figma URL/key"
    )
    parser.add_argument("--version", action="version", version=f"figma2css {__version__}")
    parser.add_argument(
        "--variables", metavar="PATH", help="saved GET /v1/files/:key/variables/local JSON"
    )
    parser.add_argument(
        "--no-variables",
        action="store_true",
        help="when fetching live, do not request Figma variables",
    )
    parser.add_argument(
        "--node-id", metavar="ID", help="when fetching live, only this node, e.g. 12:34"
    )
    parser.add_argument(
        "--save", metavar="DIR", help="when fetching live, also save the raw responses in DIR"
    )
    parser.add_argument("-o", "--output", metavar="FILE", help="write here instead of stdout")
    parser.add_argument("--format", choices=("css", "json"), default="css", help="default: css")
    parser.add_argument("--selector", default=":root", help="selector for the base block")
    parser.add_argument(
        "--mode-selector",
        default=DEFAULT_MODE_SELECTOR,
        metavar="TEMPLATE",
        help="selector for other variable modes (default: %(default)s)",
    )
    parser.add_argument("--mode", metavar="NAME", help="variable mode to use as the base values")
    parser.add_argument("--prefix", default="", metavar="NAME", help="namespace: --NAME-color-x")
    parser.add_argument(
        "--only",
        metavar="LIST",
        help=f"comma-separated categories to keep ({', '.join(CATEGORIES)})",
    )
    parser.add_argument(
        "--styled-only",
        action="store_true",
        help="skip values that have no named style or variable",
    )
    parser.add_argument(
        "--inline-aliases",
        action="store_true",
        help="resolve variable aliases to their value instead of var(--other)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="do not print warnings")
    return parser


def _parse_json_text(text: str, label: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(
            f"invalid JSON in {label}: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from None


def _read_json_file(path: str) -> Any:
    target = Path(path)
    if not target.exists():
        raise InputError(f"file not found: {path}")
    try:
        text = target.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read {path}: {exc}") from None
    return _parse_json_text(text, path)


def _read_source(source: str) -> Any:
    if source == "-":
        return _parse_json_text(sys.stdin.read(), "standard input")
    return _read_json_file(source)


def _is_local(source: str) -> bool:
    return source == "-" or Path(source).exists()


def _save(directory: str, name: str, data: Any) -> None:
    target = Path(directory)
    try:
        target.mkdir(parents=True, exist_ok=True)
        (target / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot save {name} in {directory}: {exc}") from None


def fetch_live(args: argparse.Namespace, warnings: list[str]) -> tuple[Any, Any]:
    """Fetch file (or node) data, and variables unless skipped, with ``FIGMA_TOKEN``."""
    ref = parse_source(args.source)
    assert ref is not None  # strict parse either returns or raises
    key, url_node = ref
    client = FigmaClient(get_token())
    node_id = args.node_id or url_node
    data = client.nodes(key, [node_id]) if node_id else client.file(key)
    if args.save:
        _save(args.save, f"{key}.file.json", data)
    variables = None
    if args.variables is None and not args.no_variables:
        try:
            variables = client.local_variables(key)
        except FigmaApiError as exc:
            if exc.kind not in ("token", "not-found"):
                raise
            warnings.append(
                "skipped Figma variables: the variables endpoint refused the request "
                f"(HTTP {exc.status}); it needs an Enterprise plan and the "
                "file_variables:read scope. Styles were still extracted."
            )
        if variables is not None and args.save:
            _save(args.save, f"{key}.variables.json", variables)
    return data, variables


def _filter(tokens: dict[str, dict[str, str]], keep: set[str]) -> dict[str, dict[str, str]]:
    return {category: items for category, items in tokens.items() if category in keep}


def _categories_to_keep(only: str | None) -> set[str]:
    if not only:
        return set(CATEGORIES)
    keep = {name.strip() for name in only.split(",") if name.strip()}
    unknown = sorted(keep - set(CATEGORIES))
    if unknown:
        raise InputError(
            f"unknown category {', '.join(unknown)} in --only (choose from "
            f"{', '.join(CATEGORIES)})",
            EXIT_USAGE,
        )
    return keep


def run(args: argparse.Namespace) -> int:
    warnings: list[str] = []
    keep = _categories_to_keep(args.only)
    if _is_local(args.source):
        data = _read_source(args.source)
        variables = _read_json_file(args.variables) if args.variables else None
    elif parse_source(args.source, strict=False):
        data, fetched = fetch_live(args, warnings)
        variables = _read_json_file(args.variables) if args.variables else fetched
    else:
        raise InputError(f"file not found: {args.source}")

    try:
        result = extract(
            data,
            variables,
            mode=args.mode,
            styled_only=args.styled_only,
            inline_aliases=args.inline_aliases,
            prefix=args.prefix,
        )
    except (FigmaDataError, VariableError) as exc:
        raise InputError(str(exc)) from None

    tokens = _filter(result.tokens, keep)
    modes = {m: _filter(t, keep) for m, t in result.modes.items()}
    modes = {m: t for m, t in modes.items() if any(t.values())}
    warnings.extend(result.warnings)
    if not tokens and not modes:
        warnings.append("no design tokens found in the input")

    if args.format == "json":
        document: dict[str, Any] = {"tokens": tokens}
        if modes:
            document["modes"] = modes
        text = json.dumps(document, indent=2, ensure_ascii=False)
    else:
        text = tokens_to_css(tokens, args.selector, modes, args.mode_selector)

    if args.output:
        try:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            raise InputError(f"cannot write {args.output}: {exc}") from None
    else:
        sys.stdout.write(text + "\n")

    if not args.quiet:
        for message in warnings:
            print(f"warning: {message}", file=sys.stderr)
        if args.output:
            count = sum(len(v) for v in tokens.values()) + sum(
                len(v) for t in modes.values() for v in t.values()
            )
            print(f"wrote {count} tokens to {args.output}", file=sys.stderr)
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except InputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.code
    except FigmaApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_AUTH if exc.kind == "token" else EXIT_API
    except BrokenPipeError:
        return EXIT_OK
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
