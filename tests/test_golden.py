"""Golden-file test: the CLI output for the fixtures is pinned in tests/fixtures/expected.css.

If you change naming or formatting on purpose, regenerate it with:

    figma2css tests/fixtures/file_response.json \
        --variables tests/fixtures/variables_local.json -q > tests/fixtures/expected.css
"""

import io
import re
from contextlib import redirect_stdout

from figma2css.cli import main


def test_cli_output_matches_the_golden_file(fixtures_dir) -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(
            [
                str(fixtures_dir / "file_response.json"),
                "--variables",
                str(fixtures_dir / "variables_local.json"),
                "-q",
            ]
        )
    assert code == 0
    expected = (fixtures_dir / "expected.css").read_text(encoding="utf-8")
    assert buffer.getvalue().replace("\r\n", "\n") == expected.replace("\r\n", "\n")


def test_every_custom_property_in_the_golden_file_is_declared_once(fixtures_dir) -> None:
    css = (fixtures_dir / "expected.css").read_text(encoding="utf-8")
    root = css.split("[data-theme", 1)[0]
    names = [
        line.split(":", 1)[0].strip()
        for line in root.splitlines()
        if line.strip().startswith("--")
    ]
    assert len(names) == len(set(names)) > 20


def test_every_var_reference_in_the_golden_file_resolves(fixtures_dir) -> None:
    css = (fixtures_dir / "expected.css").read_text(encoding="utf-8")
    declared = set(re.findall(r"^\s+(--[\w-]+):", css, re.MULTILINE))
    referenced = set(re.findall(r"var\((--[\w-]+)\)", css))
    assert referenced and referenced <= declared
