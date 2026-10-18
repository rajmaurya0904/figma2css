"""Tests for figma2css.api, run against a local HTTP server (no real Figma, no real token)."""

import pytest

from figma2css.api import (
    FigmaApiError,
    FigmaClient,
    MissingTokenError,
    get_token,
    looks_like_figma_source,
    parse_source,
)

from .fakeapi import FakeFigma

KEY = "AbCdEfGhIjKlMnOp"
FAKE_TOKEN = "figd_not-a-real-token-for-tests"


def test_get_token_reads_only_figma_token() -> None:
    assert get_token({"FIGMA_TOKEN": "  abc  "}) == "abc"


@pytest.mark.parametrize("env", [{}, {"FIGMA_TOKEN": ""}, {"FIGMA_TOKEN": "   "}])
def test_get_token_missing_raises_with_instructions(env) -> None:
    with pytest.raises(MissingTokenError) as info:
        get_token(env)
    assert info.value.kind == "token"
    assert "FIGMA_TOKEN is not set" in str(info.value)
    assert "export" in str(info.value)


def test_client_refuses_an_empty_token() -> None:
    with pytest.raises(MissingTokenError):
        FigmaClient("")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (KEY, (KEY, None)),
        (f"https://www.figma.com/file/{KEY}/My-File", (KEY, None)),
        (f"https://www.figma.com/design/{KEY}/My-File?node-id=12-34&t=x", (KEY, "12:34")),
        (f"https://figma.com/proto/{KEY}/Flow", (KEY, None)),
        (f"https://www.figma.com/board/{KEY}/Board", (KEY, None)),
        (f"https://www.figma.com/design/{KEY}/branch/Branch123456/Name", ("Branch123456", None)),
    ],
)
def test_parse_source(source, expected) -> None:
    assert parse_source(source) == expected


@pytest.mark.parametrize(
    "source",
    ["design.json", "short", "https://evil.example/design/AbCdEfGhIjKlMnOp/x", "ftp://figma.com/file/AbCdEfGhIjKl"],
)
def test_parse_source_rejects_non_figma(source) -> None:
    assert parse_source(source, strict=False) is None
    assert not looks_like_figma_source(source)
    with pytest.raises(FigmaApiError):
        parse_source(source)


def test_plain_http_base_is_refused_for_remote_hosts() -> None:
    with pytest.raises(FigmaApiError, match="refusing to send credentials"):
        FigmaClient(FAKE_TOKEN, base_url="http://api.example.com")


def test_https_base_is_accepted() -> None:
    assert FigmaClient(FAKE_TOKEN, base_url="https://proxy.example.com/").base_url == (
        "https://proxy.example.com"
    )


def test_file_request_sends_token_header_and_returns_json(file_response) -> None:
    routes = {f"/v1/files/{KEY}": (200, file_response, {})}
    with FakeFigma(routes) as server:
        data = FigmaClient(FAKE_TOKEN, base_url=server.url).file(KEY)
    assert data["name"] == "Acme Design System"
    request = server.requests[0]
    assert request["headers"]["x-figma-token"] == FAKE_TOKEN
    assert request["headers"]["user-agent"].startswith("figma2css/")


def test_nodes_request_encodes_ids(nodes_response) -> None:
    routes = {f"/v1/files/{KEY}/nodes": (200, nodes_response, {})}
    with FakeFigma(routes) as server:
        FigmaClient(FAKE_TOKEN, base_url=server.url).nodes(KEY, ["2:3", "5:6"])
    assert server.requests[0]["path"] == f"/v1/files/{KEY}/nodes?ids=2%3A3%2C5%3A6"


def test_variables_request(variables_response) -> None:
    routes = {f"/v1/files/{KEY}/variables/local": (200, variables_response, {})}
    with FakeFigma(routes) as server:
        data = FigmaClient(FAKE_TOKEN, base_url=server.url).local_variables(KEY)
    assert "variableCollections" in data["meta"]


@pytest.mark.parametrize(
    ("status", "body", "kind"),
    [
        (403, {"status": 403, "err": "Invalid token"}, "token"),
        (401, {"status": 401, "err": "unauthorized"}, "token"),
        (404, {"status": 404, "err": "Not found"}, "not-found"),
        (500, {"status": 500, "err": "boom"}, "server"),
        (400, {"status": 400, "err": "bad"}, "response"),
    ],
)
def test_http_errors_map_to_kinds_and_never_leak_the_token(status, body, kind) -> None:
    with FakeFigma({f"/v1/files/{KEY}": (status, body, {})}) as server:
        with pytest.raises(FigmaApiError) as info:
            FigmaClient(FAKE_TOKEN, base_url=server.url).file(KEY)
    assert info.value.kind == kind
    assert info.value.status == status
    assert FAKE_TOKEN not in str(info.value)


def test_403_message_includes_figmas_own_reason() -> None:
    routes = {f"/v1/files/{KEY}": (403, {"status": 403, "err": "Invalid token"}, {})}
    with FakeFigma(routes) as server, pytest.raises(FigmaApiError, match="Invalid token"):
        FigmaClient(FAKE_TOKEN, base_url=server.url).file(KEY)


def test_rate_limit_reports_retry_after() -> None:
    routes = {f"/v1/files/{KEY}": (429, {"status": 429, "err": "slow down"}, {"Retry-After": "42"})}
    with FakeFigma(routes) as server:
        with pytest.raises(FigmaApiError) as info:
            FigmaClient(FAKE_TOKEN, base_url=server.url).file(KEY)
    assert info.value.kind == "rate-limit"
    assert "42 seconds" in str(info.value)


def test_non_json_body_is_a_response_error() -> None:
    routes = {f"/v1/files/{KEY}": (200, b"<html>captive portal</html>", {})}
    with FakeFigma(routes) as server, pytest.raises(FigmaApiError, match="not valid JSON"):
        FigmaClient(FAKE_TOKEN, base_url=server.url).file(KEY)


def test_connection_refused_is_a_network_error() -> None:
    with FakeFigma({}) as server:
        url = server.url
    with pytest.raises(FigmaApiError) as info:
        FigmaClient(FAKE_TOKEN, base_url=url, timeout=2).file(KEY)
    assert info.value.kind == "network"
    assert FAKE_TOKEN not in str(info.value)
