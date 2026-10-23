"""Local dev server: real HTTP in front of the same API code, with a local store and orchestrator.

    TL_LLM_MODE=stub uv run python -m tenderlens.api.devserver          # offline, scripted agents
    TL_AWS_PROFILE=tenderlens uv run python -m tenderlens.api.devserver  # real Nova models, local storage

Requests are converted into API Gateway HTTP API events and passed to the Lambda's resolver, signed in as a
local demo user. Uploads and downloads that S3 presigned URLs handle in AWS are served under /dev/.
"""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit

from ..store import get_store
from .handler import app

PORT = int(os.environ.get("TL_DEV_PORT", "8787"))
USER = os.environ.get("TL_DEV_USER", "demo@tenderlens.local")
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
}


class Handler(BaseHTTPRequestHandler):
    def _send(
        self, status: int, body: bytes, content_type: str = "application/json", headers: dict | None = None
    ):
        self.send_response(status)
        for key, value in {**CORS, "Content-Type": content_type, **(headers or {})}.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def do_OPTIONS(self):  # noqa: N802
        self._send(204, b"")

    def do_PUT(self):  # noqa: N802
        path = urlsplit(self.path).path
        if not path.startswith("/dev/upload/"):
            return self._send(404, b'{"message": "not found"}')
        get_store().put_bytes(path.removeprefix("/dev/upload/"), self._body())
        self._send(200, b"{}")

    def do_GET(self):  # noqa: N802
        path = urlsplit(self.path).path
        if path.startswith("/dev/files/"):
            key = path.removeprefix("/dev/files/")
            store = get_store()
            if not store.exists(key):
                return self._send(404, b'{"message": "not found"}')
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
            name = key.rsplit("/", 1)[-1]
            return self._send(
                200,
                store.get_bytes(key),
                content_type,
                {"Content-Disposition": f'attachment; filename="{name}"'},
            )
        self._api("GET")

    def do_POST(self):  # noqa: N802
        self._api("POST")

    def _api(self, method: str):
        parts = urlsplit(self.path)
        event = {
            "version": "2.0",
            "routeKey": "$default",
            "rawPath": parts.path,
            "rawQueryString": parts.query,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "requestContext": {
                "http": {"method": method, "path": parts.path, "sourceIp": "127.0.0.1"},
                "authorizer": {"jwt": {"claims": {"email": USER}, "scopes": []}},
                "stage": "$default",
            },
            "body": self._body().decode() if method == "POST" else None,
            "isBase64Encoded": False,
        }
        result = app.resolve(event, SimpleNamespace(function_name="devserver", aws_request_id="local"))
        body = result.get("body") or ""
        headers = {
            k: v
            for k, v in (result.get("headers") or {}).items()
            if not k.lower().startswith("access-control")
        }
        content_type = headers.pop("Content-Type", "application/json")
        self._send(result.get("statusCode", 200), body.encode(), content_type, headers)

    def log_message(self, fmt, *args):
        if os.environ.get("TL_DEV_QUIET") != "1":
            super().log_message(fmt, *args)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="TenderLens local API")
    parser.add_argument("--stub", action="store_true", help="use scripted offline agents instead of Bedrock")
    if parser.parse_args().stub:
        os.environ["TL_LLM_MODE"] = "stub"
    os.environ.setdefault("TL_STORE", "local")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    mode = os.environ.get("TL_LLM_MODE", "bedrock")
    print(
        json.dumps(
            {
                "api": f"http://localhost:{PORT}",
                "user": USER,
                "llm": mode,
                "store": get_store().__class__.__name__,
            }
        ),
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
