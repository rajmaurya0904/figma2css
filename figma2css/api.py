"""A small Figma REST API client built on the standard library.

The personal access token is read only from the ``FIGMA_TOKEN`` environment variable.
It is never accepted as a command-line argument, never written to disk and never
included in an error message.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from . import __version__

TOKEN_ENV = "FIGMA_TOKEN"
BASE_URL_ENV = "FIGMA_API_BASE"
DEFAULT_BASE_URL = "https://api.figma.com"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")

_URL_KEY = re.compile(r"^/(?:file|design|proto|board)/([A-Za-z0-9]+)(?:/branch/([A-Za-z0-9]+))?")
_BARE_KEY = re.compile(r"^[A-Za-z0-9]{10,}$")


class FigmaApiError(Exception):
    """A request to the Figma API failed.

    ``kind`` is one of ``token`` (missing or rejected credentials), ``not-found``,
    ``rate-limit``, ``network``, ``server`` or ``response`` (unusable body).
    """

    def __init__(self, message: str, kind: str = "response", status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


class MissingTokenError(FigmaApiError):
    """``FIGMA_TOKEN`` is not set."""

    def __init__(self) -> None:
        super().__init__(
            f"{TOKEN_ENV} is not set. Create a personal access token in Figma "
            f"(Settings > Security > Personal access tokens, scope file_content:read), "
            f"export it as {TOKEN_ENV}, and run again. Or pass a JSON file you saved earlier "
            "instead of a Figma URL.",
            kind="token",
        )


def get_token(environ: Mapping[str, str] | None = None) -> str:
    """The token from ``FIGMA_TOKEN``; raises :class:`MissingTokenError` if unset/blank."""
    env = os.environ if environ is None else environ
    token = env.get(TOKEN_ENV, "").strip()
    if not token:
        raise MissingTokenError
    return token


def looks_like_figma_source(source: str) -> bool:
    """True for a figma.com file URL or a bare file key (not a local path)."""
    return bool(parse_source(source, strict=False))


def parse_source(source: str, *, strict: bool = True) -> tuple[str, str | None] | None:
    """Split a Figma URL or bare key into ``(file_key, node_id)``.

    ``node-id=1-2`` in a URL becomes the API form ``1:2``. For a branch URL the branch
    key is returned, since that is what the API expects. With ``strict=False`` an
    unrecognised string yields ``None`` instead of raising.
    """
    text = source.strip()
    if _BARE_KEY.match(text):
        return text, None
    parsed = urllib.parse.urlparse(text)
    host = (parsed.hostname or "").lower()
    if parsed.scheme in ("http", "https") and (host == "figma.com" or host.endswith(".figma.com")):
        match = _URL_KEY.match(parsed.path)
        if match:
            key = match.group(2) or match.group(1)
            node = urllib.parse.parse_qs(parsed.query).get("node-id", [None])[0]
            return key, node.replace("-", ":") if node else None
    if strict:
        raise FigmaApiError(
            f"{source!r} is not a Figma file URL or file key "
            "(expected https://www.figma.com/design/<key>/... or the bare key)",
            kind="response",
        )
    return None


def _resolve_base_url(base_url: str | None) -> str:
    base = (base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")
    parsed = urllib.parse.urlparse(base)
    local = parsed.scheme == "http" and (parsed.hostname or "") in LOCAL_HOSTS
    if parsed.scheme != "https" and not local:
        raise FigmaApiError(
            f"refusing to send credentials to {base!r}: the API base must be https "
            "(plain http is allowed only for localhost)",
            kind="response",
        )
    return base


class FigmaClient:
    """Fetches file, node and variable data for one access token."""

    def __init__(self, token: str, base_url: str | None = None, timeout: float = 30.0) -> None:
        if not token:
            raise MissingTokenError
        self._token = token
        self.base_url = _resolve_base_url(base_url)
        self.timeout = timeout

    def get_json(self, path: str, params: Mapping[str, str] | None = None) -> Any:
        """GET ``path`` and return the decoded JSON body, raising :class:`FigmaApiError`."""
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            headers={
                "X-Figma-Token": self._token,
                "Accept": "application/json",
                "User-Agent": f"figma2css/{__version__}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc, path) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise FigmaApiError(
                f"could not reach {self.base_url}: {reason}", kind="network"
            ) from None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise FigmaApiError(
                f"{path} returned a body that is not valid JSON", kind="response"
            ) from None

    @staticmethod
    def _http_error(exc: urllib.error.HTTPError, path: str) -> FigmaApiError:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = str(body.get("err") or body.get("message") or "")
        except (ValueError, UnicodeDecodeError, AttributeError, OSError):
            pass
        suffix = f" ({detail})" if detail else ""
        status = exc.code
        if status in (401, 403):
            return FigmaApiError(
                f"Figma rejected the request to {path} with HTTP {status}{suffix}. Check that "
                f"{TOKEN_ENV} is valid, not expired, has the needed scope and can open the file.",
                kind="token",
                status=status,
            )
        if status == 404:
            return FigmaApiError(
                f"Figma returned 404 for {path}{suffix}: the file or node does not exist, "
                "or your account cannot see it.",
                kind="not-found",
                status=status,
            )
        if status == 429:
            wait = exc.headers.get("Retry-After") if exc.headers else None
            hint = f" Retry after {wait} seconds." if wait else ""
            return FigmaApiError(
                f"Figma rate limit hit on {path}.{hint}", kind="rate-limit", status=status
            )
        kind = "server" if status >= 500 else "response"
        return FigmaApiError(
            f"Figma returned HTTP {status} for {path}{suffix}", kind=kind, status=status
        )

    def file(self, key: str) -> Any:
        """``GET /v1/files/:key`` - the whole document."""
        return self.get_json(f"/v1/files/{urllib.parse.quote(key, safe='')}")

    def nodes(self, key: str, node_ids: list[str]) -> Any:
        """``GET /v1/files/:key/nodes`` - only the named subtrees."""
        return self.get_json(
            f"/v1/files/{urllib.parse.quote(key, safe='')}/nodes", {"ids": ",".join(node_ids)}
        )

    def local_variables(self, key: str) -> Any:
        """``GET /v1/files/:key/variables/local`` (needs file_variables:read, Enterprise)."""
        return self.get_json(f"/v1/files/{urllib.parse.quote(key, safe='')}/variables/local")
