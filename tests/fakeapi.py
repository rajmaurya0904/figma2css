"""A throwaway local HTTP server that imitates the Figma REST API for tests.

It speaks real HTTP on 127.0.0.1, so the client's request building, headers, status
handling and JSON decoding are exercised end to end without any network access or
real credentials.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class FakeFigma:
    """Serve ``routes`` (path -> (status, body, headers)) and record every request."""

    def __init__(self, routes: dict[str, tuple[int, Any, dict[str, str]]]) -> None:
        self.routes = routes
        self.requests: list[dict[str, Any]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server naming
                path = self.path.split("?", 1)[0]
                outer.requests.append(
                    {"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}}
                )
                missing = (404, {"status": 404, "err": "Not found"}, {})
                status, body, headers = outer.routes.get(path, missing)
                payload = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args: Any) -> None:
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __enter__(self) -> FakeFigma:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
