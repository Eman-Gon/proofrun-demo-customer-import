"""Stateless HTTP API and demo page. Run with python -m customer_service.server."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from .models import Customer

MAX_BODY_BYTES = 16_384
INDEX_PATH = Path(__file__).parent / "static" / "index.html"


def import_customer(payload):
    """Return a normalized record or reject a malformed customer."""
    if not isinstance(payload, dict) or set(payload) - {"name", "nickname"}:
        raise ValueError("invalid_customer")
    if "name" in payload and (
        not isinstance(payload["name"], str) or not payload["name"].strip()
    ):
        raise ValueError("invalid_customer")
    if "nickname" in payload and payload["nickname"] is not None and not isinstance(
        payload["nickname"], str
    ):
        raise ValueError("invalid_customer")
    try:
        customer = Customer(**payload)
    except ValidationError as error:
        raise ValueError("invalid_customer") from error
    return {"customer": {"name": customer.name, "nickname": customer.nickname}}


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def send_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, payload):
        self.send_bytes(
            status, json.dumps(payload, separators=(",", ":")).encode(),
            "application/json; charset=utf-8",
        )

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            self.send_json(200, {"status": "ok"})
        elif path == "/":
            self.send_bytes(200, INDEX_PATH.read_bytes(), "text/html; charset=utf-8")
        else:
            self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if urlsplit(self.path).path != "/customers/import":
            self.send_json(404, {"error": "not_found"})
            return
        if self.headers.get("Transfer-Encoding"):
            self.send_json(400, {"error": "unsupported_transfer_encoding"})
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "expected_json"})
            return
        if self.headers.get("Content-Length") is None:
            self.send_json(411, {"error": "length_required"})
            return
        try:
            length = int(self.headers["Content-Length"])
            if length < 0:
                raise ValueError
        except ValueError:
            self.send_json(400, {"error": "invalid_content_length"})
            return
        if length > MAX_BODY_BYTES:
            self.send_json(413, {"error": "request_too_large"})
            return
        try:
            body = self.rfile.read(length)
        except TimeoutError:
            self.send_json(408, {"error": "request_timeout"})
            return
        try:
            if len(body) != length:
                raise ValueError
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"error": "invalid_json"})
            return
        try:
            result = import_customer(payload)
        except ValueError:
            self.send_json(422, {"error": "invalid_customer"})
            return
        self.send_json(200, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Customer import demo: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
