"""End-to-end tests for the figma2css command line."""

import contextlib
import io
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from figma2css.cli import main

from .fakeapi import FakeFigma

KEY = "AbCdEfGhIjKlMnOp"
URL = f"https://www.figma.com/design/{KEY}/Acme"
FAKE_TOKEN = "figd_not-a-real-token-for-tests"


def run_subprocess(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    """Run the CLI in a real subprocess, the way a user would."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("FIGMA_")}
    return subprocess.run(
        [sys.executable, "-m", "figma2css", *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**env, "PYTHONIOENCODING": "utf-8"},
        timeout=60,
    )


def run_cli(*args: str, stdin: str | None = None) -> SimpleNamespace:
    """Run main() in-process with captured streams (fast; same code path)."""
    out, err = io.StringIO(), io.StringIO()
    real_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin or "")
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(list(args))
            except SystemExit as exc:  # argparse exits for --help, --version, bad usage
                code = exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.stdin = real_stdin
    return SimpleNamespace(returncode=code, stdout=out.getvalue(), stderr=err.getvalue())


def test_help_exits_zero_and_documents_the_token() -> None:
    result = run_subprocess("--help")
    assert result.returncode == 0
    assert "usage: figma2css" in result.stdout
    assert "FIGMA_TOKEN" in result.stdout


def test_version() -> None:
    result = run_cli("--version")
    assert result.returncode == 0
    assert result.stdout.startswith("figma2css ")


def test_cli_run_prints_css_for_a_saved_file(fixtures_dir) -> None:
    result = run_subprocess(str(fixtures_dir / "file_response.json"))
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(":root {\n  /* colors */")
    assert "--color-brand-primary: #216bed;" in result.stdout
    assert "--font-heading-h1-size: 32px;" in result.stdout


def test_cli_missing_file(tmp_path) -> None:
    result = run_subprocess(str(tmp_path / "nonexistent.json"))
    assert result.returncode == 1
    assert "Error: file not found" in result.stderr
    assert result.stdout == ""


def test_cli_invalid_json(tmp_path) -> None:
    bad = tmp_path / "invalid.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    result = run_subprocess(str(bad))
    assert result.returncode == 1
    assert "Error: invalid JSON" in result.stderr
    assert "line 1" in result.stderr


def test_cli_rejects_json_that_is_not_a_figma_file(tmp_path) -> None:
    other = tmp_path / "package.json"
    other.write_text('{"name": "not-figma"}', encoding="utf-8")
    result = run_cli(str(other))
    assert result.returncode == 1
    assert "not a Figma file response" in result.stderr


def test_cli_reports_a_saved_figma_error_body(tmp_path) -> None:
    saved = tmp_path / "error.json"
    saved.write_text('{"status": 403, "err": "Invalid token"}', encoding="utf-8")
    result = run_cli(str(saved))
    assert result.returncode == 1
    assert "Figma API error 403: Invalid token" in result.stderr


def test_cli_rejects_a_directory(tmp_path) -> None:
    result = run_cli(str(tmp_path))
    assert result.returncode == 1
    assert result.stderr.startswith("Error: cannot read")


def test_cli_accepts_a_utf8_bom(tmp_path, file_response) -> None:
    saved = tmp_path / "bom.json"
    saved.write_text(json.dumps(file_response), encoding="utf-8-sig")
    assert run_cli(str(saved)).returncode == 0


def test_cli_reads_standard_input(fixtures_dir) -> None:
    text = (fixtures_dir / "file_response.json").read_text(encoding="utf-8")
    result = run_cli("-", stdin=text)
    assert result.returncode == 0
    assert "--color-brand-primary" in result.stdout


def test_cli_invalid_json_on_stdin() -> None:
    result = run_cli("-", stdin="nope")
    assert result.returncode == 1
    assert "invalid JSON in standard input" in result.stderr


def test_empty_figma_object_gives_empty_root_and_a_warning(tmp_path) -> None:
    saved = tmp_path / "empty.json"
    saved.write_text("{}", encoding="utf-8")
    result = run_cli(str(saved))
    assert result.returncode == 0
    assert result.stdout == ":root {}\n"
    assert "no design tokens found" in result.stderr


def test_quiet_suppresses_warnings(tmp_path) -> None:
    saved = tmp_path / "empty.json"
    saved.write_text("{}", encoding="utf-8")
    assert run_cli(str(saved), "-q").stderr == ""


def test_variables_flag_adds_variable_tokens_and_mode_blocks(fixtures_dir) -> None:
    result = run_cli(
        str(fixtures_dir / "file_response.json"),
        "--variables",
        str(fixtures_dir / "variables_local.json"),
    )
    assert result.returncode == 0
    assert "--color-accent: var(--color-blue-600);" in result.stdout
    assert '[data-theme="dark"] {' in result.stdout


def test_missing_variables_file_is_an_error(fixtures_dir, tmp_path) -> None:
    result = run_cli(
        str(fixtures_dir / "file_response.json"), "--variables", str(tmp_path / "v.json")
    )
    assert result.returncode == 1
    assert "file not found" in result.stderr


def test_mode_and_inline_aliases_flags(fixtures_dir) -> None:
    result = run_cli(
        str(fixtures_dir / "file_response.json"),
        "--variables",
        str(fixtures_dir / "variables_local.json"),
        "--mode",
        "Dark",
        "--inline-aliases",
    )
    assert result.returncode == 0
    assert "--color-accent: #699ef7;" in result.stdout
    assert '[data-theme="light"] {' in result.stdout


def test_json_format(fixtures_dir) -> None:
    result = run_cli(
        str(fixtures_dir / "file_response.json"),
        "--variables",
        str(fixtures_dir / "variables_local.json"),
        "--format",
        "json",
    )
    document = json.loads(result.stdout)
    assert document["tokens"]["colors"]["--color-brand-primary"] == "#216bed"
    assert "colors" in document["modes"]["Dark"]


def test_only_filters_categories(fixtures_dir) -> None:
    result = run_cli(str(fixtures_dir / "file_response.json"), "--only", "spacing,radii")
    assert "/* spacing */" in result.stdout and "/* radii */" in result.stdout
    assert "/* colors */" not in result.stdout


def test_only_rejects_unknown_category(fixtures_dir) -> None:
    result = run_cli(str(fixtures_dir / "file_response.json"), "--only", "colours")
    assert result.returncode == 2
    assert "unknown category colours" in result.stderr


def test_prefix_selector_and_styled_only(fixtures_dir) -> None:
    result = run_cli(
        str(fixtures_dir / "file_response.json"),
        "--prefix",
        "acme",
        "--selector",
        ".theme",
        "--styled-only",
    )
    assert result.stdout.startswith(".theme {")
    assert "--acme-color-brand-primary: #216bed;" in result.stdout
    assert "--acme-color-ff5a1f" not in result.stdout


def test_output_file(fixtures_dir, tmp_path) -> None:
    target = tmp_path / "tokens.css"
    result = run_cli(str(fixtures_dir / "file_response.json"), "-o", str(target))
    assert result.returncode == 0
    assert result.stdout == ""
    assert "--color-brand-primary: #216bed;" in target.read_text(encoding="utf-8")
    assert "wrote " in result.stderr and "tokens to" in result.stderr


def test_unwritable_output_path(fixtures_dir, tmp_path) -> None:
    result = run_cli(
        str(fixtures_dir / "file_response.json"), "-o", str(tmp_path / "no" / "such" / "x.css")
    )
    assert result.returncode == 1
    assert "cannot write" in result.stderr


def test_no_arguments_is_a_usage_error() -> None:
    result = run_cli()
    assert result.returncode == 2
    assert "usage:" in result.stderr


# -- live fetch path, against a local fake of the Figma API ----------------------------


@pytest.fixture
def live_env(monkeypatch):
    def configure(server: FakeFigma, token: str | None = FAKE_TOKEN) -> None:
        monkeypatch.setenv("FIGMA_API_BASE", server.url)
        if token is None:
            monkeypatch.delenv("FIGMA_TOKEN", raising=False)
        else:
            monkeypatch.setenv("FIGMA_TOKEN", token)

    return configure


def test_live_fetch_with_token_prints_css(live_env, capsys, file_response, variables_response):
    routes = {
        f"/v1/files/{KEY}": (200, file_response, {}),
        f"/v1/files/{KEY}/variables/local": (200, variables_response, {}),
    }
    with FakeFigma(routes) as server:
        live_env(server)
        code = main([URL])
    out = capsys.readouterr()
    assert code == 0
    assert "--color-brand-primary: #216bed;" in out.out
    assert "--color-accent: var(--color-blue-600);" in out.out
    assert [r["headers"]["x-figma-token"] for r in server.requests] == [FAKE_TOKEN] * 2
    assert FAKE_TOKEN not in out.out + out.err


def test_live_fetch_accepts_a_bare_key(live_env, capsys, file_response):
    with FakeFigma({f"/v1/files/{KEY}": (200, file_response, {})}) as server:
        live_env(server)
        assert main([KEY, "--no-variables"]) == 0
    assert [r["path"] for r in server.requests] == [f"/v1/files/{KEY}"]
    assert "--color-brand-primary" in capsys.readouterr().out


def test_live_without_a_token_degrades_with_a_clear_error(live_env, capsys):
    with FakeFigma({}) as server:
        live_env(server, token=None)
        code = main([URL])
    err = capsys.readouterr().err
    assert code == 3
    assert err.startswith("Error: FIGMA_TOKEN is not set")
    assert server.requests == []


def test_live_with_a_blank_token_is_treated_as_missing(live_env, capsys):
    with FakeFigma({}) as server:
        live_env(server, token="  ")
        assert main([URL]) == 3
    assert server.requests == []


def test_live_rejected_token_exits_3_without_echoing_it(live_env, capsys):
    routes = {f"/v1/files/{KEY}": (403, {"status": 403, "err": "Invalid token"}, {})}
    with FakeFigma(routes) as server:
        live_env(server)
        code = main([URL])
    err = capsys.readouterr().err
    assert code == 3
    assert "Invalid token" in err
    assert FAKE_TOKEN not in err


def test_live_file_not_found_exits_4(live_env, capsys):
    with FakeFigma({}) as server:
        live_env(server)
        code = main([URL, "--no-variables"])
    assert code == 4
    assert "404" in capsys.readouterr().err


def test_live_unreachable_server_exits_4(live_env, capsys):
    with FakeFigma({}) as server:
        live_env(server)
    assert main([URL, "--no-variables"]) == 4
    assert "could not reach" in capsys.readouterr().err


def test_live_variables_denied_is_only_a_warning(live_env, capsys, file_response):
    routes = {
        f"/v1/files/{KEY}": (200, file_response, {}),
        f"/v1/files/{KEY}/variables/local": (
            403,
            {"status": 403, "err": "Limited by Figma plan"},
            {},
        ),
    }
    with FakeFigma(routes) as server:
        live_env(server)
        code = main([URL])
    out = capsys.readouterr()
    assert code == 0
    assert "--color-brand-primary" in out.out
    assert "skipped Figma variables" in out.err
    assert "Enterprise" in out.err


def test_live_url_node_id_uses_the_nodes_endpoint(live_env, capsys, nodes_response):
    routes = {f"/v1/files/{KEY}/nodes": (200, nodes_response, {})}
    with FakeFigma(routes) as server:
        live_env(server)
        code = main([f"{URL}?node-id=2-3", "--no-variables"])
    assert code == 0
    assert server.requests[0]["path"] == f"/v1/files/{KEY}/nodes?ids=2%3A3"
    assert "--font-heading-h1-size: 32px;" in capsys.readouterr().out


def test_live_node_id_flag_overrides(live_env, capsys, nodes_response):
    routes = {f"/v1/files/{KEY}/nodes": (200, nodes_response, {})}
    with FakeFigma(routes) as server:
        live_env(server)
        main([KEY, "--node-id", "7:8", "--no-variables"])
    assert server.requests[0]["path"].endswith("ids=7%3A8")


def test_live_save_writes_raw_responses(
    live_env, tmp_path, capsys, file_response, variables_response
):
    routes = {
        f"/v1/files/{KEY}": (200, file_response, {}),
        f"/v1/files/{KEY}/variables/local": (200, variables_response, {}),
    }
    with FakeFigma(routes) as server:
        live_env(server)
        assert main([URL, "--save", str(tmp_path / "raw")]) == 0
    saved = json.loads((tmp_path / "raw" / f"{KEY}.file.json").read_text(encoding="utf-8"))
    assert saved["name"] == "Acme Design System"
    assert (tmp_path / "raw" / f"{KEY}.variables.json").exists()
    # and the saved file round-trips through the offline path
    capsys.readouterr()
    assert main([str(tmp_path / "raw" / f"{KEY}.file.json")]) == 0


def test_live_local_variables_file_replaces_the_variables_request(
    live_env, capsys, file_response, fixtures_dir
):
    with FakeFigma({f"/v1/files/{KEY}": (200, file_response, {})}) as server:
        live_env(server)
        code = main([URL, "--variables", str(fixtures_dir / "variables_local.json")])
    assert code == 0
    assert len(server.requests) == 1


def test_non_figma_non_file_source_is_file_not_found(capsys):
    assert main(["definitely-not-a-file.json"]) == 1
    assert "Error: file not found: definitely-not-a-file.json" in capsys.readouterr().err
