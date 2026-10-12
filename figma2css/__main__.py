"""Command line entry point for figma2css.

Provides a minimal CLI that reads a JSON file and reports errors.
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="figma2css")
    parser.add_argument("json_file", help="Path to a JSON file to process")
    args = parser.parse_args()
    json_path = Path(args.json_file)
    try:
        with json_path.open() as f:
            json.load(f)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    # For now, successful parsing does nothing.
    # Future functionality would process the JSON.


if __name__ == "__main__":
    main()
